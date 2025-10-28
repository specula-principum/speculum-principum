"""Extraction coordination for the knowledge base engine."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import logging
from threading import Lock
from time import monotonic
from typing import Callable, Iterable, Mapping, MutableMapping, Sequence

from src.extraction import ExtractionResult
from src.extraction.cli import available_extractors, run_extractor
from src.extraction.config import ExtractionConfig, validate_requested_extractors


logger = logging.getLogger(__name__)


ProgressCallback = Callable[["ExtractionProgressEvent"], None]
RunnerCallable = Callable[[str, str, Mapping[str, object]], ExtractionResult]


@dataclass(frozen=True, slots=True)
class ExtractionRunSummary:
    """Execution metadata for a single extractor run."""

    extractor: str
    duration: float
    from_cache: bool
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


@dataclass(frozen=True, slots=True)
class ExtractionBundle:
    """Aggregated extraction results and execution details."""

    results: Mapping[str, ExtractionResult]
    failures: Mapping[str, str]
    summaries: Sequence[ExtractionRunSummary]
    started_at: datetime
    completed_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "results", dict(self.results))
        object.__setattr__(self, "failures", dict(self.failures))
        object.__setattr__(self, "summaries", tuple(self.summaries))

    @property
    def success(self) -> bool:
        return not self.failures


@dataclass(frozen=True, slots=True)
class ExtractionProgressEvent:
    """Progress notification emitted during extraction coordination."""

    extractor: str
    index: int
    total: int
    status: str
    duration: float | None = None
    error: str | None = None


@dataclass(slots=True)
class _CacheEntry:
    result: ExtractionResult
    timestamp: float


def _default_runner(name: str, text: str, config: Mapping[str, object]) -> ExtractionResult:
    return run_extractor(name, text, config=config)


class ExtractionCoordinator:
    """Manages extraction tool execution and result aggregation."""

    def __init__(
        self,
        *,
        enabled_tools: Sequence[str] | None = None,
        parallel_execution: bool = True,
        cache_results: bool = True,
        cache_ttl: float | None = 86_400.0,
        runner: RunnerCallable | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.enabled_tools: tuple[str, ...] = tuple(enabled_tools or ())
        self.parallel_execution = parallel_execution
        self.cache_results = cache_results
        self.cache_ttl = cache_ttl if (cache_ttl is None or cache_ttl >= 0) else 0.0
        self._runner: RunnerCallable = runner or _default_runner
        self._progress_callback = progress_callback
        self._cache: MutableMapping[str, _CacheEntry] = {}
        self._cache_lock = Lock()

    def extract_all(
        self,
        text: str,
        config: ExtractionConfig | Mapping[str, Mapping[str, object]] | None = None,
        *,
        source_path: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> ExtractionBundle:
        """Run all configured extractors on the provided text."""

        return self._run_extractors(
            text,
            config,
            requested=None,
            source_path=source_path,
            progress_callback=progress_callback,
        )

    def extract_selective(
        self,
        text: str,
        extractors: Sequence[str],
        config: ExtractionConfig | Mapping[str, Mapping[str, object]] | None = None,
        *,
        source_path: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> ExtractionBundle:
        """Run only the requested extractors for the provided text."""

        if not extractors:
            raise ValueError("extractors must contain at least one extractor name")

        return self._run_extractors(
            text,
            config,
            requested=tuple(extractors),
            source_path=source_path,
            progress_callback=progress_callback,
        )

    # Internal helpers -------------------------------------------------

    def _run_extractors(
        self,
        text: str,
        config: ExtractionConfig | Mapping[str, Mapping[str, object]] | None,
        *,
        requested: Sequence[str] | None,
        source_path: str | None,
        progress_callback: ProgressCallback | None,
    ) -> ExtractionBundle:
        extraction_config = self._normalise_config(config)
        selected = self._resolve_extractors(requested, extraction_config)

        started_at = datetime.utcnow()
        results: dict[str, ExtractionResult] = {}
        failures: dict[str, str] = {}
        summaries: list[ExtractionRunSummary] = []

        if not selected:
            completed = datetime.utcnow()
            return ExtractionBundle(results, failures, summaries, started_at, completed)

        total = len(selected)
        tasks = [
            (index, extractor, self._build_extractor_config(extractor, extraction_config, source_path))
            for index, extractor in enumerate(selected, start=1)
        ]

        if self.parallel_execution and len(tasks) > 1:
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
                futures = [
                    executor.submit(
                        self._execute_extractor,
                        extractor,
                        text,
                        cfg,
                        index,
                        total,
                        progress_callback,
                    )
                    for index, extractor, cfg in tasks
                ]
                for future in futures:
                    extractor, outcome = future.result()
                    self._record_outcome(extractor, outcome, results, failures, summaries)
        else:
            for index, extractor, cfg in tasks:
                _, outcome = self._execute_extractor(
                    extractor,
                    text,
                    cfg,
                    index,
                    total,
                    progress_callback,
                )
                self._record_outcome(extractor, outcome, results, failures, summaries)

        completed_at = datetime.utcnow()
        order = {name: position for position, name in enumerate(selected)}
        summaries.sort(key=lambda summary: order.get(summary.extractor, 0))
        return ExtractionBundle(results, failures, summaries, started_at, completed_at)

    def _record_outcome(
        self,
        extractor: str,
        outcome: tuple[ExtractionResult | None, ExtractionRunSummary],
        results: dict[str, ExtractionResult],
        failures: dict[str, str],
        summaries: list[ExtractionRunSummary],
    ) -> None:
        result, summary = outcome
        summaries.append(summary)
        if result is not None:
            results[extractor] = result
        if summary.error is not None:
            failures[extractor] = summary.error

    def _execute_extractor(
        self,
        extractor: str,
        text: str,
        cfg: Mapping[str, object],
        index: int,
        total: int,
        progress_callback: ProgressCallback | None,
    ) -> tuple[str, tuple[ExtractionResult | None, ExtractionRunSummary]]:
        self._emit_progress(extractor, index, total, "scheduled", progress_callback)

        cache_key = self._build_cache_key(extractor, text, cfg)
        cached_entry = self._load_from_cache(cache_key)
        if cached_entry is not None:
            duration = 0.0
            summary = ExtractionRunSummary(extractor=extractor, duration=duration, from_cache=True, error=None)
            self._emit_progress(extractor, index, total, "cache-hit", progress_callback, duration=duration)
            return extractor, (cached_entry.result, summary)

        self._emit_progress(extractor, index, total, "running", progress_callback)

        started = monotonic()
        try:
            result = self._runner(extractor, text, cfg)
        except Exception as exc:  # noqa: BLE001
            duration = monotonic() - started
            message = str(exc)
            logger.exception("Extractor '%s' failed", extractor)
            summary = ExtractionRunSummary(
                extractor=extractor,
                duration=duration,
                from_cache=False,
                error=message,
            )
            self._emit_progress(extractor, index, total, "failed", progress_callback, duration=duration, error=message)
            return extractor, (None, summary)

        duration = monotonic() - started
        summary = ExtractionRunSummary(extractor=extractor, duration=duration, from_cache=False, error=None)

        self._store_in_cache(cache_key, result)
        self._emit_progress(extractor, index, total, "success", progress_callback, duration=duration)
        return extractor, (result, summary)

    def _normalise_config(
        self,
        config: ExtractionConfig | Mapping[str, Mapping[str, object]] | None,
    ) -> ExtractionConfig:
        if isinstance(config, ExtractionConfig):
            return config
        if config is None:
            return ExtractionConfig.empty()
        if isinstance(config, Mapping):
            return ExtractionConfig.from_mapping(config)
        raise TypeError("config must be an ExtractionConfig, mapping, or None")

    def _resolve_extractors(
        self,
        requested: Sequence[str] | None,
        config: ExtractionConfig,
    ) -> tuple[str, ...]:
        available = available_extractors()
        config_keys = tuple(config.raw.keys())

        if requested:
            candidates: Iterable[str] = requested
        elif self.enabled_tools:
            candidates = self.enabled_tools
        elif config_keys:
            candidates = config_keys
        else:
            candidates = available

        ordered_unique: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            ordered_unique.append(candidate)
            seen.add(candidate)

        validate_requested_extractors(ordered_unique)
        if self.enabled_tools:
            disallowed = [name for name in ordered_unique if name not in self.enabled_tools]
            if disallowed:
                raise ValueError(
                    "Extractors not permitted by coordinator configuration: " + ", ".join(disallowed)
                )

        return tuple(ordered_unique)

    def _build_extractor_config(
        self,
        extractor: str,
        config: ExtractionConfig,
        source_path: str | None,
    ) -> Mapping[str, object]:
        mapping = dict(config.raw.get(extractor, {}))
        if source_path and "source_path" not in mapping:
            mapping["source_path"] = source_path
        return mapping

    def _emit_progress(
        self,
        extractor: str,
        index: int,
        total: int,
        status: str,
        progress_callback: ProgressCallback | None,
        *,
        duration: float | None = None,
        error: str | None = None,
    ) -> None:
        callback = progress_callback or self._progress_callback
        if not callback:
            return
        event = ExtractionProgressEvent(
            extractor=extractor,
            index=index,
            total=total,
            status=status,
            duration=duration,
            error=error,
        )
        try:
            callback(event)
        except Exception:  # pragma: no cover - defensive guard
            logger.exception("Progress callback failed for extractor '%s'", extractor)

    def _build_cache_key(self, extractor: str, text: str, cfg: Mapping[str, object]) -> str:
        serialized_config = json.dumps(cfg, sort_keys=True, default=self._json_default)
        hasher = hashlib.sha256()
        hasher.update(extractor.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(text.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(serialized_config.encode("utf-8"))
        return hasher.hexdigest()

    @staticmethod
    def _json_default(value: object) -> str:
        return repr(value)

    def _load_from_cache(self, key: str) -> _CacheEntry | None:
        if not self.cache_results:
            return None
        with self._cache_lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if self.cache_ttl is not None and (monotonic() - entry.timestamp) > self.cache_ttl:
                self._cache.pop(key, None)
                return None
            return entry

    def _store_in_cache(self, key: str, result: ExtractionResult) -> None:
        if not self.cache_results:
            return
        entry = _CacheEntry(result=result, timestamp=monotonic())
        with self._cache_lock:
            self._cache[key] = entry

