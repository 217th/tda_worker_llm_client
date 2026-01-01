from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Mapping, Sequence

from worker_llm_client.artifacts.domain import GcsUri, InvalidGcsUri
from worker_llm_client.artifacts.services import ArtifactStore
from worker_llm_client.ops.logging import EventLogger
from worker_llm_client.workflow.domain import (
    FlowRun,
    InvalidStepInputs,
    LLMReportInputs,
    LLMReportStep,
)


# Hard limits used during prompt/context assembly.
# These enforce the contract in spec/prompt_storage_and_context.md and prevent
# oversized artifacts from being injected into the model request.
MAX_CONTEXT_BYTES_PER_JSON_ARTIFACT = 65536
MAX_CHART_IMAGE_BYTES = 262144


@dataclass(frozen=True, slots=True)
class JsonArtifact:
    uri: str
    payload: str
    bytes_len: int
    data: Any


@dataclass(frozen=True, slots=True)
class ChartImage:
    uri: str
    description: str
    mime_type: str
    data: bytes
    bytes_len: int


@dataclass(frozen=True, slots=True)
class PreviousReport:
    step_id: str | None
    artifact: JsonArtifact


@dataclass(frozen=True, slots=True)
class ResolvedUserInput:
    symbol: str
    timeframe: str
    ohlcv: JsonArtifact
    charts_manifest: JsonArtifact
    chart_images: tuple[ChartImage, ...]
    previous_reports: tuple[PreviousReport, ...]


@dataclass(frozen=True, slots=True)
class UserInputPayload:
    text: str
    chart_images: tuple[ChartImage, ...]


class UserInputAssembler:
    def __init__(
        self,
        *,
        artifact_store: ArtifactStore,
        max_json_bytes: int = MAX_CONTEXT_BYTES_PER_JSON_ARTIFACT,
        max_chart_image_bytes: int = MAX_CHART_IMAGE_BYTES,
    ) -> None:
        self._artifact_store = artifact_store
        self._max_json_bytes = max_json_bytes
        self._max_chart_image_bytes = max_chart_image_bytes

    def resolve(
        self,
        *,
        flow_run: FlowRun,
        step: LLMReportStep,
        inputs: LLMReportInputs,
        event_logger: EventLogger | None = None,
        event_id: str | None = None,
    ) -> ResolvedUserInput:
        # Resolve *all* upstream context referenced by LLM_REPORT inputs.
        # This produces a fully materialized snapshot that can be rendered into
        # the final UserInput section (text + optional chart images).
        run_id = _extract_run_id(flow_run)
        step_id = step.step.step_id
        event_id = event_id or "unknown"
        symbol = _extract_symbol(flow_run)
        timeframe = _extract_timeframe(step)

        # Load JSON artifacts from GCS, validate size/UTF-8/JSON, and normalize
        # to a canonical JSON string for deterministic prompt injection.
        ohlcv = _load_json_artifact(
            self._artifact_store,
            inputs.ohlcv_gcs_uri,
            label="ohlcv",
            max_bytes=self._max_json_bytes,
            event_logger=event_logger,
            event_id=event_id,
            run_id=run_id,
            step_id=step_id,
        )
        charts_manifest = _load_json_artifact(
            self._artifact_store,
            inputs.charts_manifest_gcs_uri,
            label="charts_manifest",
            max_bytes=self._max_json_bytes,
            event_logger=event_logger,
            event_id=event_id,
            run_id=run_id,
            step_id=step_id,
        )

        # Chart images are optional, but the manifest must contain at least one
        # valid image URI; otherwise the step is invalid.
        chart_images = _load_chart_images(
            self._artifact_store,
            charts_manifest.data,
            max_bytes=self._max_chart_image_bytes,
            event_logger=event_logger,
            event_id=event_id,
            run_id=run_id,
            step_id=step_id,
        )

        # Previous reports may be referenced by stepId or external GCS URI.
        # Each reference is loaded and normalized as JSON for prompt context.
        previous_reports = []
        for ref in inputs.previous_report_refs:
            step_id = ref.step_id
            label = step_id or "external"
            report = _load_json_artifact(
                self._artifact_store,
                ref.gcs_uri,
                label=f"previous_report:{label}",
                max_bytes=self._max_json_bytes,
                event_logger=event_logger,
                event_id=event_id,
                run_id=run_id,
                step_id=step.step.step_id,
            )
            previous_reports.append(PreviousReport(step_id=step_id, artifact=report))

        return ResolvedUserInput(
            symbol=symbol,
            timeframe=timeframe,
            ohlcv=ohlcv,
            charts_manifest=charts_manifest,
            chart_images=tuple(chart_images),
            previous_reports=tuple(previous_reports),
        )

    def assemble(self, *, base_user_prompt: str, resolved: ResolvedUserInput) -> UserInputPayload:
        # Compose the final user prompt by appending a deterministic "UserInput"
        # section that includes:
        # - basic scope (symbol + timeframe)
        # - JSON artifacts (OHLCV + charts manifest + previous reports)
        # - a human-readable list of chart images (actual bytes returned separately)
        if not isinstance(base_user_prompt, str) or not base_user_prompt.strip():
            raise InvalidStepInputs("userPrompt must be a non-empty string")

        lines: list[str] = []
        lines.append(base_user_prompt.rstrip())
        lines.append("")
        lines.append("## UserInput:")
        lines.append("")
        lines.append("Метаданные:")
        lines.append(f"- symbol: {resolved.symbol}")
        lines.append(f"- timeframe: {resolved.timeframe}")
        lines.append("")
        lines.append("### OHLCV (time series)")
        request_ts = _extract_ohlcv_request_timestamp(resolved.ohlcv.data)
        lines.append(f"- request_timestamp: {request_ts}")
        lines.append("- data:")
        lines.append("```json")
        lines.append(_render_ohlcv_data(resolved.ohlcv))
        lines.append("```")
        lines.append("")
        lines.append("### Charts (images)")
        generated_at = _extract_charts_generated_at(resolved.charts_manifest.data)
        lines.append(f"- generated_at: {generated_at}")
        chart_entries = _extract_chart_entries(resolved.charts_manifest.data)
        for entry in chart_entries:
            lines.append(f"- {entry.template_id}: {entry.kind}")
        lines.append("")
        if resolved.previous_reports:
            lines.append("### Previous reports")
            for report in resolved.previous_reports:
                label = report.step_id or "external"
                lines.append(f"- {label} (uri: {report.artifact.uri})")
                lines.append("```json")
                lines.append(report.artifact.payload)
                lines.append("```")

        # Return a text payload for the prompt, plus any chart images that will
        # be attached as separate binary parts by the LLM client.
        return UserInputPayload(text="\n".join(lines).strip() + "\n", chart_images=resolved.chart_images)


def _extract_symbol(flow_run: FlowRun) -> str:
    raw = flow_run.raw if isinstance(flow_run.raw, Mapping) else {}
    scope = raw.get("scope")
    if not isinstance(scope, Mapping):
        raise InvalidStepInputs("flow_run.scope is required")
    symbol = scope.get("symbol")
    if not isinstance(symbol, str) or not symbol.strip():
        raise InvalidStepInputs("flow_run.scope.symbol is required")
    return symbol.strip()


def _extract_run_id(flow_run: FlowRun) -> str:
    if flow_run.run_id:
        return flow_run.run_id
    raw = flow_run.raw if isinstance(flow_run.raw, Mapping) else {}
    run_id = raw.get("runId")
    return run_id.strip() if isinstance(run_id, str) and run_id.strip() else "unknown"


def _extract_timeframe(step: LLMReportStep) -> str:
    raw = step.step.raw
    if not isinstance(raw, Mapping):
        raise InvalidStepInputs("step.timeframe is required")
    timeframe = raw.get("timeframe")
    if not isinstance(timeframe, str) or not timeframe.strip():
        raise InvalidStepInputs("step.timeframe is required")
    return timeframe.strip()


def _extract_ohlcv_request_timestamp(data: Any) -> str:
    if isinstance(data, Mapping):
        meta = data.get("metadata")
        if isinstance(meta, Mapping):
            for key in ("request_timestamp", "requestTimestamp"):
                value = meta.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return "unknown"


def _render_ohlcv_data(artifact: JsonArtifact) -> str:
    data = artifact.data
    if isinstance(data, Mapping) and "data" in data:
        payload = data.get("data")
        return _normalize_json(payload)
    return artifact.payload


@dataclass(frozen=True, slots=True)
class ChartEntry:
    template_id: str
    kind: str


def _extract_charts_generated_at(manifest_data: Any) -> str:
    if isinstance(manifest_data, Mapping):
        for key in ("generated_at", "generatedAt", "created_at", "createdAt"):
            value = manifest_data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "unknown"


def _extract_chart_entries(manifest_data: Any) -> list[ChartEntry]:
    if not isinstance(manifest_data, Mapping):
        return [ChartEntry(template_id="unknown_template", kind="chart")]
    items = []
    try:
        items = list(_extract_manifest_items(manifest_data))
    except InvalidStepInputs:
        return [ChartEntry(template_id="unknown_template", kind="chart")]
    entries: list[ChartEntry] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        template_id = _extract_chart_template_id(item)
        kind = _extract_chart_kind(item)
        entries.append(ChartEntry(template_id=template_id, kind=kind))
    if not entries:
        entries.append(ChartEntry(template_id="unknown_template", kind="chart"))
    return entries


def _load_json_artifact(
    store: ArtifactStore,
    uri: str,
    *,
    label: str,
    max_bytes: int,
    event_logger: EventLogger | None,
    event_id: str,
    run_id: str,
    step_id: str,
) -> JsonArtifact:
    # Reads a JSON artifact from GCS and enforces:
    # - valid gs:// URI
    # - max size limit (raw bytes)
    # - UTF-8 decoding
    # - valid JSON parse
    # It then re-serializes the JSON with sorted keys for stable prompt output.
    gcs_uri = _parse_gcs_uri(uri, label=label)
    _log_event(
        event_logger,
        event="gcs_read_started",
        severity="INFO",
        eventId=event_id,
        runId=run_id,
        stepId=step_id,
        gcs_uri=str(gcs_uri),
        kind=label,
    )
    started = time.monotonic()
    try:
        payload = store.read_bytes(gcs_uri)
    except Exception as exc:
        _log_event(
            event_logger,
            event="gcs_read_finished",
            severity="ERROR",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            gcs_uri=str(gcs_uri),
            kind=label,
            ok=False,
            error={"type": exc.__class__.__name__},
            durationMs=int((time.monotonic() - started) * 1000),
        )
        raise
    _log_event(
        event_logger,
        event="gcs_read_finished",
        severity="INFO",
        eventId=event_id,
        runId=run_id,
        stepId=step_id,
        gcs_uri=str(gcs_uri),
        kind=label,
        ok=True,
        bytes=len(payload),
        durationMs=int((time.monotonic() - started) * 1000),
    )
    if len(payload) > max_bytes:
        _log_event(
            event_logger,
            event="context_json_too_large",
            severity="WARNING",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            kind=label,
            bytes=len(payload),
            maxBytes=max_bytes,
        )
        raise InvalidStepInputs(f"{label} exceeds maxContextBytesPerJsonArtifact")
    text = _decode_utf8(payload, label=label)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        _log_event(
            event_logger,
            event="context_json_invalid",
            severity="WARNING",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            kind=label,
            error={"type": exc.__class__.__name__},
        )
        raise InvalidStepInputs(f"{label} must be valid JSON") from exc
    normalized = json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    _log_event(
        event_logger,
        event="context_json_validated",
        severity="INFO",
        eventId=event_id,
        runId=run_id,
        stepId=step_id,
        kind=label,
        bytes=len(payload),
        normalizedBytes=len(normalized.encode("utf-8")),
    )
    return JsonArtifact(
        uri=str(gcs_uri),
        payload=normalized,
        bytes_len=len(payload),
        data=parsed,
    )


def _load_chart_images(
    store: ArtifactStore,
    manifest_data: Any,
    *,
    max_bytes: int,
    event_logger: EventLogger | None,
    event_id: str,
    run_id: str,
    step_id: str,
) -> list[ChartImage]:
    # Parse the charts manifest and load image bytes from GCS. The manifest is
    # expected to be a JSON object containing an array of items under one of the
    # accepted keys (items/charts/images). Each item can expose a URI directly
    # or nested under an "artifact" object.
    if not isinstance(manifest_data, Mapping):
        raise InvalidStepInputs("charts manifest must be an object")

    items = _extract_manifest_items(manifest_data)
    items_with_uri = 0
    images: list[ChartImage] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        uri = _extract_chart_uri(item)
        if uri is None:
            continue
        items_with_uri += 1
        description = _extract_chart_description(item)
        gcs_uri = _parse_gcs_uri(uri, label="chart_image")
        _log_event(
            event_logger,
            event="gcs_read_started",
            severity="INFO",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            gcs_uri=str(gcs_uri),
            kind="chart_image",
        )
        started = time.monotonic()
        try:
            data = store.read_bytes(gcs_uri)
        except Exception as exc:
            _log_event(
                event_logger,
                event="gcs_read_finished",
                severity="ERROR",
                eventId=event_id,
                runId=run_id,
                stepId=step_id,
                gcs_uri=str(gcs_uri),
                kind="chart_image",
                ok=False,
                error={"type": exc.__class__.__name__},
                durationMs=int((time.monotonic() - started) * 1000),
            )
            raise
        _log_event(
            event_logger,
            event="gcs_read_finished",
            severity="INFO",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            gcs_uri=str(gcs_uri),
            kind="chart_image",
            ok=True,
            bytes=len(data),
            durationMs=int((time.monotonic() - started) * 1000),
        )
        if len(data) > max_bytes:
            _log_event(
                event_logger,
                event="chart_image_too_large",
                severity="WARNING",
                eventId=event_id,
                runId=run_id,
                stepId=step_id,
                gcs_uri=str(gcs_uri),
                bytes=len(data),
                maxBytes=max_bytes,
            )
            raise InvalidStepInputs("chart image exceeds maxChartImageBytes")
        images.append(
            ChartImage(
                uri=str(gcs_uri),
                description=description,
                mime_type="image/png",
                data=data,
                bytes_len=len(data),
            )
        )
        _log_event(
            event_logger,
            event="chart_image_loaded",
            severity="INFO",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            gcs_uri=str(gcs_uri),
            bytes=len(data),
        )

    _log_event(
        event_logger,
        event="charts_manifest_parsed",
        severity="INFO",
        eventId=event_id,
        runId=run_id,
        stepId=step_id,
        itemsTotal=len(items),
        itemsWithUri=items_with_uri,
    )
    # The manifest must point to at least one valid image to be considered usable.
    if not images:
        _log_event(
            event_logger,
            event="charts_manifest_no_images",
            severity="WARNING",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            itemsTotal=len(items),
        )
        raise InvalidStepInputs("charts manifest contains no valid image URIs")

    return images


def _log_event(event_logger: EventLogger | None, **payload: Any) -> None:
    if event_logger is None:
        return
    event_logger.log(**payload)


def _extract_manifest_items(manifest: Mapping[str, Any]) -> Sequence[Any]:
    items = manifest.get("items")
    if items is None:
        items = manifest.get("charts")
    if items is None:
        items = manifest.get("images")
    if items is None:
        raise InvalidStepInputs("charts manifest must include items")
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
        raise InvalidStepInputs("charts manifest items must be an array")
    return items


def _extract_chart_uri(item: Mapping[str, Any]) -> str | None:
    for key in ("gcsUri", "gcs_uri", "pngGcsUri", "png_gcs_uri", "imageGcsUri", "uri"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    artifact = item.get("artifact")
    if isinstance(artifact, Mapping):
        for key in ("gcsUri", "gcs_uri", "pngGcsUri", "png_gcs_uri", "uri"):
            value = artifact.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _extract_chart_template_id(item: Mapping[str, Any]) -> str:
    for key in ("templateId", "chartTemplateId", "chart_template_id"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    artifact = item.get("artifact")
    if isinstance(artifact, Mapping):
        for key in ("templateId", "chartTemplateId", "chart_template_id"):
            value = artifact.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "unknown_template"


def _extract_chart_kind(item: Mapping[str, Any]) -> str:
    for key in ("kind", "description"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "chart"


def _extract_chart_description(item: Mapping[str, Any]) -> str:
    for key in ("description", "chartTemplateId", "kind", "templateId"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "chart"


def _parse_gcs_uri(uri: str, *, label: str) -> GcsUri:
    try:
        return GcsUri.parse(uri)
    except InvalidGcsUri as exc:
        raise InvalidStepInputs(f"{label} must be a valid gs:// URI") from exc


def _decode_utf8(payload: bytes, *, label: str) -> str:
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidStepInputs(f"{label} must be utf-8 JSON") from exc


def _normalize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
