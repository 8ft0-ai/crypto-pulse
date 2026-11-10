"""Deterministically project one validated source snapshot into the v1 LLM evidence contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

from .contracts import EVIDENCE_SCHEMA_VERSION, canonical_json_bytes, content_sha256, evidence_id
from .schema_validation import validate_schema

PRODUCT_BOUNDARIES = (
    "AI-generated public demonstration content.",
    "Not financial advice, investment research, a recommendation, or a trading signal.",
    "Repository code owns validation, rendering, review, and publication.",
)


class EvidenceBundleError(ValueError):
    """Raised when a selected snapshot cannot become governed evidence."""


@dataclass(frozen=True)
class EvidenceBundleBuild:
    bundle: dict[str, Any]
    snapshot_path: str
    snapshot_sha256: str
    quality_status: str


def _repository_path(repository_root: Path, requested: str) -> tuple[Path, str]:
    candidate = PurePosixPath(requested)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise EvidenceBundleError("snapshot path must be repository-relative and must not contain '..'")
    if not requested.startswith("data/crypto/hourly/") or not requested.endswith("_source_snapshot.json"):
        raise EvidenceBundleError(
            "snapshot path must match data/crypto/hourly/**/*_source_snapshot.json"
        )
    root = repository_root.resolve()
    path = (root / Path(*candidate.parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise EvidenceBundleError("snapshot path resolves outside the repository") from exc
    if not path.is_file():
        raise EvidenceBundleError(f"snapshot file does not exist: {requested}")
    return path, candidate.as_posix()


def _finite_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if isinstance(value, int):
        return value
    return number


def _subject(kind: str, identifier: str, *, symbol: str | None = None, name: str | None = None) -> dict[str, str]:
    value = {"type": kind, "id": identifier}
    if symbol:
        value["symbol"] = symbol
    if name:
        value["name"] = name
    return value


def _source(name: str, path: str) -> dict[str, str]:
    return {"name": name, "source_path": path}


def _append(
    output: list[dict[str, Any]],
    *,
    identifier: str,
    evidence_type: str,
    subject: dict[str, str],
    field: str,
    value: Any,
    source_name: str,
    source_path: str,
    unit: str | None = None,
    observed_at: str | None = None,
) -> None:
    item: dict[str, Any] = {
        "evidence_id": identifier,
        "evidence_type": evidence_type,
        "subject": subject,
        "field": field,
        "value": value,
        "source": _source(source_name, source_path),
    }
    if unit:
        item["unit"] = unit
    if observed_at:
        item["observed_at"] = observed_at
    output.append(item)


def _append_number(output: list[dict[str, Any]], **kwargs: Any) -> None:
    number = _finite_number(kwargs.pop("value"))
    if number is not None:
        _append(output, evidence_type="number", value=number, **kwargs)


def _market_evidence(snapshot: Mapping[str, Any], output: list[dict[str, Any]]) -> None:
    assets = (snapshot.get("market") or {}).get("assets", [])
    fields = {
        "price_usd": "usd",
        "change_1h_pct": "percent",
        "change_24h_pct": "percent",
        "change_7d_pct": "percent",
        "market_cap_usd": "usd",
        "volume_24h_usd": "usd",
        "market_cap_rank": "rank",
    }
    for index, row in enumerate(assets if isinstance(assets, list) else []):
        if not isinstance(row, Mapping):
            continue
        asset_id = str(row.get("id", "")).strip().lower()
        symbol = str(row.get("symbol", "")).strip().upper()
        name = str(row.get("name", "")).strip()
        if not asset_id:
            continue
        subject = _subject("asset", asset_id, symbol=symbol or None, name=name or None)
        observed_at = row.get("last_updated") if isinstance(row.get("last_updated"), str) else None
        for field, unit in fields.items():
            _append_number(
                output,
                identifier=evidence_id("market", "asset", asset_id, field),
                subject=subject,
                field=field,
                value=row.get(field),
                unit=unit,
                observed_at=observed_at,
                source_name="coingecko",
                source_path=f"/market/assets/{index}/{field}",
            )
        if observed_at:
            _append(
                output,
                identifier=evidence_id("market", "asset", asset_id, "last_updated"),
                evidence_type="timestamp",
                subject=subject,
                field="last_updated",
                value=observed_at,
                source_name="coingecko",
                source_path=f"/market/assets/{index}/last_updated",
            )


def _source_evidence(snapshot: Mapping[str, Any], output: list[dict[str, Any]]) -> None:
    sources = snapshot.get("sources")
    if not isinstance(sources, Mapping):
        return
    for name in sorted(sources):
        payload = sources[name]
        if not isinstance(payload, Mapping):
            continue
        subject = _subject("source", name, name=name.replace("_", " ").title())
        status = payload.get("status")
        if isinstance(status, str):
            _append(
                output,
                identifier=evidence_id("source", name, "status"),
                evidence_type="status",
                subject=subject,
                field="status",
                value=status,
                source_name="source-snapshot",
                source_path=f"/sources/{name}/status",
            )
        for field in ("reason", "message"):
            value = payload.get(field)
            if isinstance(value, str) and value.strip():
                _append(
                    output,
                    identifier=evidence_id("source", name, field),
                    evidence_type="string",
                    subject=subject,
                    field=field,
                    value=value,
                    source_name="source-snapshot",
                    source_path=f"/sources/{name}/{field}",
                )
        fetched_at = payload.get("fetched_at_utc")
        if isinstance(fetched_at, str):
            _append(
                output,
                identifier=evidence_id("source", name, "fetched_at_utc"),
                evidence_type="timestamp",
                subject=subject,
                field="fetched_at_utc",
                value=fetched_at,
                source_name="source-snapshot",
                source_path=f"/sources/{name}/fetched_at_utc",
            )
        covered = payload.get("covered_symbols")
        if isinstance(covered, list) and all(isinstance(item, (str, int, float, bool)) for item in covered):
            values = list(dict.fromkeys(covered))
            _append(
                output,
                identifier=evidence_id("source", name, "covered_symbols"),
                evidence_type="set",
                subject=subject,
                field="covered_symbols",
                value=values,
                source_name="source-snapshot",
                source_path=f"/sources/{name}/covered_symbols",
            )


def _exchange_evidence(snapshot: Mapping[str, Any], output: list[dict[str, Any]]) -> None:
    exchange = snapshot.get("exchange_crosscheck")
    if not isinstance(exchange, Mapping):
        return
    selected = exchange.get("selected")
    sources = exchange.get("sources")
    if not isinstance(sources, Mapping):
        return
    for source_name in sorted(sources):
        rows = sources[source_name]
        if not isinstance(rows, list):
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                continue
            pair = str(row.get("pair") or row.get("symbol") or "").strip().lower()
            symbol = str(row.get("symbol", "")).strip().upper()
            if not pair:
                continue
            subject = _subject("exchange_pair", pair, symbol=symbol or None)
            observed_at = row.get("source_time") if isinstance(row.get("source_time"), str) else None
            quote = str(row.get("quote", "usd")).strip().lower() or "usd"
            for field in ("price", "bid", "ask"):
                _append_number(
                    output,
                    identifier=evidence_id("exchange", source_name, pair, field),
                    subject=subject,
                    field=field,
                    value=row.get(field),
                    unit=quote,
                    observed_at=observed_at,
                    source_name=source_name,
                    source_path=f"/exchange_crosscheck/sources/{source_name}/{index}/{field}",
                )
            if observed_at:
                _append(
                    output,
                    identifier=evidence_id("exchange", source_name, pair, "source_time"),
                    evidence_type="timestamp",
                    subject=subject,
                    field="source_time",
                    value=observed_at,
                    source_name=source_name,
                    source_path=f"/exchange_crosscheck/sources/{source_name}/{index}/source_time",
                )
    if isinstance(selected, str) and selected:
        _append(
            output,
            identifier=evidence_id("exchange", "selection", "source"),
            evidence_type="string",
            subject=_subject("market", "exchange-crosscheck"),
            field="source",
            value=selected,
            source_name="source-snapshot",
            source_path="/exchange_crosscheck/selected",
        )


def _defi_evidence(snapshot: Mapping[str, Any], output: list[dict[str, Any]]) -> None:
    defi = snapshot.get("defi")
    if not isinstance(defi, Mapping):
        return
    _append_number(
        output,
        identifier=evidence_id("defi", "market", "total_tvl_usd"),
        subject=_subject("defi_metric", "total-tvl", name="Total DeFi TVL"),
        field="total_tvl_usd",
        value=defi.get("total_tvl_usd"),
        unit="usd",
        source_name="defillama",
        source_path="/defi/total_tvl_usd",
    )
    stablecoins = defi.get("stablecoins")
    for index, row in enumerate(stablecoins if isinstance(stablecoins, list) else []):
        if not isinstance(row, Mapping):
            continue
        symbol = str(row.get("symbol", "")).strip().upper()
        stable_id = str(row.get("id") or symbol).strip().lower()
        if not stable_id:
            continue
        subject = _subject(
            "asset", f"stablecoin-{stable_id}", symbol=symbol or None, name=str(row.get("name", "")).strip() or None
        )
        for field, unit in (
            ("price_usd", "usd"),
            ("circulating_usd", "usd"),
            ("change_1d_pct", "percent"),
            ("change_7d_pct", "percent"),
        ):
            _append_number(
                output,
                identifier=evidence_id("defi", "stablecoin", stable_id, field),
                subject=subject,
                field=field,
                value=row.get(field),
                unit=unit,
                source_name="defillama",
                source_path=f"/defi/stablecoins/{index}/{field}",
            )


def build_evidence_bundle(
    requested_snapshot_path: str,
    *,
    repository_root: str | Path = ".",
    source_config_path: str | Path = "config/crypto_sources.yml",
    evidence_schema: dict[str, Any] | None = None,
    validator: Callable[[Path, dict[str, Any]], dict[str, Any]] | None = None,
    config_loader: Callable[[Path], dict[str, Any]] | None = None,
) -> EvidenceBundleBuild:
    root = Path(repository_root)
    path, relative = _repository_path(root, requested_snapshot_path)
    if validator is None or config_loader is None:
        from scripts.validate_crypto_snapshot import load_config, validate_snapshot

        validator = validator or validate_snapshot
        config_loader = config_loader or load_config
    config_path = root / source_config_path
    quality = validator(path, config_loader(config_path))
    status = quality.get("status")
    if status not in {"valid-ok", "valid-degraded"}:
        raise EvidenceBundleError(f"snapshot is not valid for generation: {status!r}")
    raw = path.read_bytes()
    try:
        snapshot = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceBundleError("validated snapshot could not be decoded as JSON") from exc
    if not isinstance(snapshot, dict):
        raise EvidenceBundleError("snapshot root must be an object")

    evidence: list[dict[str, Any]] = []
    snapshot_subject = _subject("snapshot", path.stem)
    _append(
        evidence,
        identifier=evidence_id("quality", "snapshot", "status"),
        evidence_type="status",
        subject=snapshot_subject,
        field="status",
        value=status,
        source_name="snapshot-validator",
        source_path="/quality/status",
    )
    generated_at = (snapshot.get("run") or {}).get("generated_at_utc")
    if isinstance(generated_at, str):
        _append(
            evidence,
            identifier=evidence_id("quality", "snapshot", "generated_at_utc"),
            evidence_type="timestamp",
            subject=snapshot_subject,
            field="generated_at_utc",
            value=generated_at,
            source_name="source-snapshot",
            source_path="/run/generated_at_utc",
        )
    _market_evidence(snapshot, evidence)
    _source_evidence(snapshot, evidence)
    _exchange_evidence(snapshot, evidence)
    _defi_evidence(snapshot, evidence)

    identifiers = [item["evidence_id"] for item in evidence]
    if len(identifiers) != len(set(identifiers)):
        raise EvidenceBundleError("deterministic evidence projection produced duplicate IDs")
    source_sha = hashlib.sha256(raw).hexdigest()
    payload = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "source_snapshot": {
            "path": relative,
            "sha256": source_sha,
            "schema_version": str(snapshot.get("schema_version", "")),
            "quality_status": status,
            "generated_at_utc": generated_at,
        },
        "product_boundaries": list(PRODUCT_BOUNDARIES),
        "evidence": evidence,
    }
    bundle = {"bundle_id": f"sha256:{content_sha256(payload)}", **payload}
    if evidence_schema is not None:
        diagnostics = validate_schema(bundle, evidence_schema)
        if diagnostics:
            detail = "; ".join(f"{item.path}: {item.message}" for item in diagnostics[:8])
            raise EvidenceBundleError(f"evidence bundle violates its schema: {detail}")
    return EvidenceBundleBuild(bundle, relative, source_sha, status)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a governed LLM evidence bundle from one validated snapshot")
    parser.add_argument("snapshot_path")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--source-config", default="config/crypto_sources.yml")
    parser.add_argument("--evidence-schema", default="schemas/crypto-market-evidence-bundle-v1.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--metadata-output")
    args = parser.parse_args()
    root = Path(args.repository_root)
    schema = json.loads((root / args.evidence_schema).read_text(encoding="utf-8"))
    build = build_evidence_bundle(
        args.snapshot_path,
        repository_root=root,
        source_config_path=args.source_config,
        evidence_schema=schema,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_json_bytes(build.bundle) + b"\n")
    if args.metadata_output:
        metadata = {
            "snapshot_path": build.snapshot_path,
            "snapshot_sha256": build.snapshot_sha256,
            "quality_status": build.quality_status,
            "bundle_id": build.bundle["bundle_id"],
        }
        target = Path(args.metadata_output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(canonical_json_bytes(metadata) + b"\n")
    print(json.dumps({"bundle_id": build.bundle["bundle_id"], "snapshot_sha256": build.snapshot_sha256}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
