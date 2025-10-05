from src.workflow.workflow_state_manager import (
    TEMP_DISCOVERY_LABEL,
    WORKFLOW_LABEL_PREFIX,
    SPECIALIST_LABEL_PREFIX,
    WorkflowState,
    ensure_discovery_labels,
    get_state_from_labels,
    is_at_least_state,
    plan_state_transition,
)


def test_ensure_discovery_labels_adds_expected_state_and_temp_labels():
    plan = ensure_discovery_labels({"site-monitor", "automated"})

    assert TEMP_DISCOVERY_LABEL in plan.labels_to_add
    assert f"{WORKFLOW_LABEL_PREFIX}discovery" not in plan.final_labels  # sanity
    assert plan.final_labels == {
        "site-monitor",
        "automated",
        TEMP_DISCOVERY_LABEL,
        WorkflowState.DISCOVERY.label,
    }


def test_plan_state_transition_promotes_state_and_clears_temporary():
    current_labels = {
        TEMP_DISCOVERY_LABEL,
        WorkflowState.DISCOVERY.label,
        "site-monitor",
        f"{WORKFLOW_LABEL_PREFIX}legacy",
    }

    plan = plan_state_transition(
        current_labels,
        WorkflowState.ASSIGNED,
        ensure_labels=["osint"],
        specialist_labels=["intelligence-analyst"],
        clear_temporary=True,
    )

    expected_workflow_label = f"{WORKFLOW_LABEL_PREFIX}osint"
    expected_specialist_label = f"{SPECIALIST_LABEL_PREFIX}intelligence-analyst"

    assert WorkflowState.DISCOVERY.label in plan.labels_to_remove
    assert WorkflowState.ASSIGNED.label in plan.labels_to_add
    assert TEMP_DISCOVERY_LABEL in plan.labels_to_remove
    assert expected_workflow_label in plan.labels_to_add
    assert expected_specialist_label in plan.labels_to_add
    assert expected_workflow_label in plan.final_labels
    assert expected_specialist_label in plan.final_labels
    assert TEMP_DISCOVERY_LABEL not in plan.final_labels


def test_state_helpers_detect_current_state_and_ordering():
    labels = {"site-monitor", WorkflowState.COPILOT_ASSIGNED.label}

    assert get_state_from_labels(labels) == WorkflowState.COPILOT_ASSIGNED
    assert is_at_least_state(labels, WorkflowState.ASSIGNED)
    assert not is_at_least_state(labels, WorkflowState.COMPLETED)
