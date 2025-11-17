"""Tests for the entities extractor."""
from __future__ import annotations

from pathlib import Path

import yaml

from src.extraction.entities import extract_entities

SAMPLE_TEXT = (
    "Niccolo Machiavelli served the Florentine Republic in 1532 after advising the Sforza family."
)


def test_extract_entities_detects_person_org_and_date() -> None:
    result = extract_entities(SAMPLE_TEXT)
    entities = {entity.entity_type: entity for entity in result.data}

    assert entities["PERSON"].text == "Niccolo Machiavelli"
    assert entities["ORG"].text in {"Florentine Republic", "Sforza"}
    assert entities["DATE"].text == "1532"


def test_extract_entities_respects_entity_type_filter() -> None:
    result = extract_entities(SAMPLE_TEXT, entity_types=("PERSON",))
    assert all(entity.entity_type == "PERSON" for entity in result.data)


def test_entities_default_profile_for_prince_fixture() -> None:
    text_path = Path("tests/extraction/fixtures/prince01mach_1/sample_combined.md")
    text = text_path.read_text(encoding="utf-8")

    full_config = yaml.safe_load(Path("config/extraction.yaml").read_text(encoding="utf-8"))
    entities_config = dict(full_config["entities"])  # type: ignore[index]
    entities_config["source_path"] = str(text_path)

    result = extract_entities(text, config=entities_config)

    payload = {(entity.text, entity.entity_type) for entity in result.data}

    assert ("Luigi Ricci", "PERSON") in payload
    assert ("Oxford University Press", "ORG") in payload
    italy = next(entity for entity in result.data if entity.text == "Italy")
    assert italy.entity_type == "GPE"
    assert italy.metadata.get("pattern") == "known_location"
    assert all(entity.confidence >= entities_config["confidence_threshold"] for entity in result.data)


def test_entities_detect_us_locations_demonyms_and_agencies() -> None:
    text = (
        "The State of Colorado coordinated with the Department of Transportation to provide grants "
        "so Texans could expand regional transit services."
    )

    full_config = yaml.safe_load(Path("config/extraction.yaml").read_text(encoding="utf-8"))
    entities_config = dict(full_config["entities"])  # type: ignore[index]

    result = extract_entities(text, config=entities_config)

    state_entity = next(entity for entity in result.data if entity.text == "State of Colorado")
    assert state_entity.entity_type == "GPE"
    assert state_entity.metadata.get("pattern") == "known_location"

    texans_entity = next(entity for entity in result.data if entity.text == "Texans")
    assert texans_entity.metadata.get("canonical") == "Texas"

    agency_entity = next(entity for entity in result.data if entity.text == "Department of Transportation")
    assert agency_entity.entity_type == "ORG"
    assert agency_entity.metadata.get("pattern") == "known_organization"
