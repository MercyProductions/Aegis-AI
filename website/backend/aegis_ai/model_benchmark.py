from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .model_registry import ModelRegistryManager
from .providers.registry import build_provider_adapter, provider_config_from_registry_provider
from .schemas import (
    ModelBenchmarkJobInfo,
    ModelBenchmarkProviderScore,
    ModelBenchmarkResult,
    ModelBenchmarkRunRequest,
    ModelBenchmarkSnapshot,
    ModelBenchmarkSuiteInfo,
    ModelBenchmarkSuiteSummary,
    ModelRegistryProvider,
)
from .settings import Settings


@dataclass(frozen=True)
class BenchmarkSuite:
    id: str
    label: str
    description: str
    prompt: str
    expected_terms: tuple[str, ...]
    expected_display: str


BENCHMARK_SUITES: tuple[BenchmarkSuite, ...] = (
    BenchmarkSuite(
        id="chat",
        label="General Chat",
        description="Short instruction following and conversational usefulness.",
        prompt=(
            "Return only valid JSON with keys answer and confidence. "
            "Answer this user request: Count from 11 to 20 inclusive as comma-separated numbers."
        ),
        expected_terms=("11", "12", "13", "14", "15", "16", "17", "18", "19", "20"),
        expected_display="11 through 20",
    ),
    BenchmarkSuite(
        id="code",
        label="Coding",
        description="Small code generation with a named function and usable implementation.",
        prompt=(
            "Return only valid JSON with keys answer, code, language, and confidence. "
            "Write a Python function named fibonacci(n) that returns the nth Fibonacci number iteratively."
        ),
        expected_terms=("def fibonacci", "return", "for", "python"),
        expected_display="iterative Python fibonacci(n)",
    ),
    BenchmarkSuite(
        id="reasoning",
        label="Reasoning",
        description="Compact deterministic reasoning without tools.",
        prompt=(
            "Return only valid JSON with keys answer and confidence. "
            "A three-digit code uses these digits in order: 2+3, 9-4, and 12/3. What is the code?"
        ),
        expected_terms=("554",),
        expected_display="554",
    ),
)
MAX_MODEL_BENCHMARK_JSON_BYTES = 512_000


class ModelBenchmarkManager:
    def __init__(self, project_root: Path, settings: Settings, registry: ModelRegistryManager):
        self.project_root = project_root
        self.settings = settings
        self.registry = registry
        self.results_path = project_root / "data" / "model_benchmarks.json"
        self.jobs_path = project_root / "data" / "model_benchmark_jobs.json"
        self._active_tasks: dict[str, asyncio.Task[None]] = {}
        self._recover_interrupted_jobs()

    def snapshot(self) -> ModelBenchmarkSnapshot:
        results = self._load_results()
        provider_scores = self._provider_scores(results)
        suite_summaries = self._suite_summaries(results, provider_scores)
        latest_at = max((result.created_at for result in results), default="")
        return ModelBenchmarkSnapshot(
            ok=True,
            message=self._message(results, provider_scores),
            suites=[ModelBenchmarkSuiteInfo(id=suite.id, label=suite.label, description=suite.description) for suite in BENCHMARK_SUITES],
            provider_scores=provider_scores,
            suite_summaries=suite_summaries,
            recent_results=sorted(results, key=lambda result: result.created_at, reverse=True)[:50],
            jobs=self.jobs(limit=12),
            recommendations=self._recommendations(provider_scores, suite_summaries),
            results_total=len(results),
            latest_at=latest_at,
        )

    def jobs(self, limit: int = 25) -> list[ModelBenchmarkJobInfo]:
        return sorted(self._load_jobs(), key=lambda job: job.created_at, reverse=True)[: max(1, limit)]

    async def run(self, request: ModelBenchmarkRunRequest) -> ModelBenchmarkSnapshot:
        suites = self._select_suites(request.suite_ids)
        providers = self._select_providers(request.provider_ids, request.max_models, request.local_only)
        if not suites:
            raise ValueError("At least one benchmark suite is required.")
        if not providers:
            raise ValueError("No configured benchmarkable providers are available.")

        results: list[ModelBenchmarkResult] = []
        for provider in providers:
            config = provider_config_from_registry_provider(provider, self.settings)
            adapter = build_provider_adapter(self.settings, config)
            for suite in suites:
                results.append(await self._run_suite(provider, adapter, suite, request.timeout_seconds))

        self._append_results(results)
        return self.snapshot()

    def start_job(self, request: ModelBenchmarkRunRequest) -> ModelBenchmarkJobInfo:
        suites = self._select_suites(request.suite_ids)
        providers = self._select_providers(request.provider_ids, request.max_models, request.local_only)
        if not suites:
            raise ValueError("At least one benchmark suite is required.")
        if not providers:
            raise ValueError("No configured benchmarkable providers are available.")
        active = [job for job in self._load_jobs() if job.status in {"queued", "running", "cancel_requested"}]
        if active:
            raise ValueError("A model benchmark job is already running. Refresh scores to view its progress.")

        now = self._now()
        job = ModelBenchmarkJobInfo(
            id=f"bench-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}",
            status="queued",
            message=f"Queued {len(providers)} model(s) across {len(suites)} suite(s).",
            created_at=now,
            suite_ids=[suite.id for suite in suites],
            provider_ids=[provider.id for provider in providers],
            max_models=request.max_models,
            local_only=request.local_only,
            timeout_seconds=request.timeout_seconds,
            total_runs=len(providers) * len(suites),
        )
        self._upsert_job(job)
        task = asyncio.create_task(self._run_job(job.id, request))
        self._active_tasks[job.id] = task
        task.add_done_callback(lambda finished_task, job_id=job.id: self._handle_job_task_done(job_id, finished_task))
        return job

    def cancel_job(self, job_id: str) -> ModelBenchmarkJobInfo:
        job = self._get_job(job_id)
        if job.status == "failed" and job.message == "Benchmark job state was not found.":
            raise ValueError("Benchmark job was not found.")
        if job.status in {"completed", "failed", "interrupted", "canceled"}:
            raise ValueError(f"Benchmark job is already {job.status}.")
        if job.status == "cancel_requested":
            return job

        job.status = "cancel_requested"
        job.message = "Cancel requested. Stopping the benchmark job..."
        self._upsert_job(job)

        task = self._active_tasks.get(job_id)
        if task is not None and not task.done():
            task.cancel()
        else:
            self._mark_job_canceled(job_id, "Benchmark job was canceled before it started another run.")
        return self._get_job(job_id)

    async def _run_job(self, job_id: str, request: ModelBenchmarkRunRequest) -> None:
        try:
            suites = self._select_suites(request.suite_ids)
            providers = self._select_providers(request.provider_ids, request.max_models, request.local_only)
            if not suites or not providers:
                raise ValueError("No benchmark suites or providers are available for this job.")

            job = self._get_job(job_id)
            job.status = "running"
            job.started_at = self._now()
            job.message = "Benchmark job is running."
            job.suite_ids = [suite.id for suite in suites]
            job.provider_ids = [provider.id for provider in providers]
            job.total_runs = len(suites) * len(providers)
            self._upsert_job(job)

            for provider in providers:
                self._raise_if_job_canceled(job_id)
                config = provider_config_from_registry_provider(provider, self.settings)
                adapter = build_provider_adapter(self.settings, config)
                for suite in suites:
                    self._raise_if_job_canceled(job_id)
                    job = self._get_job(job_id)
                    job.status = "running"
                    job.current_provider_id = provider.id
                    job.current_model_name = provider.model_name
                    job.current_suite_id = suite.id
                    job.message = f"Benchmarking {provider.model_name} on {suite.label}."
                    self._upsert_job(job)

                    result = await self._run_suite(provider, adapter, suite, request.timeout_seconds)
                    self._append_results([result])

                    job = self._get_job(job_id)
                    job.completed_runs += 1
                    if result.status != "succeeded":
                        job.failed_runs += 1
                    job.message = self._job_progress_message(job)
                    self._upsert_job(job)
                    self._raise_if_job_canceled(job_id)

            job = self._get_job(job_id)
            job.status = "completed"
            job.finished_at = self._now()
            job.current_provider_id = ""
            job.current_model_name = ""
            job.current_suite_id = ""
            job.message = self._job_progress_message(job)
            self._upsert_job(job)
        except asyncio.CancelledError:
            self._mark_job_canceled(job_id, "Benchmark job was canceled.")
            raise
        except Exception as exc:
            job = self._get_job(job_id)
            job.status = "failed"
            job.finished_at = self._now()
            job.error = str(exc)[:500]
            job.message = "Benchmark job failed."
            self._upsert_job(job)

    async def _run_suite(
        self,
        provider: ModelRegistryProvider,
        adapter: Any,
        suite: BenchmarkSuite,
        timeout_seconds: float,
    ) -> ModelBenchmarkResult:
        started = time.perf_counter()
        created_at = self._now()
        result = ModelBenchmarkResult(
            id=f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}",
            created_at=created_at,
            provider_id=provider.id,
            provider_label=provider.label,
            api=provider.api,
            endpoint=provider.endpoint,
            model_name=provider.model_name,
            suite_id=suite.id,
            suite_label=suite.label,
            status="running",
            expected=suite.expected_display,
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are being benchmarked by Aegis. Return concise, valid JSON only. "
                    "Do not include markdown fences or extra commentary."
                ),
            },
            {"role": "user", "content": suite.prompt},
        ]

        try:
            payload = await asyncio.wait_for(adapter.complete_json(messages), timeout=max(5.0, timeout_seconds))
            latency_ms = int((time.perf_counter() - started) * 1000)
            score, metadata = self.score_payload(suite, payload, latency_ms)
            result.status = "succeeded"
            result.score = score
            result.latency_ms = latency_ms
            result.answer_excerpt = self._excerpt(payload)
            result.metadata = metadata
            return result
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            result.status = "failed"
            result.latency_ms = int((time.perf_counter() - started) * 1000)
            result.error = f"Benchmark timed out after {timeout_seconds:.0f}s."
            return result
        except Exception as exc:
            result.status = "failed"
            result.latency_ms = int((time.perf_counter() - started) * 1000)
            result.error = str(exc)[:500]
            return result

    def score_payload(self, suite: BenchmarkSuite, payload: dict[str, Any], latency_ms: int) -> tuple[float, dict[str, Any]]:
        text = self._payload_text(payload)
        lowered = text.lower()
        hits = sum(1 for term in suite.expected_terms if term.lower() in lowered)
        hit_ratio = hits / max(1, len(suite.expected_terms))
        has_answer = any(str(payload.get(key) or "").strip() for key in ("answer", "code", "language"))
        valid_confidence = self._confidence(payload.get("confidence"))
        latency_score = max(0.0, min(1.0, (30000.0 - max(0, latency_ms)) / 30000.0))
        score = 0.25 + (0.15 if has_answer else 0.0) + (0.45 * hit_ratio) + (0.10 * latency_score) + (0.05 if valid_confidence is not None else 0.0)
        return round(max(0.0, min(1.0, score)), 4), {
            "expected_hits": hits,
            "expected_terms": len(suite.expected_terms),
            "hit_ratio": round(hit_ratio, 4),
            "has_answer": has_answer,
            "confidence": valid_confidence,
            "latency_score": round(latency_score, 4),
        }

    def _select_suites(self, suite_ids: list[str]) -> list[BenchmarkSuite]:
        requested = {suite_id.strip().lower() for suite_id in suite_ids if suite_id.strip()}
        if not requested:
            return list(BENCHMARK_SUITES)
        return [suite for suite in BENCHMARK_SUITES if suite.id in requested]

    def _select_providers(self, provider_ids: list[str], max_models: int, local_only: bool) -> list[ModelRegistryProvider]:
        registry = self.registry.snapshot()
        requested = {provider_id.strip() for provider_id in provider_ids if provider_id.strip()}
        providers: list[ModelRegistryProvider] = []
        for provider in registry.providers:
            if requested and provider.id not in requested:
                continue
            if not provider.enabled or not provider.configured or not provider.model_name.strip():
                continue
            if local_only and not provider.local:
                continue
            if "embeddings" in provider.roles and "chat" not in provider.capabilities:
                continue
            if "chat" not in provider.capabilities and "code" not in provider.capabilities and "reasoning" not in provider.capabilities:
                continue
            providers.append(provider)

        active_id = registry.active_provider_id
        providers.sort(
            key=lambda provider: (
                provider.id != active_id,
                not provider.local,
                provider.label.lower(),
                provider.model_name.lower(),
            )
        )
        return providers[: max(1, min(20, max_models))]

    def _provider_scores(self, results: list[ModelBenchmarkResult]) -> list[ModelBenchmarkProviderScore]:
        registry = self.registry.snapshot()
        providers_by_id = {provider.id: provider for provider in registry.providers}
        grouped: dict[str, list[ModelBenchmarkResult]] = {}
        for result in results:
            if result.provider_id:
                grouped.setdefault(result.provider_id, []).append(result)

        scores: list[ModelBenchmarkProviderScore] = []
        for provider_id, provider_results in grouped.items():
            latest_by_suite: dict[str, ModelBenchmarkResult] = {}
            for result in sorted(provider_results, key=lambda item: item.created_at):
                latest_by_suite[result.suite_id] = result

            latest_results = list(latest_by_suite.values())
            if not latest_results:
                continue
            overall = sum(result.score for result in latest_results) / len(latest_results)
            latencies = [result.latency_ms for result in latest_results if result.latency_ms is not None and result.latency_ms >= 0]
            provider = providers_by_id.get(provider_id)
            score = ModelBenchmarkProviderScore(
                provider_id=provider_id,
                provider_label=(provider.label if provider else latest_results[-1].provider_label),
                api=(provider.api if provider else latest_results[-1].api),
                model_name=(provider.model_name if provider else latest_results[-1].model_name),
                local=(provider.local if provider else True),
                enabled=(provider.enabled if provider else True),
                configured=(provider.configured if provider else False),
                overall_score=round(overall, 4),
                chat_score=self._suite_score(latest_by_suite, "chat"),
                code_score=self._suite_score(latest_by_suite, "code"),
                reasoning_score=self._suite_score(latest_by_suite, "reasoning"),
                avg_latency_ms=int(sum(latencies) / len(latencies)) if latencies else None,
                run_count=len(provider_results),
                latest_at=max(result.created_at for result in provider_results),
            )
            score.recommendation = self._score_recommendation(score)
            scores.append(score)

        scores.sort(key=lambda score: (score.overall_score, -(score.avg_latency_ms or 999999), score.latest_at), reverse=True)
        return scores

    def _suite_summaries(
        self,
        results: list[ModelBenchmarkResult],
        provider_scores: list[ModelBenchmarkProviderScore],
    ) -> list[ModelBenchmarkSuiteSummary]:
        summaries: list[ModelBenchmarkSuiteSummary] = []
        score_by_provider = {score.provider_id: score for score in provider_scores}
        for suite in BENCHMARK_SUITES:
            suite_results = [result for result in results if result.suite_id == suite.id]
            latest_by_provider: dict[str, ModelBenchmarkResult] = {}
            for result in sorted(suite_results, key=lambda item: item.created_at):
                latest_by_provider[result.provider_id] = result
            candidates = list(latest_by_provider.values())
            if not candidates:
                summaries.append(ModelBenchmarkSuiteSummary(suite_id=suite.id, suite_label=suite.label))
                continue
            best = max(candidates, key=lambda result: (result.score, -(result.latency_ms or 999999), result.created_at))
            provider_score = score_by_provider.get(best.provider_id)
            summaries.append(
                ModelBenchmarkSuiteSummary(
                    suite_id=suite.id,
                    suite_label=suite.label,
                    best_provider_id=best.provider_id,
                    best_provider_label=best.provider_label,
                    best_model_name=best.model_name,
                    best_score=best.score,
                    best_latency_ms=best.latency_ms,
                    run_count=len(suite_results),
                )
            )
            if provider_score and not summaries[-1].best_provider_label:
                summaries[-1].best_provider_label = provider_score.provider_label
        return summaries

    def _message(self, results: list[ModelBenchmarkResult], scores: list[ModelBenchmarkProviderScore]) -> str:
        if not results:
            return "No model benchmark data yet. Run a quick benchmark to seed routing quality scores."
        best = scores[0] if scores else None
        if best is None:
            return f"{len(results)} benchmark result(s) stored."
        return f"{len(results)} benchmark result(s) stored. Current leader: {best.model_name} ({best.overall_score:.2f})."

    def _recommendations(
        self,
        scores: list[ModelBenchmarkProviderScore],
        summaries: list[ModelBenchmarkSuiteSummary],
    ) -> list[str]:
        if not scores:
            return ["Run the quick local benchmark to start ranking installed models for chat, code, and reasoning."]
        recommendations = [f"Default to {scores[0].model_name} for balanced local work based on the latest benchmark pass."]
        for summary in summaries:
            if summary.best_model_name:
                recommendations.append(f"Use {summary.best_model_name} for {summary.suite_label.lower()} prompts.")
        return recommendations[:5]

    def _score_recommendation(self, score: ModelBenchmarkProviderScore) -> str:
        suite_scores = {
            "chat": score.chat_score,
            "code": score.code_score,
            "reasoning": score.reasoning_score,
        }
        best_suite, best_score = max(
            ((name, value) for name, value in suite_scores.items() if value is not None),
            key=lambda item: item[1],
            default=("general", 0.0),
        )
        if best_score >= 0.75:
            return f"Strong {best_suite} route candidate."
        if score.overall_score >= 0.55:
            return "Usable fallback route candidate."
        return "Needs more data or a stronger prompt fit."

    def _append_results(self, results: list[ModelBenchmarkResult]) -> None:
        existing = self._load_results()
        combined = sorted([*existing, *results], key=lambda result: result.created_at, reverse=True)[:500]
        self._write_json_list(self.results_path, [result.model_dump() for result in combined])

    def _job_progress_message(self, job: ModelBenchmarkJobInfo) -> str:
        if job.total_runs <= 0:
            return "Benchmark job has no runnable model/suite pairs."
        done = min(job.completed_runs, job.total_runs)
        failures = f", {job.failed_runs} failed" if job.failed_runs else ""
        return f"{done}/{job.total_runs} benchmark run(s) completed{failures}."

    def _raise_if_job_canceled(self, job_id: str) -> None:
        job = self._get_job(job_id)
        if job.status in {"cancel_requested", "canceled"}:
            raise asyncio.CancelledError()

    def _mark_job_canceled(self, job_id: str, message: str) -> None:
        job = self._get_job(job_id)
        if job.status in {"completed", "failed", "interrupted", "canceled"}:
            return
        job.status = "canceled"
        job.finished_at = job.finished_at or self._now()
        job.current_provider_id = ""
        job.current_model_name = ""
        job.current_suite_id = ""
        job.message = message
        self._upsert_job(job)

    def _handle_job_task_done(self, job_id: str, task: asyncio.Task[None]) -> None:
        self._active_tasks.pop(job_id, None)
        if task.cancelled():
            self._mark_job_canceled(job_id, "Benchmark job was canceled.")
            return
        try:
            task.result()
        except Exception as exc:
            job = self._get_job(job_id)
            if job.status not in {"completed", "failed", "interrupted", "canceled"}:
                job.status = "failed"
                job.finished_at = self._now()
                job.error = str(exc)[:500]
                job.message = "Benchmark job failed."
                self._upsert_job(job)

    def _get_job(self, job_id: str) -> ModelBenchmarkJobInfo:
        for job in self._load_jobs():
            if job.id == job_id:
                return job
        return ModelBenchmarkJobInfo(id=job_id, status="failed", message="Benchmark job state was not found.")

    def _upsert_job(self, job: ModelBenchmarkJobInfo) -> None:
        jobs = [existing for existing in self._load_jobs() if existing.id != job.id]
        jobs.insert(0, job)
        jobs = sorted(jobs, key=lambda item: item.created_at, reverse=True)[:100]
        self._write_json_list(self.jobs_path, [item.model_dump() for item in jobs])

    def _load_jobs(self) -> list[ModelBenchmarkJobInfo]:
        payload = self._read_json_list(self.jobs_path)
        jobs: list[ModelBenchmarkJobInfo] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                job = ModelBenchmarkJobInfo.model_validate(item)
            except (TypeError, ValueError):
                continue
            if not job.id:
                continue
            jobs.append(job)
        return jobs

    def _recover_interrupted_jobs(self) -> None:
        jobs = self._load_jobs()
        changed = False
        now = self._now()
        for job in jobs:
            if job.status in {"queued", "running", "cancel_requested"}:
                job.status = "interrupted"
                job.finished_at = job.finished_at or now
                job.message = "Benchmark job was interrupted by a backend restart."
                changed = True
        if changed:
            self._write_json_list(self.jobs_path, [item.model_dump() for item in jobs])

    def _load_results(self) -> list[ModelBenchmarkResult]:
        payload = self._read_json_list(self.results_path)
        results: list[ModelBenchmarkResult] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                results.append(ModelBenchmarkResult.model_validate(item))
            except (TypeError, ValueError):
                continue
        return results

    def _read_json_list(self, path: Path) -> list[Any]:
        try:
            if not path.exists() or not path.is_file() or path.stat().st_size > MAX_MODEL_BENCHMARK_JSON_BYTES:
                return []
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return payload if isinstance(payload, list) else []

    def _write_json_list(self, path: Path, payload: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp")
        try:
            tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
            tmp.replace(path)
        except OSError:
            try:
                if tmp.is_file():
                    tmp.unlink()
            except OSError:
                pass
            raise

    def _suite_score(self, latest_by_suite: dict[str, ModelBenchmarkResult], suite_id: str) -> float | None:
        result = latest_by_suite.get(suite_id)
        return result.score if result else None

    def _payload_text(self, payload: dict[str, Any]) -> str:
        try:
            return json.dumps(payload, ensure_ascii=True, sort_keys=True)
        except TypeError:
            return str(payload)

    def _excerpt(self, payload: dict[str, Any]) -> str:
        return self._payload_text(payload)[:320]

    def _confidence(self, value: Any) -> float | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if parsed < 0.0 or parsed > 1.0:
            return None
        return parsed

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
