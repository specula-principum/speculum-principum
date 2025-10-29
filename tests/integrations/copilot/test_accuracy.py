from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Dict, cast
import json

import pytest

from src.integrations.copilot.accuracy import (
    AccuracyScenario,
  AccuracyReport,
    collect_kb_signatures,
    evaluate_accuracy,
    load_accuracy_scenario,
    render_accuracy_report,
)


@pytest.fixture()
def kb_root(tmp_path: Path) -> Path:
    root = tmp_path / "knowledge-base"
    _build_sample_kb(root)
    return root


def test_load_accuracy_scenario(tmp_path: Path) -> None:
    scenario_path = tmp_path / "scenario.yaml"
    scenario_path.write_text(
        textwrap.dedent(
            """
            name: Sample Scenario
            description: Validate golden concepts and entities
            expectations:
              concepts:
                - concepts/governance/stellar-governance
              entities:
                must_include:
                  - entities/institutions/terra-council
              relationships:
                - concepts/governance/stellar-governance|related|concepts/governance/interplanetary-law
            """
        ).strip(),
        encoding="utf-8",
    )

    scenario = load_accuracy_scenario(scenario_path)
    assert scenario.name == "Sample Scenario"
    assert "golden" in (scenario.description or "")
    assert "concepts/governance/stellar-governance" in scenario.concepts
    assert "entities/institutions/terra-council" in scenario.entities
    assert (
        "concepts/governance/stellar-governance|related|concepts/governance/interplanetary-law"
        in scenario.relationships
    )


def test_collect_kb_signatures(kb_root: Path) -> None:
    snapshot = collect_kb_signatures(kb_root)
    assert "concepts/governance/stellar-governance" in snapshot["concepts"]
    assert "entities/institutions/terra-council" in snapshot["entities"]
    assert (
        "concepts/governance/stellar-governance|related|concepts/governance/interplanetary-law"
        in snapshot["relationships"]
    )


def test_load_accuracy_scenario_from_json(tmp_path: Path) -> None:
  scenario_path = tmp_path / "scenario.json"
  scenario_path.write_text(
    json.dumps(
      {
        "name": "JSON Scenario",
        "expectations": {
          "concepts": ["concepts/governance/stellar-governance"],
          "relationships": [
            {
              "source": "concepts/governance/stellar-governance",
              "target": "concepts/governance/interplanetary-law",
              "relation": "supports",
            }
          ],
        },
      }
    ),
    encoding="utf-8",
  )

  scenario = load_accuracy_scenario(scenario_path)
  assert scenario.name == "JSON Scenario"
  assert "supports" in next(iter(scenario.relationships))


def test_evaluate_accuracy_success(tmp_path: Path, kb_root: Path) -> None:
    scenario_path = tmp_path / "scenario.yaml"
    scenario_path.write_text(
        textwrap.dedent(
            """
            expectations:
              concepts:
                - concepts/governance/stellar-governance
              entities:
                - entities/institutions/terra-council
              relationships:
                - concepts/governance/stellar-governance|related|concepts/governance/interplanetary-law
                - concepts/governance/stellar-governance|topic|concepts/governance/interplanetary-law
                - entities/institutions/terra-council|entity|concepts/governance/stellar-governance
            """
        ).strip(),
        encoding="utf-8",
    )

    scenario = load_accuracy_scenario(scenario_path)
    report = evaluate_accuracy(scenario, kb_root)
    assert report.is_successful is True
    assert report.overall_recall == pytest.approx(1.0)
    rendered = render_accuracy_report(report)
    assert "Success: yes" in rendered
    assert "Overall Recall" in rendered


def test_evaluate_accuracy_detects_missing(kb_root: Path) -> None:
    scenario = AccuracyScenario(
        name="Missing Concept",
        description=None,
        concepts=frozenset({"concepts/governance/nonexistent"}),
        entities=frozenset(),
        relationships=frozenset(),
    )

    report = evaluate_accuracy(scenario, kb_root)
    assert report.is_successful is False
    assert report.concepts.missing == {"concepts/governance/nonexistent"}
    assert report.concepts.precision == pytest.approx(0.0)
    assert report.concepts.recall == pytest.approx(0.0)


def test_evaluate_accuracy_flags_unexpected(kb_root: Path) -> None:
  scenario = AccuracyScenario(
    name="Unexpected",
    description=None,
    concepts=frozenset(),
    entities=frozenset(),
    relationships=frozenset(),
  )

  report = evaluate_accuracy(scenario, kb_root)
  assert "concepts/governance/stellar-governance" in report.concepts.unexpected
  assert report.concepts.precision == pytest.approx(0.0)
  assert report.concepts.recall == pytest.approx(1.0)


def test_accuracy_report_to_dict_contains_metrics(kb_root: Path) -> None:
  scenario = AccuracyScenario(
    name="Dict",
    description="check serialization",
    concepts=frozenset({"concepts/governance/stellar-governance"}),
    entities=frozenset(),
    relationships=frozenset(),
  )
  report = evaluate_accuracy(scenario, kb_root)
  payload = cast(Dict[str, Any], report.to_dict())
  assert payload["scenario"]["name"] == "Dict"
  assert payload["concepts"]["expected"] == 1
  assert payload["overall"]["matches"] == 1


def _build_sample_kb(root: Path) -> None:
    concept_path = root / "concepts" / "governance" / "stellar-governance.md"
    entity_path = root / "entities" / "institutions" / "terra-council.md"
    for file_path in (concept_path, entity_path):
        file_path.parent.mkdir(parents=True, exist_ok=True)

    concept_path.write_text(
        textwrap.dedent(
            """
            ---
            title: Stellar Governance
            slug: stellar-governance
            kb_id: concepts/governance/stellar-governance
            type: concept
            primary_topic: governance
            tags:
              - governance
            sources:
              - kb_id: sources/chronicle/starfall
                pages: [1]
            dublin_core:
              title: Stellar Governance
            ia:
              findability_score: 0.92
              completeness: 0.95
              related_by_topic:
                - concepts/governance/interplanetary-law
            related_concepts:
              - concepts/governance/interplanetary-law
            ---
            Stellar governance focuses on federated planetary systems.
            """
        ).strip(),
        encoding="utf-8",
    )

    entity_path.write_text(
        textwrap.dedent(
            """
            ---
            title: Terra Council
            slug: terra-council
            kb_id: entities/institutions/terra-council
            type: entity
            primary_topic: institutions
            tags:
              - institutions
            sources:
              - kb_id: sources/chronicle/terra
                pages: [2]
            dublin_core:
              title: Terra Council
            ia:
              findability_score: 0.9
              completeness: 0.88
              related_by_entity:
                - concepts/governance/stellar-governance
            ---
            Terra Council coordinates interplanetary governance.
            """
        ).strip(),
        encoding="utf-8",
    )
