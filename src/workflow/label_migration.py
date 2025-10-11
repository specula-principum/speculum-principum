"""Legacy label translation has been retired.

This module remains as a compatibility shim for any lingering imports, but it no
longer mutates labels. Once downstream callers have been updated the module can
be removed entirely.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Iterable, Mapping


@dataclass(frozen=True)
class LegacyTranslationResult:
    """Result object returned by the compatibility shim."""

    augmented_labels: FrozenSet[str]
    added_labels: FrozenSet[str]
    mapping: Mapping[str, FrozenSet[str]]


class WorkflowLabelTranslator:  # pragma: no cover - compatibility shim
    """Compatibility shim preserved for older imports."""

    @classmethod
    def translate(cls, labels: Iterable[str]) -> LegacyTranslationResult:
        """Return the labels unchanged now that legacy translation is removed."""

        normalized = tuple(label for label in labels if isinstance(label, str))
        return LegacyTranslationResult(
            augmented_labels=frozenset(normalized),
            added_labels=frozenset(),
            mapping={},
        )