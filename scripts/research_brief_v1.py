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


def evidence(path):
    """Only link repository-tracked data at the exact commit that last changed it."""
    try:
        relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
        sha = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", relative],
            cwd=ROOT, check=True, capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
            return None
        committed = subprocess.run(
            ["git", "show", f"{sha}:{relative}"],
            cwd=ROOT, check=True, capture_output=True, timeout=5,
        ).stdout
        if path.read_bytes() != committed:
            return None
        digest = hashlib.sha256(committed).hexdigest()
        url = f"https://github.com/8ft0-ai/crypto-pulse/blob/{sha}/{quote(relative, safe='/')}"
        return f"[archived JSON]({url}) (SHA-256 `{digest}`)"
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


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


def research_brief(snapshot, path, quality):
    lines = ["## Evidence-backed findings", "",
             "Deterministic observations only; no LLM inference, causal explanation or investment recommendation.", ""]
    if quality.get("status") not in ("valid-ok", "valid-degraded"):
        return "\n".join(lines + ["No qualifying finding: snapshot quality is not accepted."])
    assets = {a.get("symbol"): a for a in snapshot.get("market", {}).get("assets", []) if isinstance(a, dict)}
    run_time = instant(snapshot.get("run", {}).get("generated_at_utc"))
    ref = evidence(path)
    if ref:
        lines += [f"**Primary evidence:** {ref}.", ""]
    else:
        lines += ["**Primary evidence:** immutable public link unavailable; findings requiring provenance are inconclusive.", ""]
    findings = []
    if ref and run_time and all(k in assets for k in ("SOL", "BTC", "ETH")):
        changes = {k: number(assets[k].get("change_7d_pct")) for k in ("SOL", "BTC", "ETH")}
        times = [instant(assets[k].get("last_updated")) for k in changes]
        if all(v is not None for v in changes.values()) and all(t and abs((run_time-t).total_seconds()) <= MAX_SOURCE_SKEW_SECONDS for t in times):
            btc_gap = changes["SOL"] - changes["BTC"]
            eth_gap = changes["SOL"] - changes["ETH"]
            if abs(btc_gap) >= MIN_RELATIVE_7D_GAP_PP and abs(eth_gap) >= MIN_RELATIVE_7D_GAP_PP:
                findings.append(
                    f"**Seven-day relative movement:** SOL {changes['SOL']:+.2f}%, BTC {changes['BTC']:+.2f}%, ETH {changes['ETH']:+.2f}%. "
                    f"SOL minus BTC = {btc_gap:+.2f} percentage points; SOL minus ETH = {eth_gap:+.2f} percentage points. "
                    "These are source-reported rolling changes, not independently reconstructed returns. "
                    "Test whether the gap persists in later aligned snapshots; no cause is established."
                )
    exchange = snapshot.get("exchange_crosscheck", {})
    selected = exchange.get("selected")
    rows = exchange.get("sources", {}).get(selected, []) if selected else []
    by_symbol = {r.get("symbol"): r for r in rows if isinstance(r, dict)}
    differences = []
    rejected = []
    if ref and run_time:
        for symbol in sorted(set(assets) & set(by_symbol)):
            market = assets[symbol]
            row = by_symbol[symbol]
            a, b = number(market.get("price_usd")), number(row.get("price"))
            ta, tb = instant(market.get("last_updated")), instant(row.get("source_time"))
            if not (a and b and a > 0 and b > 0 and ta and tb and abs((ta-tb).total_seconds()) <= MAX_SOURCE_SKEW_SECONDS and abs((run_time-ta).total_seconds()) <= MAX_SOURCE_SKEW_SECONDS and abs((run_time-tb).total_seconds()) <= MAX_SOURCE_SKEW_SECONDS):
                rejected.append(symbol)
                continue
            delta = abs(a-b)/a*100
            if delta > MAX_CROSS_SOURCE_DIFFERENCE_PCT:
                rejected.append(f"{symbol} {delta:.3f}% (over tolerance)")
            else:
                differences.append(f"{symbol} {delta:.3f}%")
        if differences or rejected:
            findings.append(
                f"**Cross-source price check:** accepted: {', '.join(differences) if differences else 'none'}; absolute difference versus the market-source price "
                f"(tolerance ≤{MAX_CROSS_SOURCE_DIFFERENCE_PCT:.1f}%; observation skew ≤{MAX_SOURCE_SKEW_SECONDS} s). "
                + ("Rejected/inconclusive: " + ", ".join(sorted(set(rejected))) + ". " if rejected else "All compared rows are within tolerance. ")
                + "These are asynchronous venue/source observations, not identical-time execution prices."
            )
    if ref and run_time:
        previous = prior_snapshot(path, run_time)
        if previous:
            prev_time, prev_path, prev = previous
            prev_ref = evidence(prev_path)
            prev_assets = {a.get("symbol"): a for a in prev.get("market", {}).get("assets", []) if isinstance(a, dict)}
            comparisons = []
            if prev_ref:
                for symbol in sorted(set(assets) & set(prev_assets)):
                    old, new = number(prev_assets[symbol].get("price_usd")), number(assets[symbol].get("price_usd"))
                    old_time, new_time = instant(prev_assets[symbol].get("last_updated")), instant(assets[symbol].get("last_updated"))
                    if (old and new and old > 0 and new > 0 and old_time and new_time
                            and 0 < (new_time-old_time).total_seconds() <= MAX_HISTORICAL_GAP_SECONDS
                            and abs((prev_time-old_time).total_seconds()) <= MAX_SOURCE_SKEW_SECONDS
                            and abs((run_time-new_time).total_seconds()) <= MAX_SOURCE_SKEW_SECONDS):
                        comparisons.append(f"{symbol} {(new/old-1)*100:+.2f}%")
                if comparisons:
                    findings.append(
                        f"**Archived interval comparison:** {', '.join(comparisons)} spot-price change over "
                        f"{(run_time-prev_time).total_seconds()/3600:.2f} h, comparing this snapshot with {prev_ref}. "
                        "This is a two-point observation, not evidence of a sustained trend. Test with subsequent aligned hours."
                    )
    if not findings:
        lines.append("No qualifying finding: source alignment, materiality, archived comparison or immutable evidence is insufficient.")
    else:
        for i, finding in enumerate(findings[:3], 1):
            lines.extend([f"{i}. {finding}", ""])
    lines += ["", "### Evidence boundaries", "",
              f"- Required snapshot quality: `{quality.get('status', 'unknown')}`; source timestamp alignment tolerance: {MAX_SOURCE_SKEW_SECONDS} seconds.",
              f"- Price difference tolerance: {MAX_CROSS_SOURCE_DIFFERENCE_PCT:.1f}%; material relative seven-day gap: {MIN_RELATIVE_7D_GAP_PP:.1f} percentage points.",
              "- Missing, stale or incomparable values are omitted rather than estimated. Historical comparison requires a verified prior snapshot within 90 minutes.",
              "- Figures are demonstration observations and may be inaccurate, incomplete or stale. They do not establish causality or predict returns."]
    return "\n".join(lines)
