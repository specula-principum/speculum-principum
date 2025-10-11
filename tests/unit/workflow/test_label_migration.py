"""Compatibility checks for the retired label translation shim."""

from src.workflow.label_migration import WorkflowLabelTranslator


def test_translate_returns_original_labels_without_modification():
    labels = ["site-monitor", "statute-review", "custom"]
    result = WorkflowLabelTranslator.translate(labels)

    assert result.augmented_labels == frozenset(labels)
    assert result.added_labels == frozenset()
    assert result.mapping == {}
