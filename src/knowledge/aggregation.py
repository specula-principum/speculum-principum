"""Knowledge graph aggregation utilities for discussion content generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, List

from src.knowledge.storage import (
    EntityAssociation,
    EntityProfile,
    KnowledgeGraphStorage,
)


@dataclass
class AggregatedEntity:
    """Represents an entity aggregated from multiple source documents."""

    name: str
    entity_type: str
    profiles: List[EntityProfile] = field(default_factory=list)
    associations_as_source: List[EntityAssociation] = field(default_factory=list)
    associations_as_target: List[EntityAssociation] = field(default_factory=list)
    source_checksums: List[str] = field(default_factory=list)

    @property
    def average_confidence(self) -> float:
        """Calculate the average confidence across all profiles."""
        if not self.profiles:
            return 0.0
        return sum(p.confidence for p in self.profiles) / len(self.profiles)

    @property
    def merged_summary(self) -> str:
        """Create a merged summary from all profiles."""
        if not self.profiles:
            return ""
        # Use the profile with highest confidence as primary
        primary = max(self.profiles, key=lambda p: p.confidence)
        return primary.summary

    @property
    def merged_attributes(self) -> dict[str, Any]:
        """Merge attributes from all profiles, preferring higher confidence sources."""
        if not self.profiles:
            return {}
        # Sort by confidence descending
        sorted_profiles = sorted(self.profiles, key=lambda p: p.confidence, reverse=True)
        merged: dict[str, Any] = {}
        for profile in reversed(sorted_profiles):  # Lower confidence first, then override
            merged.update(profile.attributes)
        return merged

    @property
    def all_mentions(self) -> List[str]:
        """Collect all unique mentions across profiles."""
        seen: set[str] = set()
        mentions: List[str] = []
        for profile in self.profiles:
            for mention in profile.mentions:
                if mention not in seen:
                    seen.add(mention)
                    mentions.append(mention)
        return mentions


class KnowledgeAggregator:
    """Aggregates knowledge graph data across multiple source documents."""

    def __init__(self, storage: KnowledgeGraphStorage | None = None) -> None:
        self.storage = storage or KnowledgeGraphStorage()

    def list_all_checksums(self) -> List[str]:
        """Enumerate all source document checksums in the knowledge graph."""
        checksums: set[str] = set()

        # Check all entity type directories
        for directory in [
            self.storage._profiles_dir,
            self.storage._people_dir,
            self.storage._organizations_dir,
            self.storage._concepts_dir,
            self.storage._associations_dir,
        ]:
            if directory.exists():
                for path in directory.glob("*.json"):
                    # Extract checksum from filename
                    checksums.add(path.stem)

        return sorted(checksums)

    def get_all_profiles(self) -> List[EntityProfile]:
        """Aggregate all profiles across all source documents."""
        profiles: List[EntityProfile] = []
        for checksum in self.list_all_checksums():
            extracted = self.storage.get_extracted_profiles(checksum)
            if extracted:
                profiles.extend(extracted.profiles)
        return profiles

    def get_all_associations(self) -> List[EntityAssociation]:
        """Aggregate all associations across all source documents."""
        associations: List[EntityAssociation] = []
        for checksum in self.list_all_checksums():
            extracted = self.storage.get_extracted_associations(checksum)
            if extracted:
                associations.extend(extracted.associations)
        return associations

    def list_entities(self, entity_type: str | None = None) -> List[str]:
        """List all unique entity names, optionally filtered by type.
        
        Args:
            entity_type: Filter by entity type (Person, Organization, Concept).
                         If None, returns all entity types.
        
        Returns:
            List of unique entity names.
        """
        profiles = self.get_all_profiles()
        seen: set[str] = set()
        entities: List[str] = []

        for profile in profiles:
            if entity_type and profile.entity_type.lower() != entity_type.lower():
                continue
            name_lower = profile.name.lower()
            if name_lower not in seen:
                seen.add(name_lower)
                # Use the original casing from the first occurrence
                entities.append(profile.name)

        return sorted(entities)

    def get_profiles_by_entity(
        self,
        name: str,
        entity_type: str | None = None,
    ) -> List[EntityProfile]:
        """Find all profiles for a given entity name.
        
        Args:
            name: The entity name to search for (case-insensitive).
            entity_type: Optional filter by entity type.
        
        Returns:
            List of matching profiles from all source documents.
        """
        all_profiles = self.get_all_profiles()
        name_lower = name.lower()
        matches: List[EntityProfile] = []

        for profile in all_profiles:
            if profile.name.lower() != name_lower:
                continue
            if entity_type and profile.entity_type.lower() != entity_type.lower():
                continue
            matches.append(profile)

        return matches

    def get_associations_for_entity(self, name: str) -> tuple[List[EntityAssociation], List[EntityAssociation]]:
        """Find all associations where the entity is source or target.
        
        Args:
            name: The entity name to search for (case-insensitive).
        
        Returns:
            Tuple of (associations_as_source, associations_as_target).
        """
        all_associations = self.get_all_associations()
        name_lower = name.lower()

        as_source: List[EntityAssociation] = []
        as_target: List[EntityAssociation] = []

        for assoc in all_associations:
            if assoc.source.lower() == name_lower:
                as_source.append(assoc)
            if assoc.target.lower() == name_lower:
                as_target.append(assoc)

        return as_source, as_target

    def get_aggregated_entity(
        self,
        name: str,
        entity_type: str | None = None,
    ) -> AggregatedEntity | None:
        """Get a fully aggregated view of an entity across all sources.
        
        Args:
            name: The entity name to aggregate.
            entity_type: Optional filter by entity type.
        
        Returns:
            AggregatedEntity with all profiles and associations, or None if not found.
        """
        profiles = self.get_profiles_by_entity(name, entity_type)
        if not profiles:
            return None

        # Determine the entity type from profiles
        resolved_type = profiles[0].entity_type
        if entity_type:
            resolved_type = entity_type

        as_source, as_target = self.get_associations_for_entity(name)

        # Find source checksums
        checksums: set[str] = set()
        for checksum in self.list_all_checksums():
            extracted = self.storage.get_extracted_profiles(checksum)
            if extracted:
                for profile in extracted.profiles:
                    if profile.name.lower() == name.lower():
                        checksums.add(checksum)

        return AggregatedEntity(
            name=profiles[0].name,  # Use original casing
            entity_type=resolved_type,
            profiles=profiles,
            associations_as_source=as_source,
            associations_as_target=as_target,
            source_checksums=sorted(checksums),
        )


# =============================================================================
# Markdown Content Generation
# =============================================================================


def _format_attributes_table(attributes: dict[str, Any]) -> str:
    """Format entity attributes as a markdown table."""
    if not attributes:
        return "_No attributes available._"

    lines = ["| Attribute | Value |", "|-----------|-------|"]
    for key, value in sorted(attributes.items()):
        # Format complex values
        if isinstance(value, list):
            value_str = ", ".join(str(v) for v in value)
        elif isinstance(value, dict):
            value_str = ", ".join(f"{k}: {v}" for k, v in value.items())
        else:
            value_str = str(value)
        # Escape pipe characters
        value_str = value_str.replace("|", "\\|")
        lines.append(f"| {key} | {value_str} |")

    return "\n".join(lines)


def _format_associations_list(
    associations: List[EntityAssociation],
    direction: str,
) -> str:
    """Format associations as a markdown list."""
    if not associations:
        return "_No associations found._"

    lines = []
    for assoc in associations:
        if direction == "outgoing":
            target = assoc.target
            relationship = assoc.relationship
            line = f"- **{relationship}** → {target}"
        else:
            source = assoc.source
            relationship = assoc.relationship
            line = f"- {source} → **{relationship}**"

        if assoc.evidence:
            # Truncate long evidence
            evidence = assoc.evidence
            if len(evidence) > 200:
                evidence = evidence[:197] + "..."
            line += f"\n  - _Evidence:_ {evidence}"

        if assoc.confidence < 1.0:
            line += f"\n  - _Confidence:_ {assoc.confidence:.0%}"

        lines.append(line)

    return "\n".join(lines)


def _format_mentions_list(mentions: List[str], max_items: int = 5) -> str:
    """Format source mentions as a markdown list."""
    if not mentions:
        return "_No source mentions._"

    lines = []
    for i, mention in enumerate(mentions[:max_items]):
        # Clean up mention text
        mention_clean = mention.strip()
        if len(mention_clean) > 300:
            mention_clean = mention_clean[:297] + "..."
        lines.append(f"> {mention_clean}")

    if len(mentions) > max_items:
        lines.append(f"\n_...and {len(mentions) - max_items} more mentions._")

    return "\n".join(lines)


def build_entity_discussion_content(
    entity: AggregatedEntity,
    include_checksums: bool = True,
) -> str:
    """Generate markdown content for a discussion body.
    
    Args:
        entity: The aggregated entity to format.
        include_checksums: Whether to include source checksum references.
    
    Returns:
        Markdown-formatted discussion body.
    """
    sections: List[str] = []

    # Header
    sections.append(f"# {entity.name}")
    sections.append("")
    sections.append(f"**Type:** {entity.entity_type}")
    sections.append(f"**Confidence:** {entity.average_confidence:.0%}")
    sections.append("")

    # Summary
    sections.append("## Summary")
    sections.append("")
    if entity.merged_summary:
        sections.append(entity.merged_summary)
    else:
        sections.append("_No summary available._")
    sections.append("")

    # Attributes
    sections.append("## Attributes")
    sections.append("")
    sections.append(_format_attributes_table(entity.merged_attributes))
    sections.append("")

    # Associations
    if entity.associations_as_source or entity.associations_as_target:
        sections.append("## Associations")
        sections.append("")

        if entity.associations_as_source:
            sections.append("### Outgoing Relationships")
            sections.append("")
            sections.append(_format_associations_list(entity.associations_as_source, "outgoing"))
            sections.append("")

        if entity.associations_as_target:
            sections.append("### Incoming Relationships")
            sections.append("")
            sections.append(_format_associations_list(entity.associations_as_target, "incoming"))
            sections.append("")

    # Source Mentions
    sections.append("## Source Mentions")
    sections.append("")
    sections.append(_format_mentions_list(entity.all_mentions))
    sections.append("")

    # Source Documents
    if include_checksums and entity.source_checksums:
        sections.append("## Source Documents")
        sections.append("")
        for checksum in entity.source_checksums:
            short_checksum = checksum[:12]
            sections.append(f"- `{short_checksum}...`")
        sections.append("")

    # Footer
    sections.append("---")
    sections.append(f"_Generated from knowledge graph on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_")

    return "\n".join(sections)


def build_changelog_comment(
    entity_name: str,
    action: str,
    details: str | None = None,
) -> str:
    """Generate a changelog comment for discussion updates.
    
    Args:
        entity_name: The entity being updated.
        action: The action performed (e.g., "Created", "Updated").
        details: Optional additional details.
    
    Returns:
        Markdown-formatted changelog comment.
    """
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"**{action}:** {timestamp}"]

    if details:
        lines.append("")
        lines.append(details)

    return "\n".join(lines)
