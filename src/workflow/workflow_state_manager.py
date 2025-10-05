"""Utility helpers for workflow label and state transitions.

Centralizes the label semantics defined in the workflow refactor so that
site monitoring, AI workflow assignment, and issue processing apply the
same rules when advancing issues through the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterable, Optional, Set

# Label families
WORKFLOW_LABEL_PREFIX = "workflow::"
SPECIALIST_LABEL_PREFIX = "specialist::"
STATE_LABEL_PREFIX = "state::"
TEMP_DISCOVERY_LABEL = "monitor::triage"


class WorkflowState(Enum):
    """Enumerated workflow states tracked via labels."""

    DISCOVERY = auto()
    ASSIGNED = auto()
    COPILOT_ASSIGNED = auto()
    COMPLETED = auto()

    @property
    def label(self) -> str:
        return _STATE_LABEL_MAP[self]


_STATE_ORDER = {
    WorkflowState.DISCOVERY: 0,
    WorkflowState.ASSIGNED: 1,
    WorkflowState.COPILOT_ASSIGNED: 2,
    WorkflowState.COMPLETED: 3,
}

_STATE_LABEL_MAP = {
    WorkflowState.DISCOVERY: f"{STATE_LABEL_PREFIX}discovery",
    WorkflowState.ASSIGNED: f"{STATE_LABEL_PREFIX}assigned",
    WorkflowState.COPILOT_ASSIGNED: f"{STATE_LABEL_PREFIX}copilot",
    WorkflowState.COMPLETED: f"{STATE_LABEL_PREFIX}done",
}

_ALL_STATE_LABELS: Set[str] = set(_STATE_LABEL_MAP.values())
_TEMPORARY_LABELS: Set[str] = {TEMP_DISCOVERY_LABEL}


@dataclass(frozen=True)
class TransitionPlan:
    """Computed label changes for a transition."""

    final_labels: Set[str]
    labels_to_add: Set[str]
    labels_to_remove: Set[str]


def normalise_label(label: str, *, prefix: Optional[str] = None) -> str:
    """Ensure labels follow the expected prefix convention."""

    if prefix and not label.startswith(prefix):
        return f"{prefix}{label}".lower()
    return label.lower()


def plan_state_transition(
    current_labels: Iterable[str],
    target_state: WorkflowState,
    *,
    ensure_labels: Optional[Iterable[str]] = None,
    specialist_labels: Optional[Iterable[str]] = None,
    clear_temporary: bool = False,
) -> TransitionPlan:
    """Return the labels to add/remove when moving to ``target_state``.

    Args:
        current_labels: Labels currently on the issue.
        target_state: Desired workflow state.
        ensure_labels: Workflow labels that should be present (auto-prefixed).
        specialist_labels: Specialist labels that should be present (auto-prefixed).
        clear_temporary: Remove temporary discovery labels when advancing.

    Returns:
        ``TransitionPlan`` with final label set, additions, and removals.
    """

    current = {label.lower() for label in current_labels}
    labels_to_add: Set[str] = set()
    labels_to_remove: Set[str] = set()

    # Handle state labels (only one allowed)
    desired_state_label = target_state.label
    for label in current & _ALL_STATE_LABELS:
        if label != desired_state_label:
            labels_to_remove.add(label)
    if desired_state_label not in current:
        labels_to_add.add(desired_state_label)

    # Ensure workflow labels
    if ensure_labels:
        for raw_label in ensure_labels:
            normalised = normalise_label(raw_label, prefix=WORKFLOW_LABEL_PREFIX)
            if normalised not in current:
                labels_to_add.add(normalised)

    # Ensure specialist labels
    if specialist_labels:
        for raw_label in specialist_labels:
            normalised = normalise_label(raw_label, prefix=SPECIALIST_LABEL_PREFIX)
            if normalised not in current:
                labels_to_add.add(normalised)

    # Remove temporary discovery labels when instructed
    if clear_temporary:
        labels_to_remove.update(current & _TEMPORARY_LABELS)

    final_labels = (current - labels_to_remove) | labels_to_add
    return TransitionPlan(final_labels=final_labels, labels_to_add=labels_to_add, labels_to_remove=labels_to_remove)


def is_at_least_state(labels: Iterable[str], state: WorkflowState) -> bool:
    """Return ``True`` if labels indicate a state >= the provided state."""

    current_state = get_state_from_labels(labels)
    if current_state is None:
        return False
    return _STATE_ORDER[current_state] >= _STATE_ORDER[state]


def get_state_from_labels(labels: Iterable[str]) -> Optional[WorkflowState]:
    """Derive the current workflow state from label set."""

    lower_labels = {label.lower() for label in labels}
    for state, label in _STATE_LABEL_MAP.items():
        if label in lower_labels:
            return state
    return None


def ensure_discovery_labels(labels: Iterable[str]) -> TransitionPlan:
    """Ensure discovery state + temporary labels exist for new issues."""

    current = {label.lower() for label in labels}
    labels_to_add: Set[str] = set()
    if TEMP_DISCOVERY_LABEL not in current:
        labels_to_add.add(TEMP_DISCOVERY_LABEL)

    desired_state = WorkflowState.DISCOVERY.label
    if desired_state not in current:
        labels_to_add.add(desired_state)

    final_labels = current | labels_to_add
    return TransitionPlan(final_labels=final_labels, labels_to_add=labels_to_add, labels_to_remove=set())


__all__ = [
    "WorkflowState",
    "WORKFLOW_LABEL_PREFIX",
    "SPECIALIST_LABEL_PREFIX",
    "STATE_LABEL_PREFIX",
    "TEMP_DISCOVERY_LABEL",
    "TransitionPlan",
    "plan_state_transition",
    "ensure_discovery_labels",
    "is_at_least_state",
    "get_state_from_labels",
]
