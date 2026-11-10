"""Canonical report chronology for reader-facing report-recency claims."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DETERMINISTIC_SCHEMA = "deterministic-crypto-report/v1"
DETERMINISTIC_NAME_RE = re.compile(r"^(?P<hhmm>\d{4})_(?P<tz>AEDT|AEST|UTC|[A-Z]{2,5})\.md$")
LEGACY_NAME_RE = re.compile(
    r"^(?P<hhmm>\d{4})_(?P<tz>AEDT|AEST|UTC|[A-Z]{2,5})_crypto_market_intelligence\.md$"
)
LEGACY_TIMESTAMP_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<hour>\d{2}):(?P<minute>\d{2})\s+(?P<tz>AEST|AEDT|UTC)$"
)
FIXED_OFFSETS = {
    "UTC": timezone.utc,
    "AEST": timezone(timedelta(hours=10), name="AEST"),
    "AEDT": timezone(timedelta(hours=11), name="AEDT"),
}


class ReportChronologyError(ValueError):
    """Raised when a retained report cannot be ordered safely."""


def _metadata(report: Any) -> dict[str, Any]:
    value = getattr(report, "metadata", None)
    if not isinstance(value, dict):
        raise ReportChronologyError("report metadata must be a mapping")
    return value


def _source_rel(report: Any) -> str:
    value = getattr(report, "source_rel", None)
    if not isinstance(value, str) or not value:
        raise ReportChronologyError("report source path is unavailable")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or len(path.parts) < 4:
        raise ReportChronologyError("report source path is invalid")
    return value


def _path_identity(report: Any, pattern: re.Pattern[str]) -> tuple[str, str, str]:
    path = PurePosixPath(_source_rel(report))
    match = pattern.fullmatch(path.name)
    if match is None or len(path.parts) < 4:
        raise ReportChronologyError(f"unsupported report path: {path.as_posix()}")
    try:
        year, month, day = path.parts[-4], path.parts[-3], path.parts[-2]
        datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
    except ValueError as exc:
        raise ReportChronologyError(f"invalid report date path: {path.as_posix()}") from exc
    hhmm = match.group("hhmm")
    try:
        datetime.strptime(hhmm, "%H%M")
    except ValueError as exc:
        raise ReportChronologyError(f"invalid report clock path: {path.as_posix()}") from exc
    return f"{year}-{month}-{day}", hhmm, match.group("tz")


def _parse_aware_iso(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ReportChronologyError(f"{field} must be a non-empty timestamp")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ReportChronologyError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReportChronologyError(f"{field} must include an explicit timezone")
    return parsed


def _legacy_time(value: Any, field: str) -> tuple[datetime, str]:
    if isinstance(value, datetime):
        parsed = value
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ReportChronologyError(f"{field} must include an explicit timezone")
        return parsed.astimezone(timezone.utc), parsed.tzname() or "UTC"
    if not isinstance(value, str) or not value.strip():
        raise ReportChronologyError(f"{field} must be a non-empty string")
    text = value.strip()
    match = LEGACY_TIMESTAMP_RE.fullmatch(text)
    if match:
        abbreviation = match.group("tz")
        tzinfo = FIXED_OFFSETS[abbreviation]
        try:
            local = datetime.strptime(
                f"{match.group('date')} {match.group('hour')}:{match.group('minute')}",
                "%Y-%m-%d %H:%M",
            ).replace(tzinfo=tzinfo)
        except ValueError as exc:
            raise ReportChronologyError(f"{field} is invalid") from exc
        return local.astimezone(timezone.utc), abbreviation

    parsed = _parse_aware_iso(text, field)
    return parsed.astimezone(timezone.utc), parsed.tzname() or "UTC"


def _legacy_timestamp(value: Any) -> tuple[datetime, str, str]:
    canonical_utc, abbreviation = _legacy_time(value, "legacy timestamp")
    parsed = canonical_utc.astimezone(FIXED_OFFSETS.get(abbreviation, timezone.utc))
    return canonical_utc, parsed.strftime("%Y-%m-%d %H:%M"), abbreviation


def _path_local(date_text: str, hhmm: str, abbreviation: str) -> datetime:
    tzinfo = FIXED_OFFSETS.get(abbreviation)
    if tzinfo is None:
        raise ReportChronologyError(f"unsupported legacy path timezone: {abbreviation}")
    try:
        return datetime.strptime(f"{date_text} {hhmm}", "%Y-%m-%d %H%M").replace(tzinfo=tzinfo)
    except ValueError as exc:
        raise ReportChronologyError("legacy path timestamp is invalid") from exc


def _deterministic_identity(report: Any) -> tuple[datetime, str, str, str]:
    metadata = _metadata(report)
    generated_utc = _parse_aware_iso(metadata.get("generated_at_utc"), "generated_at_utc")
    if generated_utc.utcoffset() != timedelta(0):
        raise ReportChronologyError("generated_at_utc must be UTC")
    canonical_utc = generated_utc.astimezone(timezone.utc)

    path_date, path_hhmm, path_tz = _path_identity(report, DETERMINISTIC_NAME_RE)
    path_local = _path_local(path_date, path_hhmm, path_tz)
    if path_local.astimezone(timezone.utc).replace(second=0, microsecond=0) != canonical_utc.replace(
        second=0, microsecond=0
    ):
        raise ReportChronologyError("deterministic report path contradicts generated_at_utc")

    local_value = metadata.get("generated_at_local")
    local = _parse_aware_iso(local_value, "generated_at_local") if local_value is not None else None
    timezone_name = metadata.get("timezone")
    abbreviation = metadata.get("timezone_abbreviation")

    expected_local = None
    if timezone_name is not None:
        if not isinstance(timezone_name, str) or not timezone_name.strip():
            raise ReportChronologyError("timezone must be a non-empty string")
        try:
            expected_local = canonical_utc.astimezone(ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError as exc:
            raise ReportChronologyError("timezone is unsupported") from exc

    if local is not None:
        if local.astimezone(timezone.utc) != canonical_utc:
            raise ReportChronologyError("generated_at_local contradicts generated_at_utc")
        if expected_local is not None and (
            local.replace(tzinfo=None) != expected_local.replace(tzinfo=None)
            or local.utcoffset() != expected_local.utcoffset()
        ):
            raise ReportChronologyError("generated_at_local contradicts timezone")

    display_local = expected_local or local or path_local
    display_abbreviation = abbreviation or display_local.tzname() or path_tz
    if abbreviation is not None:
        if not isinstance(abbreviation, str) or not abbreviation:
            raise ReportChronologyError("timezone_abbreviation must be a non-empty string")
        if display_local.tzname() != abbreviation:
            raise ReportChronologyError("timezone_abbreviation contradicts report time")
    if path_tz != display_abbreviation:
        raise ReportChronologyError("deterministic report path timezone contradicts metadata")
    if path_date != display_local.strftime("%Y-%m-%d") or path_hhmm != display_local.strftime("%H%M"):
        raise ReportChronologyError("deterministic report path contradicts generated timestamp")

    display = f"{display_local:%Y-%m-%d %H:%M} {display_abbreviation}"
    return canonical_utc, display, display_local.strftime("%H:%M"), display_abbreviation


def _legacy_identity(report: Any) -> tuple[datetime, str, str, str]:
    metadata = _metadata(report)
    path_date, path_hhmm, path_tz = _path_identity(report, LEGACY_NAME_RE)
    path_local = _path_local(path_date, path_hhmm, path_tz)
    path_utc = path_local.astimezone(timezone.utc)

    if metadata.get("timestamp") is not None:
        canonical_utc, _display_base, timestamp_tz = _legacy_timestamp(metadata["timestamp"])
        if canonical_utc != path_utc:
            raise ReportChronologyError("legacy timestamp contradicts report path")
        if timestamp_tz in FIXED_OFFSETS and timestamp_tz != path_tz:
            raise ReportChronologyError("legacy timestamp timezone contradicts report path")
    else:
        canonical_utc = path_utc

    display = f"{path_local:%Y-%m-%d %H:%M} {path_tz}"
    return canonical_utc, display, path_local.strftime("%H:%M"), path_tz


def _canonical_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalised_legacy_alias_metadata(report: Any, canonical_utc: datetime) -> dict[str, Any]:
    metadata = dict(_metadata(report))
    if metadata.get("timestamp") is None:
        raise ReportChronologyError("legacy alias timestamp is required")
    timestamp_utc, _timestamp_tz = _legacy_time(metadata["timestamp"], "legacy alias timestamp")
    if timestamp_utc != canonical_utc:
        raise ReportChronologyError("legacy alias timestamp contradicts canonical report instant")
    metadata["timestamp"] = _canonical_text(timestamp_utc)

    if "data_cutoff" in metadata:
        cutoff_utc, _cutoff_tz = _legacy_time(metadata["data_cutoff"], "legacy alias data_cutoff")
        if cutoff_utc != canonical_utc:
            raise ReportChronologyError("legacy alias data_cutoff contradicts canonical report instant")
        metadata["data_cutoff"] = _canonical_text(cutoff_utc)
    return metadata


def _archived_body_bytes(report: Any) -> bytes:
    source_path = getattr(report, "source_path", None)
    if not isinstance(source_path, Path):
        raise ReportChronologyError("legacy alias source file is unavailable")
    try:
        raw = source_path.read_bytes()
    except OSError as exc:
        raise ReportChronologyError("legacy alias source file is unreadable") from exc
    if not raw.startswith(b"---\n"):
        raise ReportChronologyError("legacy alias source file lacks front matter")
    parts = raw.split(b"---\n", 2)
    if len(parts) != 3:
        raise ReportChronologyError("legacy alias source file front matter is malformed")
    return parts[2]


def _legacy_alias_representative(
    canonical_utc: datetime, entries: list[tuple[Any, str]]
) -> Any:
    if any(kind != "legacy" for _report, kind in entries):
        raise ReportChronologyError("duplicate canonical report instant includes a non-legacy report")

    reference_metadata: dict[str, Any] | None = None
    reference_body: bytes | None = None
    for report, _kind in entries:
        normalised_metadata = _normalised_legacy_alias_metadata(report, canonical_utc)
        body = _archived_body_bytes(report)
        if reference_metadata is None:
            reference_metadata = normalised_metadata
            reference_body = body
            continue
        if normalised_metadata != reference_metadata:
            raise ReportChronologyError("same-instant legacy reports differ outside time representation")
        if body != reference_body:
            raise ReportChronologyError("same-instant legacy report bodies differ")

    ordered = sorted((report for report, _kind in entries), key=_source_rel)
    representative = ordered[0]
    aliases = tuple(ordered[1:])
    representative.chronology_aliases = aliases
    for alias in aliases:
        alias.chronology_alias_of = _source_rel(representative)
    return representative


def canonicalise_reports(reports: Iterable[Any]) -> list[Any]:
    """Return retained reports in one fail-closed reverse UTC chronology."""
    grouped: dict[datetime, list[tuple[Any, str]]] = {}

    for report in reports:
        metadata = _metadata(report)
        if metadata.get("schema_version") == DETERMINISTIC_SCHEMA:
            canonical_utc, display, time_label, abbreviation = _deterministic_identity(report)
            kind = "deterministic"
        else:
            canonical_utc, display, time_label, abbreviation = _legacy_identity(report)
            kind = "legacy"

        report.timestamp = display
        report.sort_key = _canonical_text(canonical_utc)
        report.time_label = time_label
        report.tz = abbreviation
        report.report_time_utc = _canonical_text(canonical_utc)
        report.chronology_kind = kind
        report.chronology_aliases = ()
        grouped.setdefault(canonical_utc, []).append((report, kind))

    resolved: list[tuple[datetime, Any]] = []
    for canonical_utc, entries in grouped.items():
        if len(entries) == 1:
            representative = entries[0][0]
        else:
            representative = _legacy_alias_representative(canonical_utc, entries)
        resolved.append((canonical_utc, representative))

    resolved.sort(key=lambda item: item[0], reverse=True)
    return [report for _, report in resolved]


__all__ = ["ReportChronologyError", "canonicalise_reports"]
