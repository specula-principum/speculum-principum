"""Tests for the knowledge base extraction coordinator."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import threading
import time
from typing import Any

import pytest

from src.extraction import ExtractionResult
from src.extraction.config import ExtractionConfig
from src.kb_engine.extraction import ExtractionCoordinator


def _make_result(extractor: str, text: str, config: Mapping[str, object]) -> ExtractionResult:
    config_map = dict(config)
    source_path = str(config_map.get("source_path", "<memory>"))
    checksum = f"{extractor}:{len(text)}:{hash(text) & 0xFFFF:x}"
    return ExtractionResult(
        source_path=source_path,
        checksum=checksum,
        extractor_name=extractor,
        data={"extractor": extractor, "text": text},
        metadata=config_map,
        created_at=datetime.utcnow(),
    )


def test_extract_all_runs_enabled_tools() -> None:
    calls: list[tuple[str, str, dict[str, object]]] = []

    def runner(name: str, text: str, config: Mapping[str, object]) -> ExtractionResult:
        record = (name, text, dict(config))
        calls.append(record)
        return _make_result(name, text, config)

    coordinator = ExtractionCoordinator(
        enabled_tools=("concepts", "entities"),
        parallel_execution=False,
        cache_results=False,
        runner=runner,
    )

    bundle = coordinator.extract_all(
        "Princeps", ExtractionConfig.empty(), source_path="/tmp/source.txt"
    )

    assert bundle.success is True
    assert set(bundle.results) == {"concepts", "entities"}
    assert bundle.failures == {}
    assert [summary.extractor for summary in bundle.summaries] == ["concepts", "entities"]
    assert calls[0][0] == "concepts"
    assert calls[1][0] == "entities"


def test_extract_selective_enforces_requests() -> None:
    coordinator = ExtractionCoordinator(
        enabled_tools=("concepts", "entities"),
        parallel_execution=False,
        cache_results=False,
        runner=lambda name, text, cfg: _make_result(name, text, cfg),
    )

    bundle = coordinator.extract_selective("text", ("concepts",), ExtractionConfig.empty())
    assert bundle.success is True
    assert tuple(bundle.results) == ("concepts",)

    with pytest.raises(ValueError):
        coordinator.extract_selective("text", (), ExtractionConfig.empty())

    with pytest.raises(ValueError):
        coordinator.extract_selective("text", ("relationships",), ExtractionConfig.empty())


def test_extract_all_uses_cache() -> None:
    call_count = 0

    def runner(name: str, text: str, config: Mapping[str, object]) -> ExtractionResult:
        nonlocal call_count
        call_count += 1
        time.sleep(0.01)
        return _make_result(name, text, config)

    coordinator = ExtractionCoordinator(
        enabled_tools=("concepts",),
        parallel_execution=False,
        cache_results=True,
        cache_ttl=60.0,
        runner=runner,
    )

    first = coordinator.extract_all("text", ExtractionConfig.empty())
    second = coordinator.extract_all("text", ExtractionConfig.empty())

    assert first.success and second.success
    assert call_count == 1
    assert first.summaries[0].from_cache is False
    assert second.summaries[0].from_cache is True


def test_extract_all_parallel_execution_emits_progress() -> None:
    barrier = threading.Barrier(2, timeout=5.0)
    running_threads: set[int] = set()

    def runner(name: str, text: str, config: Mapping[str, object]) -> ExtractionResult:
        barrier.wait()
        time.sleep(0.02)
        return _make_result(name, text, config)

    lock = threading.Lock()

    def progress(event: Any) -> None:
        if getattr(event, "status", "") == "running":
            with lock:
                running_threads.add(threading.get_ident())

    coordinator = ExtractionCoordinator(
        enabled_tools=("concepts", "entities"),
        parallel_execution=True,
        cache_results=False,
        runner=runner,
    )

    bundle = coordinator.extract_all("text", ExtractionConfig.empty(), progress_callback=progress)

    assert bundle.success is True
    assert len(running_threads) >= 2


def test_extract_all_records_failures() -> None:
    def runner(name: str, text: str, config: Mapping[str, object]) -> ExtractionResult:
        if name == "entities":
            raise RuntimeError("entity extractor failure")
        return _make_result(name, text, config)

    coordinator = ExtractionCoordinator(
        enabled_tools=("concepts", "entities"),
        parallel_execution=False,
        cache_results=False,
        runner=runner,
    )

    bundle = coordinator.extract_all("text", ExtractionConfig.empty())

    assert bundle.success is False
    assert bundle.results.keys() == {"concepts"}
    assert bundle.failures == {"entities": "entity extractor failure"}
    summaries = {summary.extractor: summary for summary in bundle.summaries}
    assert summaries["concepts"].success is True
    assert summaries["entities"].success is False
    assert summaries["entities"].error == "entity extractor failure"
