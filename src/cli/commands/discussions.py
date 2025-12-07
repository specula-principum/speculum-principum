"""CLI commands for discussion synchronization operations."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from src import paths
from src.integrations.github import discussions as github_discussions
from src.knowledge.aggregation import KnowledgeAggregator, build_entity_discussion_content
from src.knowledge.storage import KnowledgeGraphStorage

if TYPE_CHECKING:
    from src.knowledge.aggregation import AggregatedEntity


def register_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register discussion CLI commands.

    Args:
        subparsers: Subparser action from main argument parser
    """
    # sync-discussions command
    parser = subparsers.add_parser(
        "sync-discussions",
        help="Sync knowledge graph entities to GitHub Discussions",
    )
    parser.add_argument(
        "--entity-type",
        choices=["Person", "Organization", "all"],
        default="all",
        help="Type of entities to sync (default: all)",
    )
    parser.add_argument(
        "--entity-name",
        help="Sync only a specific entity by name",
    )
    parser.add_argument(
        "--knowledge-graph",
        default=paths.get_knowledge_graph_root(),
        help="Path to knowledge graph directory (default: knowledge-graph/)",
    )
    parser.add_argument(
        "--repository",
        help="GitHub repository (owner/repo). Uses GH_REPOSITORY or GITHUB_REPOSITORY env var if not set.",
    )
    parser.add_argument(
        "--token",
        help="GitHub token. Uses GH_TOKEN or GITHUB_TOKEN env var if not set.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be synced without making changes",
    )
    parser.add_argument(
        "--output",
        help="Write sync report to file (JSON)",
    )
    parser.set_defaults(func=sync_discussions_cli)

    # list-entities command (utility)
    list_parser = subparsers.add_parser(
        "list-entities",
        help="List all entities in the knowledge graph",
    )
    list_parser.add_argument(
        "--entity-type",
        choices=["Person", "Organization", "all"],
        default="all",
        help="Type of entities to list (default: all)",
    )
    list_parser.add_argument(
        "--knowledge-graph",
        default="knowledge-graph",
        help="Path to knowledge graph directory (default: knowledge-graph/)",
    )
    list_parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )
    list_parser.set_defaults(func=list_entities_cli)


def _resolve_entity_types(entity_type_arg: str) -> list[str]:
    """Convert entity-type argument to list of types."""
    if entity_type_arg == "all":
        return ["Person", "Organization"]
    return [entity_type_arg]


def _get_aggregator(knowledge_graph_path: str) -> KnowledgeAggregator:
    """Create a KnowledgeAggregator for the given path."""
    storage = KnowledgeGraphStorage(root=Path(knowledge_graph_path))
    return KnowledgeAggregator(storage=storage)


def _ensure_category_exists(
    category_name: str,
    token: str,
    repository: str,
) -> str | None:
    """Ensure a discussion category exists, return its ID or None on error."""
    category = github_discussions.get_category_by_name(
        token=token,
        repository=repository,
        category_name=category_name,
    )
    if category:
        return category.id
    # Category doesn't exist - would need admin to create
    return None


def _sync_single_entity(
    entity: "AggregatedEntity",
    category_id: str,
    token: str,
    repository: str,
    dry_run: bool,
) -> dict:
    """Sync a single entity to GitHub Discussions.
    
    Returns a dict with sync result details.
    """
    entity_name = entity.name
    entity_type = entity.entity_type
    
    # Build discussion content
    body = build_entity_discussion_content(entity)
    
    # Check if discussion exists
    existing = github_discussions.find_discussion_by_title(
        token=token,
        repository=repository,
        title=entity_name,
        category_id=category_id,
    )
    
    if existing is None:
        # Create new discussion
        if dry_run:
            return {
                "entity": entity_name,
                "type": entity_type,
                "action": "would_create",
                "discussion_number": None,
            }
        
        discussion = github_discussions.create_discussion(
            token=token,
            repository=repository,
            category_id=category_id,
            title=entity_name,
            body=body,
        )
        return {
            "entity": entity_name,
            "type": entity_type,
            "action": "created",
            "discussion_number": discussion.number,
            "url": discussion.url,
        }
    
    # Discussion exists - check if update needed
    if existing.body.strip() == body.strip():
        return {
            "entity": entity_name,
            "type": entity_type,
            "action": "unchanged",
            "discussion_number": existing.number,
            "url": existing.url,
        }
    
    # Update needed
    if dry_run:
        return {
            "entity": entity_name,
            "type": entity_type,
            "action": "would_update",
            "discussion_number": existing.number,
            "url": existing.url,
        }
    
    github_discussions.update_discussion(
        token=token,
        discussion_id=existing.id,
        body=body,
    )
    
    # Add changelog comment
    changelog = f"**Updated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\nDiscussion body updated to reflect current knowledge graph state."
    github_discussions.add_discussion_comment(
        token=token,
        discussion_id=existing.id,
        body=changelog,
    )
    
    return {
        "entity": entity_name,
        "type": entity_type,
        "action": "updated",
        "discussion_number": existing.number,
        "url": existing.url,
    }


def sync_discussions_cli(args: argparse.Namespace) -> int:
    """Sync knowledge graph entities to GitHub Discussions.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Resolve credentials
    try:
        repository = github_discussions.resolve_repository(args.repository)
        token = github_discussions.resolve_token(args.token)
    except github_discussions.GitHubDiscussionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    
    knowledge_graph_path = args.knowledge_graph
    entity_types = _resolve_entity_types(args.entity_type)
    specific_entity = args.entity_name
    dry_run = args.dry_run
    
    if dry_run:
        print("DRY RUN - No changes will be made\n")
    
    print(f"Repository: {repository}")
    print(f"Knowledge Graph: {knowledge_graph_path}")
    print(f"Entity Types: {', '.join(entity_types)}")
    if specific_entity:
        print(f"Specific Entity: {specific_entity}")
    print()
    
    # Initialize aggregator
    aggregator = _get_aggregator(knowledge_graph_path)
    
    # Track results
    results: list[dict] = []
    errors: list[dict] = []
    
    # Process each entity type
    for entity_type in entity_types:
        category_name = "People" if entity_type == "Person" else "Organizations"
        print(f"Processing {entity_type}s (category: {category_name})...")
        
        # Ensure category exists
        category_id = _ensure_category_exists(category_name, token, repository)
        if category_id is None:
            error_msg = f"Category '{category_name}' not found. Please create it manually in repository settings."
            print(f"  error: {error_msg}", file=sys.stderr)
            errors.append({"entity_type": entity_type, "error": error_msg})
            continue
        
        # Get entities
        entities = aggregator.list_entities(entity_type=entity_type)
        
        if specific_entity:
            entities = [e for e in entities if e == specific_entity]
            if not entities:
                print(f"  Entity '{specific_entity}' not found in knowledge graph")
                continue
        
        print(f"  Found {len(entities)} {entity_type.lower()}(s)")
        
        for entity_name in entities:
            entity = aggregator.get_aggregated_entity(entity_name, entity_type)
            if entity is None:
                errors.append({
                    "entity": entity_name,
                    "type": entity_type,
                    "error": "Failed to aggregate entity data",
                })
                continue
            
            try:
                result = _sync_single_entity(
                    entity=entity,
                    category_id=category_id,
                    token=token,
                    repository=repository,
                    dry_run=dry_run,
                )
                results.append(result)
                
                action = result["action"]
                if action == "created":
                    print(f"    ✓ Created: {entity_name} (#{result['discussion_number']})")
                elif action == "updated":
                    print(f"    ✓ Updated: {entity_name} (#{result['discussion_number']})")
                elif action == "unchanged":
                    print(f"    - Unchanged: {entity_name}")
                elif action == "would_create":
                    print(f"    [dry-run] Would create: {entity_name}")
                elif action == "would_update":
                    print(f"    [dry-run] Would update: {entity_name}")
                    
            except github_discussions.GitHubDiscussionError as exc:
                errors.append({
                    "entity": entity_name,
                    "type": entity_type,
                    "error": str(exc),
                })
                print(f"    ✗ Error: {entity_name} - {exc}")
    
    # Summary
    print()
    print("=" * 60)
    print("Sync Summary")
    print("=" * 60)
    
    created = len([r for r in results if r["action"] == "created"])
    updated = len([r for r in results if r["action"] == "updated"])
    unchanged = len([r for r in results if r["action"] == "unchanged"])
    would_create = len([r for r in results if r["action"] == "would_create"])
    would_update = len([r for r in results if r["action"] == "would_update"])
    
    if dry_run:
        print(f"  Would create: {would_create}")
        print(f"  Would update: {would_update}")
        print(f"  Unchanged: {unchanged}")
    else:
        print(f"  Created: {created}")
        print(f"  Updated: {updated}")
        print(f"  Unchanged: {unchanged}")
    
    if errors:
        print(f"  Errors: {len(errors)}")
    
    # Write report if requested
    if args.output:
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "repository": repository,
            "knowledge_graph": knowledge_graph_path,
            "entity_types": entity_types,
            "dry_run": dry_run,
            "results": results,
            "errors": errors,
            "summary": {
                "created": created,
                "updated": updated,
                "unchanged": unchanged,
                "would_create": would_create,
                "would_update": would_update,
                "error_count": len(errors),
            },
        }
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\nReport written to: {output_path}")
    
    return 1 if errors else 0


def list_entities_cli(args: argparse.Namespace) -> int:
    """List all entities in the knowledge graph.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 for success)
    """
    knowledge_graph_path = args.knowledge_graph
    entity_types = _resolve_entity_types(args.entity_type)
    output_format = args.format
    
    aggregator = _get_aggregator(knowledge_graph_path)
    
    all_entities: list[dict] = []
    
    for entity_type in entity_types:
        entities = aggregator.list_entities(entity_type=entity_type)
        for entity_name in entities:
            entity = aggregator.get_aggregated_entity(entity_name, entity_type)
            if entity:
                source_count = len(entity.source_checksums)
                assoc_count = len(entity.associations_as_source) + len(entity.associations_as_target)
                all_entities.append({
                    "name": entity_name,
                    "type": entity_type,
                    "source_count": source_count,
                    "association_count": assoc_count,
                })
    
    if output_format == "json":
        print(json.dumps(all_entities, indent=2))
    else:
        # Table format
        if not all_entities:
            print("No entities found in knowledge graph")
            return 0
        
        print(f"Found {len(all_entities)} entities:\n")
        print(f"{'Name':<40} {'Type':<15} {'Sources':<10} {'Associations':<12}")
        print("-" * 77)
        
        for entity in sorted(all_entities, key=lambda e: (e["type"], e["name"])):
            name = entity["name"][:38] + ".." if len(entity["name"]) > 40 else entity["name"]
            print(f"{name:<40} {entity['type']:<15} {entity['source_count']:<10} {entity['association_count']:<12}")
    
    return 0
