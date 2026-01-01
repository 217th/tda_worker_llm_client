from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping, Sequence

from worker_llm_client.artifacts.domain import GcsUri, InvalidGcsUri
from worker_llm_client.artifacts.services import ArtifactStore
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
    ) -> ResolvedUserInput:
        # Resolve *all* upstream context referenced by LLM_REPORT inputs.
        # This produces a fully materialized snapshot that can be rendered into
        # the final UserInput section (text + optional chart images).
        symbol = _extract_symbol(flow_run)
        timeframe = _extract_timeframe(step)

        # Load JSON artifacts from GCS, validate size/UTF-8/JSON, and normalize
        # to a canonical JSON string for deterministic prompt injection.
        ohlcv = _load_json_artifact(
            self._artifact_store,
            inputs.ohlcv_gcs_uri,
            label="ohlcv",
            max_bytes=self._max_json_bytes,
        )
        charts_manifest = _load_json_artifact(
            self._artifact_store,
            inputs.charts_manifest_gcs_uri,
            label="charts_manifest",
            max_bytes=self._max_json_bytes,
        )

        # Chart images are optional, but the manifest must contain at least one
        # valid image URI; otherwise the step is invalid.
        chart_images = _load_chart_images(
            self._artifact_store,
            charts_manifest.data,
            max_bytes=self._max_chart_image_bytes,
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
        lines.append("## UserInput")
        lines.append("")
        lines.append(f"Symbol: {resolved.symbol}")
        lines.append(f"Timeframe: {resolved.timeframe}")
        lines.append("")
        lines.append("### OHLCV (time series)")
        lines.append(f"Source: {resolved.ohlcv.uri}")
        lines.append("```json")
        lines.append(resolved.ohlcv.payload)
        lines.append("```")
        lines.append("")
        lines.append("### Charts (images)")
        if resolved.chart_images:
            for chart in resolved.chart_images:
                lines.append(f"- {chart.description} (uri: {chart.uri})")
        else:
            lines.append("- (no charts available)")
        lines.append("")
        lines.append("### Charts manifest (JSON)")
        lines.append(f"Source: {resolved.charts_manifest.uri}")
        lines.append("```json")
        lines.append(resolved.charts_manifest.payload)
        lines.append("```")
        lines.append("")
        lines.append("### Previous reports")
        if resolved.previous_reports:
            for report in resolved.previous_reports:
                label = report.step_id or "external"
                lines.append(f"- {label} (uri: {report.artifact.uri})")
                lines.append("```json")
                lines.append(report.artifact.payload)
                lines.append("```")
        else:
            lines.append("(none)")

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


def _extract_timeframe(step: LLMReportStep) -> str:
    raw = step.step.raw
    if not isinstance(raw, Mapping):
        raise InvalidStepInputs("step.timeframe is required")
    timeframe = raw.get("timeframe")
    if not isinstance(timeframe, str) or not timeframe.strip():
        raise InvalidStepInputs("step.timeframe is required")
    return timeframe.strip()


def _load_json_artifact(
    store: ArtifactStore, uri: str, *, label: str, max_bytes: int
) -> JsonArtifact:
    # Reads a JSON artifact from GCS and enforces:
    # - valid gs:// URI
    # - max size limit (raw bytes)
    # - UTF-8 decoding
    # - valid JSON parse
    # It then re-serializes the JSON with sorted keys for stable prompt output.
    gcs_uri = _parse_gcs_uri(uri, label=label)
    payload = store.read_bytes(gcs_uri)
    if len(payload) > max_bytes:
        raise InvalidStepInputs(f"{label} exceeds maxContextBytesPerJsonArtifact")
    text = _decode_utf8(payload, label=label)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidStepInputs(f"{label} must be valid JSON") from exc
    normalized = json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return JsonArtifact(
        uri=str(gcs_uri),
        payload=normalized,
        bytes_len=len(payload),
        data=parsed,
    )


def _load_chart_images(
    store: ArtifactStore, manifest_data: Any, *, max_bytes: int
) -> list[ChartImage]:
    # Parse the charts manifest and load image bytes from GCS. The manifest is
    # expected to be a JSON object containing an array of items under one of the
    # accepted keys (items/charts/images). Each item can expose a URI directly
    # or nested under an "artifact" object.
    if not isinstance(manifest_data, Mapping):
        raise InvalidStepInputs("charts manifest must be an object")

    items = _extract_manifest_items(manifest_data)
    images: list[ChartImage] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        uri = _extract_chart_uri(item)
        if uri is None:
            continue
        description = _extract_chart_description(item)
        gcs_uri = _parse_gcs_uri(uri, label="chart_image")
        data = store.read_bytes(gcs_uri)
        if len(data) > max_bytes:
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

    # The manifest must point to at least one valid image to be considered usable.
    if not images:
        raise InvalidStepInputs("charts manifest contains no valid image URIs")

    return images


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
