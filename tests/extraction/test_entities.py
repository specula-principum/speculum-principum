"""Tests for the entities extractor."""
from __future__ import annotations

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
