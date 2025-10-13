from src.workflow.deliverable_namer import MultiWorkflowDeliverableNamer
from src.workflow.workflow_matcher import WorkflowInfo, WorkflowCandidate, WorkflowPlan


def _workflow_info(name: str, deliverable_names):
    return WorkflowInfo(
        path=f"/tmp/{name.lower().replace(' ', '_')}.yaml",
        name=name,
        description=f"Workflow {name}",
        version="1.0.0",
        trigger_labels=[f"label::{name.lower()}"],
        deliverables=[{"name": deliverable} for deliverable in deliverable_names],
        processing={},
        validation={},
        output={
            "folder_structure": "issue_{issue_number}",
            "file_pattern": "{deliverable_name}.md",
        },
    )


def _candidate(workflow_info, priority=1):
    return WorkflowCandidate(
        workflow_info=workflow_info,
        priority=priority,
        conflict_keys=frozenset(),
        dependencies=(),
    )


def _plan(candidates):
    return WorkflowPlan(
        issue_labels=("site-monitor",),
        candidates=tuple(candidates),
        selection_reason="test",
        selection_message="test-plan",
    )


def test_manifest_single_workflow_preserves_filenames():
    workflow = _workflow_info("Primary", ["Summary", "Findings"])
    plan = _plan([_candidate(workflow)])

    namer = MultiWorkflowDeliverableNamer()
    manifest = namer.build_manifest(issue_number=101, issue_title="Sample Issue", plan=plan)

    assert manifest["workflow_count"] == 1
    deliverables = manifest["workflows"][0]["deliverables"]
    filenames = {entry["final_filename"] for entry in deliverables}
    assert filenames == {"summary.md", "findings.md"}
    assert manifest["conflict_groups"] == []


def test_manifest_suffixes_conflicting_deliverables():
    primary = _workflow_info("Primary", ["Summary"])
    secondary = _workflow_info("Secondary", ["Summary"])
    plan = _plan([_candidate(primary, priority=1), _candidate(secondary, priority=2)])

    namer = MultiWorkflowDeliverableNamer()
    manifest = namer.build_manifest(issue_number=42, issue_title="Policy Update", plan=plan)

    primary_entry = manifest["workflows"][0]["deliverables"][0]
    secondary_entry = manifest["workflows"][1]["deliverables"][0]

    assert primary_entry["final_filename"].startswith("summary--primary")
    assert secondary_entry["final_filename"].startswith("summary--secondary")
    assert len(manifest["conflict_groups"]) == 1


def test_manifest_adds_counter_for_repeat_slug():
    workflow = _workflow_info("Primary", ["Duplicate", "Duplicate"])
    plan = _plan([_candidate(workflow)])

    namer = MultiWorkflowDeliverableNamer()
    manifest = namer.build_manifest(issue_number=7, issue_title="Duplicated", plan=plan)

    deliverables = manifest["workflows"][0]["deliverables"]
    filenames = [entry["final_filename"] for entry in deliverables]

    assert filenames[0].startswith("duplicate--primary")
    assert filenames[1].startswith("duplicate--primary--2")
    assert len(manifest["conflict_groups"]) == 1
