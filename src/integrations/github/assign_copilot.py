"""Helpers for assigning issues to the GitHub Copilot code assistant."""

from __future__ import annotations

import json
import os
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from typing import Mapping, Sequence
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
class CopilotHandoffResult:
    """Represents the outcome of handing an issue to the Copilot agent."""

    issue_number: int
    branch_name: str
    agent_output: str
    label_removed: bool


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

    env = os.environ.copy()
    env.setdefault("GH_TOKEN", token)
    env.setdefault("GITHUB_TOKEN", token)

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
        raise GitHubIssueError(message) from exc


def create_branch_for_issue(
    *,
    token: str,
    repository: str,
    issue_number: int,
    branch_name: str,
    base_branch: str | None = None,
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
    run_gh_command(args, token=token, capture_output=True)


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


def create_agent_task(
    *,
    token: str,
    repository: str,
    prompt: str,
    base_branch: str | None = None,
) -> str:
    """Start a Copilot agent task using the GitHub CLI."""

    args: list[str] = ["agent-task", "create", prompt, "--repo", repository]
    if base_branch:
        args.extend(["--base", base_branch])

    completed = run_gh_command(args, token=token, capture_output=True)
    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    if stdout and stderr:
        return f"{stdout}\n{stderr}".strip()
    return stdout or stderr


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


def handoff_issue_to_copilot(
    *,
    token: str,
    repository: str,
    issue_number: int,
    label: str,
    api_url: str = DEFAULT_API_URL,
    base_branch: str | None = None,
    extra_instructions: str | None = None,
) -> CopilotHandoffResult:
    """Perform the branch creation, agent task, and label cleanup for an issue."""

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
    )

    prompt = compose_agent_prompt(issue, branch_name, extra_instructions)
    agent_output = create_agent_task(
        token=token,
        repository=repository,
        prompt=prompt,
        base_branch=base_branch,
    )

    label_removed = remove_issue_label(
        token=token,
        repository=repository,
        issue_number=issue.number,
        label=label,
        api_url=api_url,
    )

    return CopilotHandoffResult(
        issue_number=issue.number,
        branch_name=branch_name,
        agent_output=agent_output,
        label_removed=label_removed,
    )


def assign_issues_to_copilot(
    *,
    token: str,
    repository: str,
    issue_numbers: Sequence[int],
    label: str,
    api_url: str = DEFAULT_API_URL,
    base_branch: str | None = None,
    extra_instructions: str | None = None,
) -> list[CopilotHandoffResult]:
    """Hand off multiple issues to the Copilot coding agent."""

    outcomes: list[CopilotHandoffResult] = []
    for issue_number in issue_numbers:
        outcomes.append(
            handoff_issue_to_copilot(
                token=token,
                repository=repository,
                issue_number=issue_number,
                label=label,
                api_url=api_url,
                base_branch=base_branch,
                extra_instructions=extra_instructions,
            )
        )
    return outcomes
