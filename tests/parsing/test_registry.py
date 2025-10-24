"""Tests for the parser registry selection logic."""

from __future__ import annotations

import pytest

from src.parsing.base import ParseTarget, ParserError
from src.parsing.registry import ParserRegistry


class DummyParser:
    def __init__(self, name: str, detector):
        self._name = name
        self._detector = detector

    @property
    def name(self) -> str:
        return self._name

    def detect(self, target: ParseTarget) -> bool:
        return bool(self._detector(target))

    def extract(self, target: ParseTarget):  # pragma: no cover - unused in tests
        raise NotImplementedError

    def to_markdown(self, document):  # pragma: no cover - unused in tests
        raise NotImplementedError


def test_selects_parser_by_suffix() -> None:
    registry = ParserRegistry()
    pdf_parser = DummyParser("pdf", lambda _t: True)
    registry.register_parser(pdf_parser, suffixes=[".pdf"])

    target = ParseTarget(source="report.pdf")

    assert registry.require_parser(target) is pdf_parser


def test_prefers_highest_priority_match() -> None:
    registry = ParserRegistry()
    low_priority = DummyParser("low", lambda _t: True)
    high_priority = DummyParser("high", lambda _t: True)
    registry.register_parser(low_priority, suffixes=[".txt"], priority=1)
    registry.register_parser(high_priority, suffixes=[".txt"], priority=5)

    target = ParseTarget(source="notes.txt")

    assert registry.require_parser(target) is high_priority


def test_fallback_detection_checks_other_parsers() -> None:
    registry = ParserRegistry()
    no_match = DummyParser("first", lambda _t: False)
    fallback = DummyParser("second", lambda _t: True)
    registry.register_parser(no_match, suffixes=[".bin"])
    registry.register_parser(fallback)

    target = ParseTarget(source="data.unknown")

    assert registry.require_parser(target) is fallback


def test_matches_by_media_type() -> None:
    registry = ParserRegistry()
    media_parser = DummyParser("media", lambda _t: True)
    registry.register_parser(media_parser, media_types=["application/pdf"])

    target = ParseTarget(source="ignored", media_type="application/pdf")

    assert registry.require_parser(target) is media_parser


def test_require_parser_raises_when_unmatched() -> None:
    registry = ParserRegistry()
    target = ParseTarget(source="empty.txt")

    with pytest.raises(ParserError):
        registry.require_parser(target)
