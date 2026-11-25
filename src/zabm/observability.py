from __future__ import annotations

import json
import math
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from zabm.evaluation import EvaluationArtifact

DEFAULT_LANGSMITH_ENDPOINT = "https://api.smith.langchain.com"
DEFAULT_LANGSMITH_PROJECT = "zabm-evaluation"
DEFAULT_LANGSMITH_TIMEOUT_SECONDS = 10.0
MAX_LANGSMITH_TIMEOUT_SECONDS = 60.0
LANGSMITH_BATCH_SIZE = 100
LANGSMITH_MAX_ATTEMPTS = 2
LANGSMITH_BATCH_PATH = "/runs/batch"


class ObservabilityError(RuntimeError):
    pass


@dataclass(frozen=True)
class LangSmithConfiguration:
    api_key: str = field(repr=False)
    endpoint: str
    project: str
    timeout_seconds: float


@dataclass(frozen=True)
class LangSmithMirrorResult:
    run_count: int
    batch_count: int
    project: str


def langsmith_configuration(
    environ: Mapping[str, str],
) -> tuple[LangSmithConfiguration | None, str | None]:
    tracing = environ.get("LANGSMITH_TRACING", "").strip().lower()
    if tracing not in {"true", "1", "yes", "on"}:
        if tracing and tracing not in {"false", "0", "no", "off"}:
            return None, "LANGSMITH_TRACING must be true or false; LangSmith mirroring is disabled"
        return None, None

    api_key = environ.get("LANGSMITH_API_KEY", "").strip()
    if not api_key:
        api_key = environ.get("LANGCHAIN_API_KEY", "").strip()
    if not api_key:
        return None, (
            "LANGSMITH_TRACING is enabled but LANGSMITH_API_KEY is not set; "
            "local evaluation continues without remote mirroring"
        )

    endpoint = (
        environ.get("LANGSMITH_ENDPOINT", "").strip()
        or environ.get("LANGCHAIN_ENDPOINT", "").strip()
        or DEFAULT_LANGSMITH_ENDPOINT
    ).rstrip("/")
    if not endpoint.startswith(("https://", "http://")):
        return None, (
            "LANGSMITH_ENDPOINT must be an HTTP(S) URL; "
            "local evaluation continues without remote mirroring"
        )

    project = (
        environ.get("LANGSMITH_PROJECT", "").strip()
        or environ.get("LANGCHAIN_PROJECT", "").strip()
        or DEFAULT_LANGSMITH_PROJECT
    )
    timeout_seconds = _timeout_seconds(environ.get("LANGSMITH_TIMEOUT_SECONDS", ""))
    return (
        LangSmithConfiguration(
            api_key=api_key,
            endpoint=endpoint,
            project=project,
            timeout_seconds=timeout_seconds,
        ),
        None,
    )


def mirror_evaluation_to_langsmith(
    report: EvaluationArtifact,
    configuration: LangSmithConfiguration,
) -> LangSmithMirrorResult:
    runs = _langsmith_runs(report, configuration.project)
    deadline = time.monotonic() + configuration.timeout_seconds
    batch_count = 0
    for offset in range(0, len(runs), LANGSMITH_BATCH_SIZE):
        batch = runs[offset : offset + LANGSMITH_BATCH_SIZE]
        _post_batch(configuration, batch, deadline)
        batch_count += 1
    return LangSmithMirrorResult(
        run_count=len(runs),
        batch_count=batch_count,
        project=configuration.project,
    )


def _timeout_seconds(raw_value: str) -> float:
    if not raw_value:
        return DEFAULT_LANGSMITH_TIMEOUT_SECONDS
    try:
        value = float(raw_value)
    except ValueError:
        return DEFAULT_LANGSMITH_TIMEOUT_SECONDS
    if not math.isfinite(value) or value <= 0:
        return DEFAULT_LANGSMITH_TIMEOUT_SECONDS
    return min(value, MAX_LANGSMITH_TIMEOUT_SECONDS)


def _langsmith_runs(
    report: EvaluationArtifact,
    project: str,
) -> list[dict[str, Any]]:
    root_id = str(uuid4())
    occurrences = [
        item.response.timestamp
        for configuration in report.configurations
        for run in configuration.runs
        for item in run.items
    ]
    if occurrences:
        root_start = min(occurrences).astimezone(UTC)
        root_end = max(occurrences).astimezone(UTC)
    else:
        root_start = datetime.now(UTC)
        root_end = root_start

    root_metadata = _mirror_metadata(report)
    runs: list[dict[str, Any]] = [
        {
            "id": root_id,
            "name": "zabm-evaluation",
            "run_type": "chain",
            "start_time": _langsmith_time(root_start),
            "end_time": _langsmith_time(root_end),
            "inputs": {
                "evaluation_set_id": report.evaluation_set_id,
                "source_pack_id": report.source_pack_id,
                "provider": report.provider.provider,
                "model": report.provider.model,
                "configuration_id": report.configuration_id,
            },
            "outputs": {
                "artifact_version": report.artifact_version,
                "evaluation_set_id": report.evaluation_set_id,
                "source_pack_id": report.source_pack_id,
                "configuration_count": len(report.configurations),
            },
            "extra": {"metadata": root_metadata},
            "tags": ["zabm", "evaluation", report.source_pack_id],
            "trace_id": root_id,
            "session_name": project,
        }
    ]

    for configuration_result in report.configurations:
        for run in configuration_result.runs:
            configuration_run_id = str(uuid4())
            run_identifier = f"{configuration_result.id}:run-{run.run}"
            run_metadata = {
                **_mirror_metadata(report),
                "evaluation_run_id": run_identifier,
                "baseline_configuration": configuration_result.id,
                "seed": run.seed,
                "temperature": run.temperature,
                "answer_mode": configuration_result.answer_mode,
                "retrieval_mode": configuration_result.retrieval_mode,
            }
            item_times = [item.response.timestamp.astimezone(UTC) for item in run.items]
            run_start = min(item_times, default=root_start)
            run_end = max(item_times, default=root_end)
            runs.append(
                {
                    "id": configuration_run_id,
                    "name": f"zabm-evaluation:{run_identifier}",
                    "run_type": "chain",
                    "start_time": _langsmith_time(run_start),
                    "end_time": _langsmith_time(run_end),
                    "inputs": {
                        "evaluation_run_id": run_identifier,
                        "seed": run.seed,
                        "temperature": run.temperature,
                    },
                    "outputs": {
                        "evaluation_run_id": run_identifier,
                        "metrics": run.metrics.model_dump(mode="json"),
                        "spread": configuration_result.spread.model_dump(mode="json"),
                    },
                    "extra": {"metadata": run_metadata},
                    "tags": [
                        "zabm",
                        "evaluation",
                        run_identifier,
                        report.source_pack_id,
                    ],
                    "parent_run_id": root_id,
                    "trace_id": root_id,
                    "session_name": project,
                }
            )

            for item in run.items:
                item_end = item.response.timestamp.astimezone(UTC)
                item_start = item_end - timedelta(milliseconds=item.latency_ms)
                item_metadata = {
                    **run_metadata,
                    "evaluation_item_id": item.id,
                    "category": item.category,
                }
                runs.append(
                    {
                        "id": str(uuid4()),
                        "name": (f"zabm-evaluation-item:{run_identifier}:{item.id}"),
                        "run_type": "chain",
                        "start_time": _langsmith_time(item_start),
                        "end_time": _langsmith_time(item_end),
                        "inputs": {
                            "evaluation_run_id": run_identifier,
                            "evaluation_item_id": item.id,
                            "category": item.category,
                            "expected_status": item.expected_status,
                        },
                        "outputs": item.model_dump(mode="json"),
                        "extra": {"metadata": item_metadata},
                        "tags": [
                            "zabm",
                            "evaluation",
                            run_identifier,
                            item.id,
                            report.source_pack_id,
                        ],
                        "parent_run_id": configuration_run_id,
                        "trace_id": root_id,
                        "session_name": project,
                    }
                )
    return runs


def _mirror_metadata(report: EvaluationArtifact) -> dict[str, Any]:
    return {
        "provider": report.provider.provider,
        "model": report.provider.model,
        "embedding_model": report.provider.embedding_model,
        "configuration": report.provider.configuration,
        "configuration_id": report.configuration_id,
        "evaluation_set_id": report.evaluation_set_id,
        "source_pack_id": report.source_pack_id,
    }


def _langsmith_time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _post_batch(
    configuration: LangSmithConfiguration,
    runs: list[dict[str, Any]],
    deadline: float,
) -> None:
    payload = json.dumps({"post": runs, "patch": []}).encode()
    api_base = (
        configuration.endpoint
        if configuration.endpoint.endswith("/api/v1")
        else f"{configuration.endpoint}/api/v1"
    )
    request = Request(
        f"{api_base}{LANGSMITH_BATCH_PATH}",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": configuration.api_key,
            "User-Agent": "zabm-langsmith-mirror/1",
        },
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(LANGSMITH_MAX_ATTEMPTS):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            with urlopen(
                request,
                timeout=min(2.5, max(0.05, remaining)),
            ):
                return
        except HTTPError as exc:
            last_error = exc
            if 400 <= exc.code < 500:
                break
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = exc
        if attempt + 1 < LANGSMITH_MAX_ATTEMPTS:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.2, remaining))

    if time.monotonic() >= deadline:
        raise ObservabilityError(
            f"LangSmith mirror exceeded its {configuration.timeout_seconds:g}s deadline"
        )
    detail = str(last_error) if last_error is not None else "no response"
    detail = detail.replace(configuration.api_key, "<redacted>")
    raise ObservabilityError(f"LangSmith mirror request failed: {detail}")
