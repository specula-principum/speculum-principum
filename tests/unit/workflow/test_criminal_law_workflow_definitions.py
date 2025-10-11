"""Validation tests for criminal law workflow definitions."""

from pathlib import Path
import yaml

from src.workflow.workflow_schemas import WorkflowSchemaValidator

ROOT = Path(__file__).resolve().parents[3]
CRIMINAL_LAW_DIR = ROOT / "docs" / "workflow" / "deliverables" / "criminal-law"
EXPECTED_WORKFLOWS = {
    "asset-evidence-cataloguing.yaml",
    "case-law-precedent-explorer.yaml",
    "compliance-remediation-monitoring.yaml",
    "inter-agency-coordination-briefs.yaml",
    "investigative-lead-development.yaml",
    "person-entity-profiling.yaml",
    "place-intelligence-mapping.yaml",
    "sentencing-mitigation-scenario-planner.yaml",
    "statutory-regulatory-research-tracker.yaml",
    "witness-expert-reliability-assessment.yaml",
}


def _load_workflow(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_all_expected_workflows_present():
    workflow_files = {path.name for path in CRIMINAL_LAW_DIR.glob("*.yaml")}
    assert workflow_files == EXPECTED_WORKFLOWS


def test_criminal_law_workflows_validate_against_schema():
    for workflow_file in CRIMINAL_LAW_DIR.glob("*.yaml"):
        workflow = _load_workflow(workflow_file)
        is_valid, errors = WorkflowSchemaValidator.validate_workflow(workflow)
        assert is_valid, f"{workflow_file.name} failed validation: {errors}"
        assert isinstance(workflow.get("audit_trail", {}).get("required"), bool)


def test_criminal_law_workflow_categories_match_taxonomy():
    categories = {
        _load_workflow(path).get("category") for path in CRIMINAL_LAW_DIR.glob("*.yaml")
    }
    assert categories == {
        "entity-foundation",
        "legal-research",
        "operational-coordination",
    }


def test_criminal_law_deliverables_declare_required_sections():
    for workflow_path in CRIMINAL_LAW_DIR.glob("*.yaml"):
        workflow = _load_workflow(workflow_path)
        deliverables = workflow.get("deliverables", [])
        declared_sections = set()

        for deliverable in deliverables:
            sections = deliverable.get("required_sections")
            assert sections, (
                f"{workflow_path.name} deliverable '{deliverable.get('name')}' is missing required_sections"
            )
            declared_sections.update(sections)

        validation_sections = (
            (workflow.get("validation") or {}).get("required_sections") or []
        )
        for section in validation_sections:
            assert (
                section in declared_sections
            ), f"{workflow_path.name} validation section '{section}' is not declared in deliverable required_sections"
