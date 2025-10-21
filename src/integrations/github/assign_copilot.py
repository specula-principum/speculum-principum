"""Helpers for assigning issues to the GitHub Copilot code assistant."""

from __future__ import annotations

import json
import os
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence
from urllib import error, parse, request

from .issues import API_VERSION, DEFAULT_API_URL, GitHubIssueError, normalize_repository


@dataclass(frozen=True)
class IssueDetails:
    """Full issue details used for Copilot handoff."""

    number: int
    title: str
    body: str
    url: str
    labels: tuple[str, ...]


@dataclass(frozen=True)
class LocalAgentRunResult:
    """Outcome details for a locally executed Copilot agent run."""

    issue_number: int
    issue_title: str
    branch_name: str
    prompt: str
    push_output: str | None
    pr_output: str | None
    label_removed: bool


DEFAULT_ALLOWED_COPILOT_TOOLS: tuple[str, ...] = (
    "write",
    "github-mcp-server(web_search)",
    "github-mcp-server(list_issues)",
    "github-mcp-server(get_issue)",
    "shell(gh issue:*)",
    "shell(gh pr create)",
)


def _normalize_allowed_tools(allowed_tools: Sequence[str] | None) -> tuple[str, ...]:
    """Return a de-duplicated tuple of allowed tool identifiers."""

    if allowed_tools is None:
        items: Iterable[str] = DEFAULT_ALLOWED_COPILOT_TOOLS
    elif isinstance(allowed_tools, str):
        items = (allowed_tools,)
    else:
        items = allowed_tools

    unique: list[str] = []
    for tool in items:
        value = tool.strip()
        if not value:
            continue
        if value not in unique:
            unique.append(value)
    return tuple(unique)


def fetch_issue_details(
    *,
    token: str,
    repository: str,
    issue_number: int,
    api_url: str = DEFAULT_API_URL,
) -> IssueDetails:
    """Retrieve title, body, URL, and labels for the issue."""

    owner, name = normalize_repository(repository)
    url = f"{api_url.rstrip('/')}/repos/{owner}/{name}/issues/{issue_number}"
    req = request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", API_VERSION)

    try:
        with request.urlopen(req) as response:  # type: ignore[no-any-unimported]
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace")
        raise GitHubIssueError(
            f"GitHub API error ({exc.code}): {error_text.strip()}"
        ) from exc
    except error.URLError as exc:
        raise GitHubIssueError(f"Failed to reach GitHub API: {exc.reason}") from exc

    if not isinstance(payload, Mapping):  # pragma: no cover - defensive
        raise GitHubIssueError("Unexpected GitHub response payload")

    try:
        title = str(payload.get("title", ""))
        url = str(payload.get("html_url") or payload.get("url"))
        body = str(payload.get("body") or "")
        labels_payload = payload.get("labels", [])
    except (TypeError, ValueError) as exc:  # pragma: no cover - protective
        raise GitHubIssueError("Unexpected GitHub response payload") from exc

    labels: list[str] = []
    if isinstance(labels_payload, Sequence):
        for entry in labels_payload:
            if isinstance(entry, Mapping):
                name_value = entry.get("name")
                if isinstance(name_value, str):
                    labels.append(name_value)

    return IssueDetails(
        number=issue_number,
        title=title,
        body=body,
        url=url,
        labels=tuple(labels),
    )


def _ascii_slug(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.lower()
    ascii_text = re.sub(r"[^a-z0-9]+", "-", ascii_text)
    ascii_text = ascii_text.strip("-")
    return ascii_text or "issue"


def _build_cli_env(token: str) -> dict[str, str]:
    env = os.environ.copy()
    if token:
        env.setdefault("GITHUB_TOKEN", token)
        env.setdefault("GH_TOKEN", token)
    return env


def generate_branch_name(issue_number: int, title: str, *, prefix: str = "copilot") -> str:
    """Return a predictable branch name for the Copilot handoff."""

    slug = _ascii_slug(title)
    base = f"{prefix}/issue-{issue_number}-{slug}"
    if len(base) <= 90:
        return base
    # Truncate overly long slugs while keeping the prefix and issue number intact.
    limit = max(10, 90 - len(f"{prefix}/issue-{issue_number}-"))
    return f"{prefix}/issue-{issue_number}-{slug[:limit]}"


def run_gh_command(
    args: Sequence[str],
    *,
    token: str,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a GitHub CLI command with the provided token."""

    env = _build_cli_env(token)

    try:
        return subprocess.run(  # type: ignore[return-value]
            ["gh", *args],
            env=env,
            check=True,
            text=True,
            capture_output=capture_output,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive
        stdout = (exc.stdout or "").strip()
        stderr = (exc.stderr or "").strip()
        details = "\n".join(part for part in (stdout, stderr) if part)
        command = "gh " + " ".join(args)
        message = f"Command '{command}' failed"
        if details:
            message = f"{message}: {details}"
        if "requires an OAuth token" in details:
            message = (
                f"{message}. Provide a Copilot-enabled personal access token via "
                "the GITHUB_TOKEN environment variable."
            )
        raise GitHubIssueError(message) from exc


def _branch_exists(
    *,
    token: str,
    repository: str,
    branch_name: str,
    api_url: str = DEFAULT_API_URL,
) -> bool:
    owner, name = normalize_repository(repository)
    encoded = parse.quote(branch_name, safe="")
    url = f"{api_url.rstrip('/')}/repos/{owner}/{name}/branches/{encoded}"
    req = request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", API_VERSION)

    try:
        with request.urlopen(req) as response:  # type: ignore[no-any-unimported]
            response.read()
    except error.HTTPError as exc:
        if exc.code == 404:
            return False
        error_text = exc.read().decode("utf-8", errors="replace")
        raise GitHubIssueError(
            f"GitHub API error ({exc.code}): {error_text.strip()}"
        ) from exc
    except error.URLError as exc:
        raise GitHubIssueError(f"Failed to reach GitHub API: {exc.reason}") from exc

    return True


def _checkout_existing_branch(branch_name: str) -> None:
    commands = [
        ["git", "fetch", "origin", branch_name],
        ["git", "checkout", "-B", branch_name, f"origin/{branch_name}"],
    ]
    for args in commands:
        try:
            subprocess.run(
                args,
                check=True,
                text=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            stdout = (exc.stdout or "").strip()
            stderr = (exc.stderr or "").strip()
            details = "\n".join(part for part in (stdout, stderr) if part)
            message = f"Command '{' '.join(args)}' failed"
            if details:
                message = f"{message}: {details}"
            raise GitHubIssueError(message) from exc


def create_branch_for_issue(
    *,
    token: str,
    repository: str,
    issue_number: int,
    branch_name: str,
    base_branch: str | None = None,
    api_url: str = DEFAULT_API_URL,
) -> None:
    """Create and checkout a development branch linked to the issue."""

    args: list[str] = [
        "issue",
        "develop",
        str(issue_number),
        "--name",
        branch_name,
        "--repo",
        repository,
        "--checkout",
    ]
    if base_branch:
        args.extend(["--base", base_branch])
    try:
        run_gh_command(args, token=token, capture_output=True)
    except GitHubIssueError as exc:
        try:
            exists = _branch_exists(
                token=token,
                repository=repository,
                branch_name=branch_name,
                api_url=api_url,
            )
        except GitHubIssueError as inner_exc:
            raise exc from inner_exc

        if not exists:
            raise exc

        _checkout_existing_branch(branch_name)
        print(f"Reusing existing branch '{branch_name}'.")


def compose_agent_prompt(
    issue: IssueDetails,
    branch_name: str,
    extra_instructions: str | None = None,
) -> str:
    """Generate a Copilot agent prompt that includes issue context."""

    lines = [
        f"Work on GitHub issue #{issue.number}: {issue.title}.",
        f"Use the existing branch '{branch_name}' for your changes.",
        "Create a pull request that resolves this issue when you are done.",
        "",
        f"Issue URL: {issue.url}",
    ]

    if issue.labels:
        lines.append(f"Labels: {', '.join(issue.labels)}")

    body_text = issue.body.strip()
    if body_text:
        lines.extend(["", "Issue body:", body_text])

    if extra_instructions:
        lines.extend(["", "Additional instructions:", extra_instructions.strip()])

    return "\n".join(lines).strip()


def run_copilot_prompt(
    *,
    token: str,
    prompt: str,
    copilot_command: str = "copilot",
    copilot_args: Sequence[str] | None = None,
    allowed_tools: Sequence[str] | None = DEFAULT_ALLOWED_COPILOT_TOOLS,
    model: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke the GitHub Copilot CLI with the supplied prompt."""

    if copilot_args and any(option in {"--prompt", "-p"} for option in copilot_args):
        raise GitHubIssueError("Provide Copilot CLI flags without --prompt; it is managed automatically.")

    command: list[str] = [copilot_command]
    if copilot_args:
        command.extend(copilot_args)
    tools_to_allow = _normalize_allowed_tools(allowed_tools)
    for tool in tools_to_allow:
        command.extend(["--allow-tool", tool])
    if model:
        command.extend(["--model", model])
    command.extend(["--prompt", prompt])

    try:
        return subprocess.run(  # type: ignore[return-value]
            command,
            env=_build_cli_env(token),
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive
        raise GitHubIssueError(f"Command '{' '.join(command)}' failed") from exc


def _push_branch(branch_name: str) -> str:
    try:
        completed = subprocess.run(  # type: ignore[return-value]
            ["git", "push", "--set-upstream", "origin", branch_name],
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive
        stdout = (exc.stdout or "").strip()
        stderr = (exc.stderr or "").strip()
        details = "\n".join(part for part in (stdout, stderr) if part)
        message = f"Command 'git push --set-upstream origin {branch_name}' failed"
        if details:
            message = f"{message}: {details}"
        raise GitHubIssueError(message) from exc

    output = (completed.stdout or "").strip()
    if completed.stderr:
        output = "\n".join(filter(None, [output, completed.stderr.strip()]))
    return output.strip() or "Branch pushed successfully."


def _discover_existing_pull_request(
    *,
    token: str,
    repository: str,
    branch_name: str,
) -> tuple[int, str] | None:
    args = [
        "pr",
        "view",
        "--head",
        branch_name,
        "--repo",
        repository,
        "--json",
        "number,url",
    ]
    completed = subprocess.run(  # type: ignore[return-value]
        ["gh", *args],
        env=_build_cli_env(token),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return None

    try:
        payload = json.loads((completed.stdout or "{}").strip() or "{}")
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, Mapping):
        return None

    number = payload.get("number")
    url = payload.get("url")
    if isinstance(number, int) and isinstance(url, str) and url:
        return number, url
    return None


def create_pull_request_for_branch(
    *,
    token: str,
    repository: str,
    branch_name: str,
    base_branch: str | None = None,
    draft: bool = False,
) -> str:
    existing = _discover_existing_pull_request(
        token=token,
        repository=repository,
        branch_name=branch_name,
    )
    if existing:
        number, url = existing
        return f"Pull request already exists: #{number} {url}"

    args: list[str] = [
        "pr",
        "create",
        "--head",
        branch_name,
        "--repo",
        repository,
        "--fill",
    ]
    if base_branch:
        args.extend(["--base", base_branch])
    if draft:
        args.append("--draft")

    try:
        completed = run_gh_command(args, token=token, capture_output=True)
    except GitHubIssueError:
        existing = _discover_existing_pull_request(
            token=token,
            repository=repository,
            branch_name=branch_name,
        )
        if existing:
            number, url = existing
            return f"Pull request already exists: #{number} {url}"
        raise
    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    if stdout and stderr:
        return f"{stdout}\n{stderr}".strip()
    return stdout or stderr


def run_issue_with_local_copilot(
    *,
    token: str,
    repository: str,
    issue_number: int,
    label_to_remove: str | None,
    api_url: str = DEFAULT_API_URL,
    base_branch: str | None = None,
    extra_instructions: str | None = None,
    copilot_command: str = "copilot",
    copilot_model: str | None = "claude-haiku-4.5",
    copilot_args: Sequence[str] | None = None,
    allowed_tools: Sequence[str] | None = DEFAULT_ALLOWED_COPILOT_TOOLS,
    push_branch_before_pr: bool = True,
    create_pr: bool = True,
    pr_draft: bool = False,
) -> LocalAgentRunResult:
    issue = fetch_issue_details(
        token=token,
        repository=repository,
        issue_number=issue_number,
        api_url=api_url,
    )
    branch_name = generate_branch_name(issue.number, issue.title)

    create_branch_for_issue(
        token=token,
        repository=repository,
        issue_number=issue.number,
        branch_name=branch_name,
        base_branch=base_branch,
        api_url=api_url,
    )

    prompt = compose_agent_prompt(issue, branch_name, extra_instructions)

    run_copilot_prompt(
        token=token,
        prompt=prompt,
        copilot_command=copilot_command,
        copilot_args=copilot_args,
        allowed_tools=allowed_tools,
        model=copilot_model,
    )

    push_output: str | None = None
    if push_branch_before_pr:
        push_output = _push_branch(branch_name)

    pr_output: str | None = None
    if create_pr:
        if push_output is None:
            push_output = _push_branch(branch_name)
        pr_output = create_pull_request_for_branch(
            token=token,
            repository=repository,
            branch_name=branch_name,
            base_branch=base_branch,
            draft=pr_draft,
        )

    label_removed = False
    if label_to_remove:
        label_removed = remove_issue_label(
            token=token,
            repository=repository,
            issue_number=issue.number,
            label=label_to_remove,
            api_url=api_url,
        )

    return LocalAgentRunResult(
        issue_number=issue.number,
        issue_title=issue.title,
        branch_name=branch_name,
        prompt=prompt,
        push_output=push_output,
        pr_output=pr_output,
        label_removed=label_removed,
    )


def remove_issue_label(
    *,
    token: str,
    repository: str,
    issue_number: int,
    label: str,
    api_url: str = DEFAULT_API_URL,
) -> bool:
    """Remove a label from the issue if it exists."""

    owner, name = normalize_repository(repository)
    encoded_label = parse.quote(label, safe="")
    url = f"{api_url.rstrip('/')}/repos/{owner}/{name}/issues/{issue_number}/labels/{encoded_label}"
    req = request.Request(url, method="DELETE")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", API_VERSION)

    try:
        with request.urlopen(req) as response:  # type: ignore[no-any-unimported]
            response.read()
    except error.HTTPError as exc:
        if exc.code == 404:
            return False
        error_text = exc.read().decode("utf-8", errors="replace")
        raise GitHubIssueError(
            f"GitHub API error ({exc.code}): {error_text.strip()}"
        ) from exc
    except error.URLError as exc:
        raise GitHubIssueError(f"Failed to reach GitHub API: {exc.reason}") from exc

    return True

