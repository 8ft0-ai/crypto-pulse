"""Repository-owned deterministic rendering for validated semantic claim plans."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import Any, Mapping, Sequence

from .claim_plan_validation import claim_source_disagreement_eligible
from .contracts import CLAIM_PLAN_RENDERER_VERSION
from .diagnostics import ValidationReport

_SECTION_HEADINGS = {
    "market_summary": "Market summary",
    "key_observations": "Key observations",
    "risks_and_limitations": "Risks and limitations",
    "data_quality": "Data quality",
    "source_status": "Source status",
}
_METRIC_LABELS = {
    "price_usd": "price",
    "price": "price",
    "bid": "bid price",
    "ask": "ask price",
    "change_1h_pct": "1-hour change",
    "change_24h_pct": "24-hour change",
    "change_7d_pct": "7-day change",
    "change_1d_pct": "1-day change",
    "market_cap_usd": "market capitalisation",
    "volume_24h_usd": "24-hour volume",
    "market_cap_rank": "market capitalisation rank",
    "total_tvl_usd": "total DeFi TVL",
    "circulating_usd": "circulating value",
    "last_updated": "last update",
    "source_time": "source time",
    "fetched_at_utc": "fetch time",
    "generated_at_utc": "generation time",
    "status": "status",
    "quality_status": "quality status",
    "covered_symbols": "covered symbols",
    "missing_symbols": "missing symbols",
    "coverage": "coverage",
    "warning": "warning",
    "warnings": "warnings",
    "reason": "reason",
    "message": "message",
}
_SOURCE_LABELS = {
    "binance": "Binance",
    "coingecko": "CoinGecko",
    "coinbase_exchange": "Coinbase Exchange",
    "defillama": "DefiLlama",
    "snapshot-validator": "snapshot validator",
    "source-snapshot": "source snapshot",
}
_DIRECTION_HORIZONS = {
    "change_1h_pct": "over 1 hour",
    "change_24h_pct": "over 24 hours",
    "change_7d_pct": "over 7 days",
    "change_1d_pct": "over 1 day",
}
_STATUS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_UTC_Z_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})T(?P<time>\d{2}:\d{2}:\d{2})(?P<fraction>\.\d+)?Z$"
)


class ClaimPlanRenderError(ValueError):
    """A validated plan still contains an unsupported rendering input."""

    def __init__(self, code: str, path: str, message: str):
        super().__init__(message)
        self.code = code
        self.path = path
        self.message = message


@dataclass(frozen=True)
class RenderedClaim:
    claim_id: str
    intent: str
    evidence_ids: tuple[str, ...]
    sentence: str

    def as_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "intent": self.intent,
            "evidence_ids": list(self.evidence_ids),
            "sentence": self.sentence,
        }


@dataclass(frozen=True)
class ClaimPlanRender:
    renderer_version: str
    markdown: bytes
    claims: tuple[RenderedClaim, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "renderer_version": self.renderer_version,
            "claims": [claim.as_dict() for claim in self.claims],
        }


@dataclass(frozen=True)
class _FormattedNumber:
    text: str
    rounded: bool

    @property
    def qualified(self) -> str:
        return f"approximately {self.text}" if self.rounded else self.text


def _plain(text: str) -> str:
    return " ".join(text.split())


def _escape(text: str) -> str:
    escaped = _plain(text).replace("\\", "\\\\")
    for character in "`*_[]<>#|":
        escaped = escaped.replace(character, "\\" + character)
    return escaped


def _code(text: str) -> str:
    return f"`{_plain(text).replace('`', 'ˋ')}`"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _evidence_map(bundle: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(item["evidence_id"]): item
        for item in _list(bundle.get("evidence"))
        if isinstance(item, Mapping) and isinstance(item.get("evidence_id"), str)
    }


def _subject_alias(item: Mapping[str, Any], path: str) -> str:
    subject = _mapping(item.get("subject"))
    if subject.get("type") == "snapshot":
        return "the source snapshot"
    name = subject.get("name")
    if isinstance(name, str) and name.strip():
        return _plain(name)
    symbol = subject.get("symbol")
    if isinstance(symbol, str) and symbol.strip():
        return _plain(symbol)
    raise ClaimPlanRenderError("missing_alias", path, "evidence subject has no approved display alias")


def _source_alias(item: Mapping[str, Any], path: str) -> str:
    name = _mapping(item.get("source")).get("name")
    if not isinstance(name, str) or name not in _SOURCE_LABELS:
        raise ClaimPlanRenderError("missing_source_alias", path, "evidence source has no approved display alias")
    return _SOURCE_LABELS[name]


def _metric_label(item: Mapping[str, Any], path: str) -> str:
    field = item.get("field")
    if not isinstance(field, str) or field not in _METRIC_LABELS:
        raise ClaimPlanRenderError("unsupported_metric", path, f"unsupported evidence field: {field!r}")
    return _METRIC_LABELS[field]


def _decimal(value: Any, path: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ClaimPlanRenderError("invalid_number", path, "numeric evidence must contain an integer or float")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ClaimPlanRenderError("invalid_number", path, "numeric evidence is not a finite decimal") from exc
    if not result.is_finite():
        raise ClaimPlanRenderError("invalid_number", path, "numeric evidence is not finite")
    return result


def _number(item: Mapping[str, Any], path: str, *, magnitude: bool = False) -> _FormattedNumber:
    value = _decimal(item.get("value"), path + ".value")
    if magnitude:
        value = abs(value)
    unit = item.get("unit")
    if unit == "usd":
        quantum = Decimal("0.01")
        rounded_value = value.quantize(quantum, rounding=ROUND_HALF_UP)
        rounded = rounded_value != value
        display = f"{rounded_value:,.2f}".rstrip("0").rstrip(".")
        return _FormattedNumber(f"US${display}", rounded)
    if unit == "percent":
        quantum = Decimal("0.01")
        rounded_value = value.quantize(quantum, rounding=ROUND_HALF_UP)
        rounded = rounded_value != value
        display = f"{rounded_value:,.2f}".rstrip("0").rstrip(".")
        return _FormattedNumber(f"{display}%", rounded)
    if unit == "rank":
        integral = value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        if integral != value:
            raise ClaimPlanRenderError("unsupported_rank_precision", path, "rank evidence must be an integer")
        return _FormattedNumber(f"#{integral:,.0f}", False)
    raise ClaimPlanRenderError("unsupported_unit", path, f"unsupported numeric unit: {unit!r}")


def _timestamp(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise ClaimPlanRenderError("invalid_timestamp", path, "timestamp evidence must be a string")
    match = _UTC_Z_RE.fullmatch(value)
    if match:
        return f"{match.group('date')} {match.group('time')}{match.group('fraction') or ''} UTC"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ClaimPlanRenderError("invalid_timestamp", path, "timestamp is not valid RFC 3339") from exc
    if parsed.tzinfo is None:
        raise ClaimPlanRenderError("invalid_timestamp", path, "timestamp must contain a timezone")
    utc = parsed.astimezone(timezone.utc)
    formatted = utc.strftime("%Y-%m-%d %H:%M:%S")
    if utc.microsecond:
        formatted += f".{utc.microsecond:06d}".rstrip("0")
    return formatted + " UTC"


def _status(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _STATUS_RE.fullmatch(value):
        raise ClaimPlanRenderError("unsupported_status", path, "status evidence is not a bounded status token")
    return value


def _set_value(value: Any, path: str) -> str:
    if not isinstance(value, list) or any(isinstance(item, (dict, list)) for item in value):
        raise ClaimPlanRenderError("unsupported_set", path, "set evidence must contain scalar values")
    return ", ".join(_escape(str(item)) for item in sorted(value, key=lambda item: str(item)))


def _absolute_clause(item: Mapping[str, Any], path: str) -> str:
    alias = _subject_alias(item, path)
    metric = _metric_label(item, path)
    evidence_type = item.get("evidence_type")
    if evidence_type == "number":
        return f"{alias} {metric} was {_number(item, path).qualified}"
    if evidence_type == "status":
        return f"{alias} {metric} was {_status(item.get('value'), path + '.value')}"
    if evidence_type == "timestamp":
        return f"{alias} {metric} was {_timestamp(item.get('value'), path + '.value')}"
    if evidence_type == "boolean":
        value = item.get("value")
        if not isinstance(value, bool):
            raise ClaimPlanRenderError("invalid_boolean", path, "boolean evidence must contain true or false")
        return f"{alias} {metric} was {'yes' if value else 'no'}"
    if evidence_type == "set":
        return f"{alias} {metric} were {_set_value(item.get('value'), path + '.value')}"
    raise ClaimPlanRenderError("unsupported_evidence_type", path, f"unsupported absolute evidence type: {evidence_type!r}")


def _absolute_sentence(evidence: Sequence[Mapping[str, Any]], path: str) -> str:
    if not evidence:
        raise ClaimPlanRenderError("missing_evidence", path, "absolute observation has no evidence")
    return "; ".join(_absolute_clause(item, f"{path}.evidence[{index}]") for index, item in enumerate(evidence)) + "."


def _directional_clause(item: Mapping[str, Any], path: str) -> str:
    alias = _subject_alias(item, path)
    field = item.get("field")
    if item.get("evidence_type") == "number":
        value = _decimal(item.get("value"), path + ".value")
        formatted = _number(item, path, magnitude=True).qualified
        horizon = _DIRECTION_HORIZONS.get(str(field))
        if horizon is None:
            raise ClaimPlanRenderError("unsupported_directional_metric", path, f"unsupported directional field: {field!r}")
        if value > 0:
            return f"{alias} increased by {formatted} {horizon}"
        if value < 0:
            return f"{alias} decreased by {formatted} {horizon}"
        return f"{alias} was unchanged at {formatted} {horizon}"
    if item.get("evidence_type") == "status":
        return f"{alias} direction was {_status(item.get('value'), path + '.value')}"
    raise ClaimPlanRenderError("unsupported_directional_evidence", path, "directional evidence must be numeric or status")


def _directional_sentence(evidence: Sequence[Mapping[str, Any]], path: str) -> str:
    if not evidence:
        raise ClaimPlanRenderError("missing_evidence", path, "directional observation has no evidence")
    return "; ".join(_directional_clause(item, f"{path}.evidence[{index}]") for index, item in enumerate(evidence)) + "."


def _comparison_sentence(
    claim: Mapping[str, Any], evidence: Sequence[Mapping[str, Any]], path: str
) -> str:
    if len(evidence) != 2:
        raise ClaimPlanRenderError("comparison_operand_count", path, "comparison requires exactly two evidence records")
    left, right = evidence
    relation = claim.get("comparison_relation")
    left_value = _number(left, path + ".left").qualified
    right_value = _number(right, path + ".right").qualified
    metric = _metric_label(left, path + ".left")
    if claim_source_disagreement_eligible(
        claim,
        {str(item["evidence_id"]): item for item in evidence},
    ):
        alias = _subject_alias(left, path + ".left")
        left_source = _source_alias(left, path + ".left")
        right_source = _source_alias(right, path + ".right")
        return (
            f"{alias} {metric} differed between {left_source} ({left_value}) "
            f"and {right_source} ({right_value})."
        )
    left_alias = _subject_alias(left, path + ".left")
    right_alias = _subject_alias(right, path + ".right")
    relation_text = {
        "greater_than": "was greater than",
        "less_than": "was less than",
        "approximately_equal": "was approximately equal to",
        "not_equal": "was not equal to",
        "opposite_direction": "moved in the opposite direction to",
    }.get(relation)
    if relation_text is None:
        raise ClaimPlanRenderError("unknown_relation", path, f"unsupported comparison relation: {relation!r}")
    return (
        f"{left_alias} {metric} ({left_value}) {relation_text} "
        f"{right_alias} {_metric_label(right, path + '.right')} ({right_value})."
    )


def _source_status_sentence(evidence: Sequence[Mapping[str, Any]], path: str) -> str:
    if not evidence:
        raise ClaimPlanRenderError("missing_evidence", path, "source status has no evidence")
    aliases = {_subject_alias(item, path) for item in evidence}
    if len(aliases) != 1:
        raise ClaimPlanRenderError("mixed_source_status", path, "one source-status claim cannot mix subjects")
    alias = next(iter(aliases))
    status_items = [item for item in evidence if item.get("field") == "status"]
    if len(status_items) != 1:
        raise ClaimPlanRenderError("source_status_cardinality", path, "source status requires exactly one status record")
    sentences = [f"{alias} source status was {_status(status_items[0].get('value'), path + '.status') }."]
    for item in evidence:
        if item.get("field") in {"reason", "message", "warning"}:
            value = item.get("value")
            if not isinstance(value, str):
                raise ClaimPlanRenderError("unsupported_source_detail", path, "source detail must be a string")
            sentences.append(f"Recorded source {_metric_label(item, path)}: {_escape(value)}.")
    return " ".join(sentences)


def _snapshot_status_sentence(evidence: Sequence[Mapping[str, Any]], path: str) -> str:
    status_items = [item for item in evidence if item.get("field") in {"status", "quality_status"}]
    if len(status_items) != 1:
        raise ClaimPlanRenderError("snapshot_status_cardinality", path, "snapshot status requires exactly one status record")
    if any(_mapping(item.get("subject")).get("type") != "snapshot" for item in evidence):
        raise ClaimPlanRenderError("snapshot_status_subject", path, "snapshot status cannot mix subjects")
    return f"The source snapshot status was {_status(status_items[0].get('value'), path + '.status')}."


def _data_quality_sentence(evidence: Sequence[Mapping[str, Any]], path: str) -> str:
    if not evidence:
        raise ClaimPlanRenderError("missing_evidence", path, "data-quality limitation has no evidence")
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for item in evidence:
        subject = _mapping(item.get("subject"))
        key = (str(subject.get("type", "")), str(subject.get("id", "")))
        groups.setdefault(key, []).append(item)
    sentences: list[str] = []
    for index, items in enumerate(groups.values()):
        alias = _subject_alias(items[0], f"{path}.group[{index}]")
        status_items = [item for item in items if item.get("field") in {"status", "quality_status"}]
        for item in status_items:
            value = _status(item.get("value"), f"{path}.group[{index}].status")
            if _mapping(item.get("subject")).get("type") == "source":
                sentences.append(f"Data quality was limited because {alias} source status was {value}.")
            else:
                sentences.append(f"Data quality was limited because the source snapshot status was {value}.")
        for item in items:
            field = item.get("field")
            if field in {"reason", "message", "warning"}:
                value = item.get("value")
                if not isinstance(value, str):
                    raise ClaimPlanRenderError("unsupported_quality_detail", path, "quality detail must be a string")
                sentences.append(f"Recorded {_metric_label(item, path)}: {_escape(value)}.")
            elif field == "missing_symbols":
                sentences.append(f"{alias} was missing coverage for {_set_value(item.get('value'), path)}.")
    if not sentences:
        raise ClaimPlanRenderError("unsupported_data_quality_evidence", path, "no deterministic limitation template supports the cited evidence")
    return " ".join(sentences)


def _render_claim(
    claim: Mapping[str, Any], evidence_by_id: Mapping[str, Mapping[str, Any]], path: str
) -> RenderedClaim:
    claim_id = claim.get("claim_id")
    intent = claim.get("intent")
    identifiers = tuple(item for item in _list(claim.get("evidence_ids")) if isinstance(item, str))
    if not isinstance(claim_id, str):
        raise ClaimPlanRenderError("missing_claim_id", path, "claim ID is missing")
    if not isinstance(intent, str):
        raise ClaimPlanRenderError("unknown_intent", path, "claim intent is missing")
    missing = [item for item in identifiers if item not in evidence_by_id]
    if missing:
        raise ClaimPlanRenderError("missing_evidence", path, f"missing cited evidence: {', '.join(missing)}")
    evidence = [evidence_by_id[item] for item in identifiers]
    if intent == "absolute_observation":
        sentence = _absolute_sentence(evidence, path)
    elif intent == "directional_observation":
        sentence = _directional_sentence(evidence, path)
    elif intent == "comparison":
        sentence = _comparison_sentence(claim, evidence, path)
    elif intent == "source_status":
        sentence = _source_status_sentence(evidence, path)
    elif intent == "data_quality_limitation":
        sentence = _data_quality_sentence(evidence, path)
    elif intent == "snapshot_status":
        sentence = _snapshot_status_sentence(evidence, path)
    else:
        raise ClaimPlanRenderError("unknown_intent", path, f"unsupported claim intent: {intent!r}")
    return RenderedClaim(claim_id, intent, identifiers, sentence)


def render_claim_plan(
    bundle: dict[str, Any], plan: dict[str, Any], report: ValidationReport
) -> ClaimPlanRender:
    """Render a validated plan into byte-stable Markdown and structured grounding."""

    if not report.is_valid:
        raise ClaimPlanRenderError("invalid_plan", "$.claim_plan", "claim-plan validation failed; no output was rendered")
    evidence_by_id = _evidence_map(bundle)
    sections_by_kind = {
        str(section.get("section_kind")): section
        for section in _list(plan.get("sections"))
        if isinstance(section, Mapping)
    }
    rendered_claims: list[RenderedClaim] = []
    lines = [
        "<!-- Deterministically rendered by llm_analysis.claim_plan_render; do not edit generated text. -->",
        "",
        "# Governed CryptoPulse market analysis",
        "",
        "> **Product boundaries**",
    ]
    for boundary in _list(bundle.get("product_boundaries")):
        if not isinstance(boundary, str):
            raise ClaimPlanRenderError("invalid_product_boundary", "$.bundle.product_boundaries", "product boundaries must be strings")
        lines.append(f"> - {_escape(boundary)}")

    for section_index, section_kind in enumerate(_list(plan.get("analysis_order"))):
        if not isinstance(section_kind, str) or section_kind not in _SECTION_HEADINGS:
            raise ClaimPlanRenderError("unknown_section", "$.claim_plan.analysis_order", f"unsupported section: {section_kind!r}")
        section = sections_by_kind.get(section_kind)
        if section is None:
            raise ClaimPlanRenderError("missing_section", "$.claim_plan.sections", f"missing section: {section_kind}")
        lines.extend(["", f"## {_SECTION_HEADINGS[section_kind]}", ""])
        claims = _list(section.get("claims"))
        if not claims:
            raise ClaimPlanRenderError("empty_section", f"$.claim_plan.sections[{section_index}]", "rendered sections cannot be empty")
        for claim_index, claim in enumerate(claims):
            if not isinstance(claim, Mapping):
                raise ClaimPlanRenderError("invalid_claim", f"$.claim_plan.sections[{section_index}].claims[{claim_index}]", "claim must be an object")
            rendered = _render_claim(
                claim,
                evidence_by_id,
                f"$.claim_plan.sections[{section_index}].claims[{claim_index}]",
            )
            rendered_claims.append(rendered)
            lines.extend(
                [
                    f"- {_escape(rendered.sentence)}",
                    f"  - Claim ID: {_code(rendered.claim_id)}",
                    f"  - Intent: {_code(rendered.intent)}",
                    f"  - Confidence: {_code(str(claim.get('confidence')))}",
                    f"  - Evidence: {', '.join(_code(item) for item in rendered.evidence_ids)}",
                ]
            )

    lines.extend(
        [
            "",
            "---",
            "",
            f"Evidence bundle: {_code(str(plan.get('evidence_bundle_id')))}  ",
            f"Claim-plan schema: {_code(str(plan.get('claim_plan_version')))}  ",
            f"Prompt version: {_code(str(plan.get('prompt_version')))}  ",
            f"Renderer version: {_code(CLAIM_PLAN_RENDERER_VERSION)}",
            "",
        ]
    )
    markdown = "\n".join(lines).encode("utf-8")
    return ClaimPlanRender(CLAIM_PLAN_RENDERER_VERSION, markdown, tuple(rendered_claims))
