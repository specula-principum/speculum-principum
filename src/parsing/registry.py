"""Parser registry for routing targets to concrete implementations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import urlparse

from . import utils
from .base import DocumentParser, ParseTarget, ParserError


@dataclass(slots=True)
class _RegistryEntry:
    parser: DocumentParser
    media_types: tuple[str, ...]
    suffixes: tuple[str, ...]
    priority: int

    def matches(self, media_type: str | None, suffix: str | None) -> bool:
        if self.media_types:
            if media_type is None or media_type not in self.media_types:
                return False
        if self.suffixes:
            if suffix is None or suffix not in self.suffixes:
                return False
        return True


class ParserRegistry:
    """Manage parser implementations and select appropriate handlers."""

    def __init__(self) -> None:
        self._entries: list[_RegistryEntry] = []

    def register_parser(
        self,
        parser: DocumentParser,
        *,
        media_types: Sequence[str] | None = None,
        suffixes: Sequence[str] | None = None,
        priority: int = 0,
        replace: bool = False,
    ) -> None:
        if not parser.name:
            raise ValueError("Parser must define a non-empty name")

        media_spec = _normalize_media_types(media_types)
        suffix_spec = utils.normalize_suffixes(
            suffixes,
            sort=True,
            preserve_order=False,
        )

        if not replace and any(entry.parser.name == parser.name for entry in self._entries):
            raise ValueError(f"Parser '{parser.name}' already registered")

        self._entries = [entry for entry in self._entries if entry.parser.name != parser.name]
        self._entries.append(
            _RegistryEntry(
                parser=parser,
                media_types=media_spec,
                suffixes=suffix_spec,
                priority=priority,
            )
        )
        self._entries.sort(key=lambda entry: entry.priority, reverse=True)

    def unregister(self, name: str) -> None:
        self._entries = [entry for entry in self._entries if entry.parser.name != name]

    def get_registered_names(self) -> list[str]:
        return [entry.parser.name for entry in self._entries]

    def find_parser(self, target: ParseTarget) -> DocumentParser | None:
        media_type = self._resolve_media_type(target)
        suffix = self._resolve_suffix(target)

        prioritized = [
            entry for entry in self._entries if entry.matches(media_type, suffix)
        ]
        fallback = [
            entry for entry in self._entries if entry not in prioritized
        ]

        for entry in prioritized + fallback:
            parser = entry.parser
            if parser.detect(target):
                return parser

        return None

    def require_parser(self, target: ParseTarget) -> DocumentParser:
        parser = self.find_parser(target)
        if parser is None:
            raise ParserError(f"No parser registered for target '{target.source}'")
        return parser

    def __iter__(self) -> Iterable[DocumentParser]:
        for entry in self._entries:
            yield entry.parser

    @staticmethod
    def _resolve_media_type(target: ParseTarget) -> str | None:
        if target.media_type:
            return target.media_type.lower()
        if target.is_remote:
            return None
        try:
            path = target.to_path()
        except ValueError:
            return None
        media_type = utils.guess_media_type(path)
        return media_type.lower() if media_type else None

    @staticmethod
    def _resolve_suffix(target: ParseTarget) -> str | None:
        if target.is_remote:
            parsed = urlparse(target.source)
            candidate = Path(parsed.path)
        else:
            try:
                candidate = target.to_path()
            except ValueError:
                candidate = Path(target.source)
        suffix = candidate.suffix
        return suffix.lower() if suffix else None


def _normalize_media_types(values: Sequence[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    normalized = {item.lower() for item in values if item}
    return tuple(sorted(normalized))


registry = ParserRegistry()
"""Default global parser registry."""