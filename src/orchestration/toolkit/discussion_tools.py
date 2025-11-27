"""GitHub Discussions tool registrations for the orchestration runtime."""

from __future__ import annotations

from typing import Any, Mapping

from src.integrations.github import discussions as github_discussions
from src.knowledge.aggregation import (
    KnowledgeAggregator,
    build_changelog_comment,
    build_entity_discussion_content,
)
from src.knowledge.storage import KnowledgeGraphStorage

from ..safety import ActionRisk
from ..tools import ToolDefinition, ToolRegistry
from ..types import ToolResult


def register_discussion_read_tools(registry: ToolRegistry) -> None:
    """Register safe GitHub Discussions read-only tools with the registry."""

    registry.register_tool(
        ToolDefinition(
            name="list_discussion_categories",
            description="List all discussion categories available in a GitHub repository.",
            parameters={
                "type": "object",
                "properties": {
                    "repository": {
                        "type": "string",
                        "description": "Repository name in 'owner/name' format. Defaults to GITHUB_REPOSITORY env var.",
                    },
                    "token": {
                        "type": "string",
                        "description": "GitHub token with read access. Defaults to GITHUB_TOKEN env var.",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
            handler=_list_discussion_categories_handler,
            risk_level=ActionRisk.SAFE,
        )
    )

    registry.register_tool(
        ToolDefinition(
            name="get_category_by_name",
            description="Find a discussion category by name (case-insensitive).",
            parameters={
                "type": "object",
                "properties": {
                    "category_name": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Name of the category to find.",
                    },
                    "repository": {
                        "type": "string",
                        "description": "Repository name in 'owner/name' format. Defaults to GITHUB_REPOSITORY env var.",
                    },
                    "token": {
                        "type": "string",
                        "description": "GitHub token with read access. Defaults to GITHUB_TOKEN env var.",
                    },
                },
                "required": ["category_name"],
                "additionalProperties": False,
            },
            handler=_get_category_by_name_handler,
            risk_level=ActionRisk.SAFE,
        )
    )

    registry.register_tool(
        ToolDefinition(
            name="find_discussion_by_title",
            description="Find an existing discussion by exact title match (case-insensitive).",
            parameters={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Title of the discussion to find.",
                    },
                    "category_id": {
                        "type": "string",
                        "description": "Optional category ID to narrow the search.",
                    },
                    "repository": {
                        "type": "string",
                        "description": "Repository name in 'owner/name' format. Defaults to GITHUB_REPOSITORY env var.",
                    },
                    "token": {
                        "type": "string",
                        "description": "GitHub token with read access. Defaults to GITHUB_TOKEN env var.",
                    },
                },
                "required": ["title"],
                "additionalProperties": False,
            },
            handler=_find_discussion_by_title_handler,
            risk_level=ActionRisk.SAFE,
        )
    )

    registry.register_tool(
        ToolDefinition(
            name="get_discussion",
            description="Get a discussion by its number.",
            parameters={
                "type": "object",
                "properties": {
                    "discussion_number": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Numeric identifier of the discussion.",
                    },
                    "repository": {
                        "type": "string",
                        "description": "Repository name in 'owner/name' format. Defaults to GITHUB_REPOSITORY env var.",
                    },
                    "token": {
                        "type": "string",
                        "description": "GitHub token with read access. Defaults to GITHUB_TOKEN env var.",
                    },
                },
                "required": ["discussion_number"],
                "additionalProperties": False,
            },
            handler=_get_discussion_handler,
            risk_level=ActionRisk.SAFE,
        )
    )

    registry.register_tool(
        ToolDefinition(
            name="list_discussions",
            description="List discussions in a repository, optionally filtered by category.",
            parameters={
                "type": "object",
                "properties": {
                    "category_id": {
                        "type": "string",
                        "description": "Optional category ID to filter discussions.",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "description": "Maximum number of discussions to return (1-100).",
                    },
                    "repository": {
                        "type": "string",
                        "description": "Repository name in 'owner/name' format. Defaults to GITHUB_REPOSITORY env var.",
                    },
                    "token": {
                        "type": "string",
                        "description": "GitHub token with read access. Defaults to GITHUB_TOKEN env var.",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
            handler=_list_discussions_handler,
            risk_level=ActionRisk.SAFE,
        )
    )


def register_discussion_mutation_tools(registry: ToolRegistry) -> None:
    """Register GitHub Discussions mutation tools (write operations) with the registry."""

    registry.register_tool(
        ToolDefinition(
            name="create_discussion",
            description="Create a new discussion in a GitHub repository.",
            parameters={
                "type": "object",
                "properties": {
                    "category_id": {
                        "type": "string",
                        "minLength": 1,
                        "description": "GraphQL node ID of the category for this discussion.",
                    },
                    "title": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Title of the discussion.",
                    },
                    "body": {
                        "type": "string",
                        "description": "Markdown content for the discussion body.",
                    },
                    "repository": {
                        "type": "string",
                        "description": "Repository name in 'owner/name' format. Defaults to GITHUB_REPOSITORY env var.",
                    },
                    "token": {
                        "type": "string",
                        "description": "GitHub token with write access. Defaults to GITHUB_TOKEN env var.",
                    },
                },
                "required": ["category_id", "title", "body"],
                "additionalProperties": False,
            },
            handler=_create_discussion_handler,
            risk_level=ActionRisk.REVIEW,
        )
    )

    registry.register_tool(
        ToolDefinition(
            name="update_discussion",
            description="Update an existing discussion's title and/or body.",
            parameters={
                "type": "object",
                "properties": {
                    "discussion_id": {
                        "type": "string",
                        "minLength": 1,
                        "description": "GraphQL node ID of the discussion to update.",
                    },
                    "title": {
                        "type": "string",
                        "description": "New title for the discussion (optional).",
                    },
                    "body": {
                        "type": "string",
                        "description": "New body content for the discussion (optional).",
                    },
                    "token": {
                        "type": "string",
                        "description": "GitHub token with write access. Defaults to GITHUB_TOKEN env var.",
                    },
                },
                "required": ["discussion_id"],
                "additionalProperties": False,
            },
            handler=_update_discussion_handler,
            risk_level=ActionRisk.REVIEW,
        )
    )

    registry.register_tool(
        ToolDefinition(
            name="add_discussion_comment",
            description="Add a comment to an existing discussion.",
            parameters={
                "type": "object",
                "properties": {
                    "discussion_id": {
                        "type": "string",
                        "minLength": 1,
                        "description": "GraphQL node ID of the discussion.",
                    },
                    "body": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Markdown content for the comment.",
                    },
                    "token": {
                        "type": "string",
                        "description": "GitHub token with write access. Defaults to GITHUB_TOKEN env var.",
                    },
                },
                "required": ["discussion_id", "body"],
                "additionalProperties": False,
            },
            handler=_add_discussion_comment_handler,
            risk_level=ActionRisk.REVIEW,
        )
    )


def register_knowledge_graph_tools(registry: ToolRegistry) -> None:
    """Register knowledge graph read tools with the registry."""

    registry.register_tool(
        ToolDefinition(
            name="list_knowledge_entities",
            description="List all unique entity names in the knowledge graph, optionally filtered by type.",
            parameters={
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "enum": ["Person", "Organization", "Concept"],
                        "description": "Filter by entity type. Omit to list all types.",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
            handler=_list_knowledge_entities_handler,
            risk_level=ActionRisk.SAFE,
        )
    )

    registry.register_tool(
        ToolDefinition(
            name="get_entity_profile",
            description="Get aggregated profile information for an entity from the knowledge graph.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Name of the entity to retrieve (case-insensitive).",
                    },
                    "entity_type": {
                        "type": "string",
                        "enum": ["Person", "Organization", "Concept"],
                        "description": "Optional filter by entity type.",
                    },
                },
                "required": ["name"],
                "additionalProperties": False,
            },
            handler=_get_entity_profile_handler,
            risk_level=ActionRisk.SAFE,
        )
    )

    registry.register_tool(
        ToolDefinition(
            name="build_entity_discussion_body",
            description="Generate markdown discussion body content for an entity.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Name of the entity (case-insensitive).",
                    },
                    "entity_type": {
                        "type": "string",
                        "enum": ["Person", "Organization", "Concept"],
                        "description": "Optional filter by entity type.",
                    },
                    "include_checksums": {
                        "type": "boolean",
                        "description": "Whether to include source checksums. Defaults to true.",
                    },
                },
                "required": ["name"],
                "additionalProperties": False,
            },
            handler=_build_entity_discussion_body_handler,
            risk_level=ActionRisk.SAFE,
        )
    )


def register_discussion_sync_tools(registry: ToolRegistry) -> None:
    """Register composite discussion sync tools with the registry."""

    registry.register_tool(
        ToolDefinition(
            name="sync_entity_discussion",
            description=(
                "Sync a knowledge graph entity to a GitHub Discussion. "
                "Creates or updates the discussion and adds a changelog comment if changed."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Name of the entity to sync (case-insensitive).",
                    },
                    "entity_type": {
                        "type": "string",
                        "enum": ["Person", "Organization"],
                        "description": "Entity type determines the discussion category.",
                    },
                    "repository": {
                        "type": "string",
                        "description": "Repository name in 'owner/name' format. Defaults to GITHUB_REPOSITORY env var.",
                    },
                    "token": {
                        "type": "string",
                        "description": "GitHub token with write access. Defaults to GITHUB_TOKEN env var.",
                    },
                },
                "required": ["entity_name", "entity_type"],
                "additionalProperties": False,
            },
            handler=_sync_entity_discussion_handler,
            risk_level=ActionRisk.REVIEW,
        )
    )


# =============================================================================
# Handler Implementations - Read Operations
# =============================================================================


def _resolve_credentials(args: Mapping[str, Any]) -> tuple[str, str] | ToolResult:
    """Resolve repository and token from args or environment."""
    repository_arg = args.get("repository")
    token_arg = args.get("token")
    try:
        repository = github_discussions.resolve_repository(
            str(repository_arg) if repository_arg else None
        )
        token = github_discussions.resolve_token(
            str(token_arg) if token_arg else None
        )
        return repository, token
    except github_discussions.GitHubDiscussionError as exc:
        return ToolResult(success=False, output=None, error=str(exc))


def _list_discussion_categories_handler(args: Mapping[str, Any]) -> ToolResult:
    creds = _resolve_credentials(args)
    if isinstance(creds, ToolResult):
        return creds
    repository, token = creds

    try:
        categories = github_discussions.list_discussion_categories(
            token=token,
            repository=repository,
        )
        return ToolResult(
            success=True,
            output={
                "count": len(categories),
                "categories": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "slug": c.slug,
                        "description": c.description,
                    }
                    for c in categories
                ],
            },
            error=None,
        )
    except github_discussions.GitHubDiscussionError as exc:
        return ToolResult(success=False, output=None, error=str(exc))


def _get_category_by_name_handler(args: Mapping[str, Any]) -> ToolResult:
    category_name = args.get("category_name")
    if not isinstance(category_name, str) or not category_name.strip():
        return ToolResult(success=False, output=None, error="category_name must be a non-empty string.")

    creds = _resolve_credentials(args)
    if isinstance(creds, ToolResult):
        return creds
    repository, token = creds

    try:
        category = github_discussions.get_category_by_name(
            token=token,
            repository=repository,
            category_name=category_name.strip(),
        )
        if category is None:
            return ToolResult(
                success=True,
                output={"found": False, "category": None},
                error=None,
            )
        return ToolResult(
            success=True,
            output={
                "found": True,
                "category": {
                    "id": category.id,
                    "name": category.name,
                    "slug": category.slug,
                    "description": category.description,
                },
            },
            error=None,
        )
    except github_discussions.GitHubDiscussionError as exc:
        return ToolResult(success=False, output=None, error=str(exc))


def _find_discussion_by_title_handler(args: Mapping[str, Any]) -> ToolResult:
    title = args.get("title")
    if not isinstance(title, str) or not title.strip():
        return ToolResult(success=False, output=None, error="title must be a non-empty string.")

    category_id = args.get("category_id")

    creds = _resolve_credentials(args)
    if isinstance(creds, ToolResult):
        return creds
    repository, token = creds

    try:
        discussion = github_discussions.find_discussion_by_title(
            token=token,
            repository=repository,
            title=title.strip(),
            category_id=str(category_id) if category_id else None,
        )
        if discussion is None:
            return ToolResult(
                success=True,
                output={"found": False, "discussion": None},
                error=None,
            )
        return ToolResult(
            success=True,
            output={
                "found": True,
                "discussion": {
                    "id": discussion.id,
                    "number": discussion.number,
                    "title": discussion.title,
                    "url": discussion.url,
                    "category_id": discussion.category_id,
                    "category_name": discussion.category_name,
                },
            },
            error=None,
        )
    except github_discussions.GitHubDiscussionError as exc:
        return ToolResult(success=False, output=None, error=str(exc))


def _get_discussion_handler(args: Mapping[str, Any]) -> ToolResult:
    discussion_number = args.get("discussion_number")
    if not isinstance(discussion_number, int) or discussion_number < 1:
        return ToolResult(success=False, output=None, error="discussion_number must be a positive integer.")

    creds = _resolve_credentials(args)
    if isinstance(creds, ToolResult):
        return creds
    repository, token = creds

    try:
        discussion = github_discussions.get_discussion(
            token=token,
            repository=repository,
            discussion_number=discussion_number,
        )
        return ToolResult(
            success=True,
            output={
                "id": discussion.id,
                "number": discussion.number,
                "title": discussion.title,
                "body": discussion.body,
                "url": discussion.url,
                "category_id": discussion.category_id,
                "category_name": discussion.category_name,
                "author": discussion.author_login,
                "created_at": discussion.created_at,
                "updated_at": discussion.updated_at,
            },
            error=None,
        )
    except github_discussions.GitHubDiscussionError as exc:
        return ToolResult(success=False, output=None, error=str(exc))


def _list_discussions_handler(args: Mapping[str, Any]) -> ToolResult:
    category_id = args.get("category_id")
    limit = args.get("limit", 50)

    if not isinstance(limit, int) or limit < 1 or limit > 100:
        return ToolResult(success=False, output=None, error="limit must be between 1 and 100.")

    creds = _resolve_credentials(args)
    if isinstance(creds, ToolResult):
        return creds
    repository, token = creds

    try:
        discussions = github_discussions.list_discussions(
            token=token,
            repository=repository,
            category_id=str(category_id) if category_id else None,
            limit=limit,
        )
        return ToolResult(
            success=True,
            output={
                "count": len(discussions),
                "discussions": [
                    {
                        "id": d.id,
                        "number": d.number,
                        "title": d.title,
                        "url": d.url,
                        "category_name": d.category_name,
                    }
                    for d in discussions
                ],
            },
            error=None,
        )
    except github_discussions.GitHubDiscussionError as exc:
        return ToolResult(success=False, output=None, error=str(exc))


# =============================================================================
# Handler Implementations - Mutation Operations
# =============================================================================


def _create_discussion_handler(args: Mapping[str, Any]) -> ToolResult:
    category_id = args.get("category_id")
    if not isinstance(category_id, str) or not category_id.strip():
        return ToolResult(success=False, output=None, error="category_id must be a non-empty string.")

    title = args.get("title")
    if not isinstance(title, str) or not title.strip():
        return ToolResult(success=False, output=None, error="title must be a non-empty string.")

    body = args.get("body", "")

    creds = _resolve_credentials(args)
    if isinstance(creds, ToolResult):
        return creds
    repository, token = creds

    try:
        discussion = github_discussions.create_discussion(
            token=token,
            repository=repository,
            category_id=category_id.strip(),
            title=title.strip(),
            body=str(body),
        )
        return ToolResult(
            success=True,
            output={
                "created": True,
                "id": discussion.id,
                "number": discussion.number,
                "title": discussion.title,
                "url": discussion.url,
            },
            error=None,
        )
    except github_discussions.GitHubDiscussionError as exc:
        return ToolResult(success=False, output=None, error=str(exc))


def _update_discussion_handler(args: Mapping[str, Any]) -> ToolResult:
    discussion_id = args.get("discussion_id")
    if not isinstance(discussion_id, str) or not discussion_id.strip():
        return ToolResult(success=False, output=None, error="discussion_id must be a non-empty string.")

    title = args.get("title")
    body = args.get("body")

    if title is None and body is None:
        return ToolResult(success=False, output=None, error="At least one of title or body must be provided.")

    token_arg = args.get("token")
    try:
        token = github_discussions.resolve_token(str(token_arg) if token_arg else None)
    except github_discussions.GitHubDiscussionError as exc:
        return ToolResult(success=False, output=None, error=str(exc))

    try:
        discussion = github_discussions.update_discussion(
            token=token,
            discussion_id=discussion_id.strip(),
            title=str(title) if title else None,
            body=str(body) if body else None,
        )
        return ToolResult(
            success=True,
            output={
                "updated": True,
                "id": discussion.id,
                "number": discussion.number,
                "title": discussion.title,
                "url": discussion.url,
            },
            error=None,
        )
    except github_discussions.GitHubDiscussionError as exc:
        return ToolResult(success=False, output=None, error=str(exc))


def _add_discussion_comment_handler(args: Mapping[str, Any]) -> ToolResult:
    discussion_id = args.get("discussion_id")
    if not isinstance(discussion_id, str) or not discussion_id.strip():
        return ToolResult(success=False, output=None, error="discussion_id must be a non-empty string.")

    body = args.get("body")
    if not isinstance(body, str) or not body.strip():
        return ToolResult(success=False, output=None, error="body must be a non-empty string.")

    token_arg = args.get("token")
    try:
        token = github_discussions.resolve_token(str(token_arg) if token_arg else None)
    except github_discussions.GitHubDiscussionError as exc:
        return ToolResult(success=False, output=None, error=str(exc))

    try:
        comment = github_discussions.add_discussion_comment(
            token=token,
            discussion_id=discussion_id.strip(),
            body=body.strip(),
        )
        return ToolResult(
            success=True,
            output={
                "created": True,
                "id": comment.id,
                "url": comment.url,
            },
            error=None,
        )
    except github_discussions.GitHubDiscussionError as exc:
        return ToolResult(success=False, output=None, error=str(exc))


# =============================================================================
# Handler Implementations - Knowledge Graph Operations
# =============================================================================


def _get_aggregator() -> KnowledgeAggregator:
    """Get a knowledge aggregator instance."""
    return KnowledgeAggregator(KnowledgeGraphStorage())


def _list_knowledge_entities_handler(args: Mapping[str, Any]) -> ToolResult:
    entity_type = args.get("entity_type")

    try:
        aggregator = _get_aggregator()
        entities = aggregator.list_entities(
            entity_type=str(entity_type) if entity_type else None
        )
        return ToolResult(
            success=True,
            output={
                "count": len(entities),
                "entity_type": entity_type,
                "entities": entities,
            },
            error=None,
        )
    except Exception as exc:
        return ToolResult(success=False, output=None, error=str(exc))


def _get_entity_profile_handler(args: Mapping[str, Any]) -> ToolResult:
    name = args.get("name")
    if not isinstance(name, str) or not name.strip():
        return ToolResult(success=False, output=None, error="name must be a non-empty string.")

    entity_type = args.get("entity_type")

    try:
        aggregator = _get_aggregator()
        entity = aggregator.get_aggregated_entity(
            name=name.strip(),
            entity_type=str(entity_type) if entity_type else None,
        )
        if entity is None:
            return ToolResult(
                success=True,
                output={"found": False, "entity": None},
                error=None,
            )
        return ToolResult(
            success=True,
            output={
                "found": True,
                "entity": {
                    "name": entity.name,
                    "entity_type": entity.entity_type,
                    "average_confidence": entity.average_confidence,
                    "profile_count": len(entity.profiles),
                    "summary": entity.merged_summary,
                    "attributes": entity.merged_attributes,
                    "associations_as_source": len(entity.associations_as_source),
                    "associations_as_target": len(entity.associations_as_target),
                    "mention_count": len(entity.all_mentions),
                    "source_checksums": entity.source_checksums,
                },
            },
            error=None,
        )
    except Exception as exc:
        return ToolResult(success=False, output=None, error=str(exc))


def _build_entity_discussion_body_handler(args: Mapping[str, Any]) -> ToolResult:
    name = args.get("name")
    if not isinstance(name, str) or not name.strip():
        return ToolResult(success=False, output=None, error="name must be a non-empty string.")

    entity_type = args.get("entity_type")
    include_checksums = args.get("include_checksums", True)

    try:
        aggregator = _get_aggregator()
        entity = aggregator.get_aggregated_entity(
            name=name.strip(),
            entity_type=str(entity_type) if entity_type else None,
        )
        if entity is None:
            return ToolResult(
                success=False,
                output=None,
                error=f"Entity not found: {name}",
            )

        content = build_entity_discussion_content(
            entity,
            include_checksums=bool(include_checksums),
        )
        return ToolResult(
            success=True,
            output={
                "entity_name": entity.name,
                "entity_type": entity.entity_type,
                "body": content,
                "body_length": len(content),
            },
            error=None,
        )
    except Exception as exc:
        return ToolResult(success=False, output=None, error=str(exc))


# =============================================================================
# Handler Implementations - Composite Sync Operations
# =============================================================================


def _sync_entity_discussion_handler(args: Mapping[str, Any]) -> ToolResult:
    """
    Sync a knowledge graph entity to a GitHub Discussion.
    
    This composite operation:
    1. Fetches the entity from the knowledge graph
    2. Generates discussion content
    3. Finds or creates the appropriate category
    4. Finds existing discussion or creates a new one
    5. Updates if content changed
    6. Adds changelog comment on updates
    """
    entity_name = args.get("entity_name")
    if not isinstance(entity_name, str) or not entity_name.strip():
        return ToolResult(success=False, output=None, error="entity_name must be a non-empty string.")

    entity_type = args.get("entity_type")
    if not isinstance(entity_type, str) or entity_type not in ("Person", "Organization"):
        return ToolResult(success=False, output=None, error="entity_type must be 'Person' or 'Organization'.")

    creds = _resolve_credentials(args)
    if isinstance(creds, ToolResult):
        return creds
    repository, token = creds

    try:
        # Step 1: Get entity from knowledge graph
        aggregator = _get_aggregator()
        entity = aggregator.get_aggregated_entity(
            name=entity_name.strip(),
            entity_type=entity_type,
        )
        if entity is None:
            return ToolResult(
                success=False,
                output=None,
                error=f"Entity not found in knowledge graph: {entity_name}",
            )

        # Step 2: Generate discussion content
        new_body = build_entity_discussion_content(entity, include_checksums=True)

        # Step 3: Find or verify category exists
        # Map entity type to category name
        category_name = "People" if entity_type == "Person" else "Organizations"
        category = github_discussions.get_category_by_name(
            token=token,
            repository=repository,
            category_name=category_name,
        )
        if category is None:
            return ToolResult(
                success=False,
                output=None,
                error=f"Discussion category '{category_name}' not found. Please create it first.",
            )

        # Step 4: Find existing discussion or create new one
        existing = github_discussions.find_discussion_by_title(
            token=token,
            repository=repository,
            title=entity.name,
            category_id=category.id,
        )

        if existing is None:
            # Create new discussion
            discussion = github_discussions.create_discussion(
                token=token,
                repository=repository,
                category_id=category.id,
                title=entity.name,
                body=new_body,
            )
            return ToolResult(
                success=True,
                output={
                    "action": "created",
                    "entity_name": entity.name,
                    "entity_type": entity.entity_type,
                    "discussion_id": discussion.id,
                    "discussion_number": discussion.number,
                    "discussion_url": discussion.url,
                    "category": category_name,
                },
                error=None,
            )

        # Step 5: Check if content changed
        if existing.body.strip() == new_body.strip():
            return ToolResult(
                success=True,
                output={
                    "action": "unchanged",
                    "entity_name": entity.name,
                    "entity_type": entity.entity_type,
                    "discussion_id": existing.id,
                    "discussion_number": existing.number,
                    "discussion_url": existing.url,
                    "category": category_name,
                },
                error=None,
            )

        # Step 6: Update discussion and add changelog
        updated = github_discussions.update_discussion(
            token=token,
            discussion_id=existing.id,
            body=new_body,
        )

        # Add changelog comment
        changelog = build_changelog_comment(
            entity_name=entity.name,
            action="Updated",
            details=f"Synced from knowledge graph with {len(entity.profiles)} profile(s).",
        )
        github_discussions.add_discussion_comment(
            token=token,
            discussion_id=updated.id,
            body=changelog,
        )

        return ToolResult(
            success=True,
            output={
                "action": "updated",
                "entity_name": entity.name,
                "entity_type": entity.entity_type,
                "discussion_id": updated.id,
                "discussion_number": updated.number,
                "discussion_url": updated.url,
                "category": category_name,
            },
            error=None,
        )

    except github_discussions.GitHubDiscussionError as exc:
        return ToolResult(success=False, output=None, error=str(exc))
    except Exception as exc:
        return ToolResult(success=False, output=None, error=f"Sync failed: {exc}")


# =============================================================================
# Convenience Registration Function
# =============================================================================


def register_all_discussion_tools(registry: ToolRegistry) -> None:
    """Register all discussion-related tools with the registry."""
    register_discussion_read_tools(registry)
    register_discussion_mutation_tools(registry)
    register_knowledge_graph_tools(registry)
    register_discussion_sync_tools(registry)
