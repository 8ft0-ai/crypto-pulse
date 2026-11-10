"""Deterministic, evidence-bounded reader findings for archived crypto snapshots."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT
MAX_SOURCE_SKEW_SECONDS = 300
MAX_CROSS_SOURCE_DIFFERENCE_PCT = 1.0
MIN_RELATIVE_7D_GAP_PP = 2.0
MAX_HISTORICAL_GAP_SECONDS = 5400


def number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def instant(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def source_identity(path, snapshot=None):
    """Bind claims to exact tracked bytes; an in-memory mutation cannot borrow a Git URL."""
    try:
        relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
        raw = path.read_bytes()
        commit = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", relative],
            cwd=ROOT, check=True, capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
            return None
        committed = subprocess.run(
            ["git", "show", f"{commit}:{relative}"],
            cwd=ROOT, check=True, capture_output=True, timeout=5,
        ).stdout
        if raw != committed or (snapshot is not None and json.loads(raw) != snapshot):
            return None
        digest = hashlib.sha256(committed).hexdigest()
        # Isolated offline fixture commits must never masquerade as public Git evidence.
        if ROOT.resolve() == PROJECT_ROOT.resolve():
            url = f"https://github.com/8ft0-ai/crypto-pulse/blob/{commit}/{quote(relative, safe='/')}"
        else:
            url = f"fixture://{commit}/{quote(relative, safe='/')}"
        return {"path": relative, "commit": commit, "sha256": digest, "url": url}
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        return None


def evidence(path):
    identity = source_identity(path)
    if not identity:
        return None
    return f"[archived JSON]({identity['url']}) (SHA-256 `{identity['sha256']}`)"


def prior_snapshot(path, now):
    """Select a prior observation only when independently archived and hour-aligned."""
    if not path.is_file() or not now:
        return None
    root = ROOT / "data" / "crypto" / "hourly"
    candidates = []
    for candidate in root.glob("*/*/*/*_source_snapshot.json"):
        if candidate.resolve() == path.resolve():
            continue
        try:
            payload = json.loads(candidate.read_text())
            t = instant(payload.get("run", {}).get("generated_at_utc"))
            if (t and 0 < (now - t).total_seconds() <= MAX_HISTORICAL_GAP_SECONDS
                    and payload.get("quality", {}).get("status") == "valid-ok"
                    and evidence(candidate)):
                # Reject prior observations whose asset timestamps are not aligned.
                assets = payload.get("market", {}).get("assets", [])
                if not any(isinstance(a, dict) and (at := instant(a.get("last_updated")))
                           and abs((t-at).total_seconds()) <= MAX_SOURCE_SKEW_SECONDS
                           for a in assets):
                    continue
                candidates.append((t, candidate, payload))
        except (OSError, ValueError, TypeError):
            continue
    return max(candidates, default=None, key=lambda x: x[0])


def _claim(kind, category, headline, finding, significance, uncertainty, next_test, sources, legacy):
    return {
        "kind": kind, "category": category, "headline": headline,
        "finding": finding, "significance": significance,
        "uncertainty": uncertainty, "next_test": next_test,
        "sources": sources, "caveats": [], "legacy": legacy,
    }


def assess(snapshot, path, quality):
    """The sole deterministic claim admission authority for Markdown and article projection."""
    identity = source_identity(path, snapshot)
    run_time = instant(snapshot.get("run", {}).get("generated_at_utc"))
    accepted_quality = quality.get("status") in ("valid-ok", "valid-degraded")
    claims = []
    candidates = []
    local_caveats = []
    assets = {a.get("symbol"): a for a in snapshot.get("market", {}).get("assets", [])
              if isinstance(a, dict) and isinstance(a.get("symbol"), str)}
    trustworthy = bool(identity and run_time and accepted_quality)
    if trustworthy:
        changes = {k: number(assets[k].get("change_7d_pct")) for k in ("SOL", "BTC", "ETH") if k in assets}
        times = [instant(assets[k].get("last_updated")) for k in ("SOL", "BTC", "ETH") if k in assets]
        aligned = (len(changes) == 3 and len(times) == 3
                   and all(v is not None for v in changes.values())
                   and all(t and abs((run_time - t).total_seconds()) <= MAX_SOURCE_SKEW_SECONDS for t in times))
        if aligned:
            btc_gap, eth_gap = changes["SOL"] - changes["BTC"], changes["SOL"] - changes["ETH"]
            if abs(btc_gap) >= MIN_RELATIVE_7D_GAP_PP and abs(eth_gap) >= MIN_RELATIVE_7D_GAP_PP:
                legacy = (
                    f"**Seven-day relative movement:** SOL {changes['SOL']:+.2f}%, BTC {changes['BTC']:+.2f}%, ETH {changes['ETH']:+.2f}%. "
                    f"SOL minus BTC = {btc_gap:+.2f} percentage points; SOL minus ETH = {eth_gap:+.2f} percentage points. "
                    "These are source-reported rolling changes, not independently reconstructed returns. "
                    "Test whether the gap persists in later aligned snapshots; no cause is established."
                )
                claims.append(_claim(
                    "seven_day_relative", "market", "SOL seven-day movement differed from BTC and ETH",
                    f"SOL {changes['SOL']:+.2f}%, BTC {changes['BTC']:+.2f}%, ETH {changes['ETH']:+.2f}%; "
                    f"SOL–BTC {btc_gap:+.2f} pp and SOL–ETH {eth_gap:+.2f} pp.",
                    "The reported seven-day gaps meet the pre-existing two-percentage-point materiality threshold.",
                    "Source-reported rolling changes are not independently reconstructed returns; no cause or forecast is established.",
                    "Check whether both gaps persist in later independently archived, timestamp-aligned snapshots.",
                    [identity], legacy,
                ))
                candidates.append({"kind": "seven_day_relative", "status": "admitted", "reason": "aligned and material"})
            else:
                candidates.append({"kind": "seven_day_relative", "status": "rejected", "reason": "below materiality threshold"})
        else:
            candidates.append({"kind": "seven_day_relative", "status": "unavailable", "reason": "missing or misaligned seven-day observations"})

        exchange = snapshot.get("exchange_crosscheck", {})
        if not isinstance(exchange, dict):
            exchange = {}
        selected = exchange.get("selected")
        sources = exchange.get("sources") if isinstance(exchange.get("sources"), dict) else {}
        rows = sources.get(selected, []) if selected else []
        by_symbol = {r.get("symbol"): r for r in rows if isinstance(r, dict)}
        differences, rejected = [], []
        for symbol in sorted(set(assets) & set(by_symbol)):
            market, row = assets[symbol], by_symbol[symbol]
            a, b = number(market.get("price_usd")), number(row.get("price"))
            ta, tb = instant(market.get("last_updated")), instant(row.get("source_time"))
            if not (a and b and a > 0 and b > 0 and ta and tb
                    and abs((ta - tb).total_seconds()) <= MAX_SOURCE_SKEW_SECONDS
                    and abs((run_time - ta).total_seconds()) <= MAX_SOURCE_SKEW_SECONDS
                    and abs((run_time - tb).total_seconds()) <= MAX_SOURCE_SKEW_SECONDS):
                rejected.append(symbol)
                continue
            delta = abs(a - b) / a * 100
            if delta > MAX_CROSS_SOURCE_DIFFERENCE_PCT:
                rejected.append(f"{symbol} {delta:.3f}% (over tolerance)")
            else:
                differences.append(f"{symbol} {delta:.3f}%")
        status = "admitted" if differences else ("rejected" if rejected else "unavailable")
        rejection = ", ".join(sorted(set(rejected)))
        candidates.append({"kind": "cross_source", "status": status,
                           "reason": rejection if rejected else ("source comparisons accepted" if differences else "no eligible rows")})
        if rejected:
            local_caveats.append("Cross-source price check rejected/inconclusive: " + rejection
                                 + ". Optional rows are not a positive finding.")
        if differences:
            legacy = (f"**Cross-source price check:** accepted: {', '.join(differences)}; absolute difference versus the market-source price "
                      f"(tolerance ≤{MAX_CROSS_SOURCE_DIFFERENCE_PCT:.1f}%; observation skew ≤{MAX_SOURCE_SKEW_SECONDS} s). "
                      + ("Rejected/inconclusive: " + rejection + ". " if rejected else "All compared rows are within tolerance. ")
                      + "These are asynchronous venue/source observations, not identical-time execution prices.")
            claims.append(_claim(
                "cross_source", "assurance", "Selected source-price checks met tolerance",
                "Accepted comparison differences: " + ", ".join(differences) + ".",
                "This is a source-consistency check, not a material market-movement finding.",
                "Asynchronous source observations are not identical-time execution prices.",
                "Repeat price checks on later aligned source observations.", [identity], legacy,
            ))

        previous = prior_snapshot(path, run_time)
        if previous:
            prev_time, prev_path, prev = previous
            prev_identity = source_identity(prev_path, prev)
            prev_assets = {a.get("symbol"): a for a in prev.get("market", {}).get("assets", []) if isinstance(a, dict)}
            comparisons = []
            if prev_identity:
                for symbol in sorted(set(assets) & set(prev_assets)):
                    old, new = number(prev_assets[symbol].get("price_usd")), number(assets[symbol].get("price_usd"))
                    old_time, new_time = instant(prev_assets[symbol].get("last_updated")), instant(assets[symbol].get("last_updated"))
                    if (old and new and old > 0 and new > 0 and old_time and new_time
                            and 0 < (new_time - old_time).total_seconds() <= MAX_HISTORICAL_GAP_SECONDS
                            and abs((prev_time - old_time).total_seconds()) <= MAX_SOURCE_SKEW_SECONDS
                            and abs((run_time - new_time).total_seconds()) <= MAX_SOURCE_SKEW_SECONDS):
                        comparisons.append(f"{symbol} {(new / old - 1) * 100:+.2f}%")
            if comparisons:
                hours = (run_time - prev_time).total_seconds() / 3600
                prev_ref = evidence(prev_path)
                legacy = (f"**Archived interval comparison:** {', '.join(comparisons)} spot-price change over "
                          f"{hours:.2f} h, comparing this snapshot with {prev_ref}. "
                          "This is a two-point observation, not evidence of a sustained trend. Test with subsequent aligned hours.")
                claims.append(_claim(
                    "archived_interval", "market", "Spot prices changed between two archived hourly observations",
                    f"{', '.join(comparisons)} across {hours:.2f} h of archived observations.",
                    "The comparison measures a bounded two-point interval, not a continuous market trend.",
                    "Timing gaps and intermediate price paths are not measured by these two records.",
                    "Compare with subsequent independently archived, aligned hourly observations.",
                    [identity, prev_identity], legacy,
                ))
                candidates.append({"kind": "archived_interval", "status": "admitted", "reason": "two pinned aligned observations"})
            else:
                candidates.append({"kind": "archived_interval", "status": "unavailable", "reason": "no comparable aligned prior values"})
        else:
            candidates.append({"kind": "archived_interval", "status": "unavailable", "reason": "no eligible pinned prior snapshot"})

    if not trustworthy:
        state = "inconclusive"
        reason = ("Required quality is not accepted." if not accepted_quality
                  else "Essential source bytes, commit, hash, or observation time cannot be established.")
    else:
        state = "finding" if any(c["category"] == "market" for c in claims) else "factual_update"
        reason = ""

    market_claims = [claim for claim in claims if claim["category"] == "market"]
    if local_caveats:
        for claim in market_claims:
            claim["caveats"].extend(local_caveats)
    if state == "finding":
        main = market_claims[0]
        headline = main["headline"]
        summary = (
            f"This archived deterministic snapshot supports a bounded market observation: {main['finding']} "
            f"{main['significance']} {main['uncertainty']} "
            "It is a demonstration observation, not investment research, a recommendation or a trading signal. "
            "The result depends on the exact cited source and observation windows; other unavailable comparisons are not estimated."
        )
    elif state == "factual_update":
        headline = "Validated archived market snapshot — no qualifying market finding"
        summary = (
            "This archived source passed the required snapshot-quality and immutable-source checks, "
            "but no source-aligned market comparison met the existing qualifying rules. "
            "Recorded prices and source checks are factual observations, not evidence of an important market discovery. "
            "Unavailable or rejected optional comparisons are not treated as positive results. "
            "Further archived, time-aligned observations would be needed to test whether a material difference emerges."
        )
    else:
        headline = "Evidence assessment inconclusive"
        summary = (
            "This candidate cannot support a new enriched market finding because essential source "
            "identity, timestamp or required quality could not be verified. No unsupported observations "
            "are promoted into conclusions. The original archived record, if legitimately published, "
            "must remain available with its own attribution and limitations. Correct source evidence "
            "and successful validation are required before attempting another assessment."
        )

    projection = {
        "schema": "cryptopulse-editorial-article/v1", "article_state": state,
        "headline": headline, "summary": summary,
        "as_of_utc": snapshot.get("run", {}).get("generated_at_utc"),
        "quality_status": quality.get("status"),
        "source": identity,
        "claims": [{k: v for k, v in claim.items() if k != "legacy"} for claim in claims],
        "candidates": candidates,
        "caveats": local_caveats, "reason": reason,
    }
    return {"projection": projection, "claims": claims, "primary_evidence": identity}


def research_brief_from_assessment(assessment):
    """Backward-compatible Markdown is a rendering of the identical admitted claim set."""
    projection = assessment["projection"]
    lines = ["## Evidence-backed findings", "",
             "Deterministic observations only; no LLM inference, causal explanation or investment recommendation.", ""]
    identity = assessment["primary_evidence"]
    if identity:
        lines.extend([f"**Primary evidence:** [archived JSON]({identity['url']}) (SHA-256 `{identity['sha256']}`).", ""])
    else:
        lines.extend(["**Primary evidence:** immutable public link unavailable; findings requiring provenance are inconclusive.", ""])
    claims = assessment["claims"]
    if not claims:
        if projection["article_state"] == "inconclusive":
            lines.append("No qualifying finding: essential source quality or provenance is insufficient.")
        else:
            lines.append("No qualifying finding: no admitted material market comparison meets the existing rules.")
    else:
        for index, claim in enumerate(claims[:3], 1):
            lines.extend([f"{index}. {claim['legacy']}", ""])
    lines.extend(["", "### Evidence boundaries", "",
                  f"- Required snapshot quality: `{projection['quality_status'] or 'unknown'}`; source timestamp alignment tolerance: {MAX_SOURCE_SKEW_SECONDS} seconds.",
                  f"- Price difference tolerance: {MAX_CROSS_SOURCE_DIFFERENCE_PCT:.1f}%; material relative seven-day gap: {MIN_RELATIVE_7D_GAP_PP:.1f} percentage points.",
                  "- Missing, stale or incomparable values are omitted rather than estimated. Historical comparison requires a verified prior snapshot within 90 minutes."])
    for caveat in projection["caveats"]:
        lines.append(f"- {caveat}")
    lines.append("- Figures are demonstration observations and may be inaccurate, incomplete or stale. They do not establish causality or predict returns.")
    return "\n".join(lines)


def research_brief(snapshot, path, quality):
    return research_brief_from_assessment(assess(snapshot, path, quality))
