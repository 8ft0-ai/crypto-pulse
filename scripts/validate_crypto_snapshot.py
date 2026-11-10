#!/usr/bin/env python3
"""Validate and classify CryptoPulse source snapshot JSON files."""
from __future__ import annotations
import argparse, json, math, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_SOURCE_STATUSES={"ok","warning","error","skipped"}
VALID_QUALITY_STATUSES={"valid-ok","valid-degraded","invalid"}
REQUIRED_TOP_LEVEL_KEYS={"schema_version","run","sources","market","exchange_crosscheck","defi","warnings","errors"}
REQUIRED_RUN_KEYS={"generated_at_utc","generated_at_local","timezone","cadence"}
DEFAULT_REQUIRED_SOURCES=["coingecko","defillama"]
DEFAULT_REQUIRED_SYMBOLS=["BTC","ETH","SOL"]
DEFAULT_MAJOR_STABLECOINS=["USDT","USDC"]
MARKET_CHANGE_FIELDS=["change_1h_pct","change_24h_pct","change_7d_pct"]

class ValidationError(ValueError):
    """Raised when a snapshot fails schema or quality validation."""

def parse_args()->argparse.Namespace:
    p=argparse.ArgumentParser(description="Validate CryptoPulse source snapshot JSON files.")
    p.add_argument("path",help="Snapshot file or directory containing *_source_snapshot.json files.")
    p.add_argument("--config",default="config/crypto_sources.yml",help="YAML source-quality config used to classify snapshots.")
    return p.parse_args()

def load_config(path:Path)->dict[str,Any]:
    if not path.exists(): return {}
    try: import yaml
    except ImportError: return {}
    data=yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data,dict): raise ValidationError(f"config must contain a YAML mapping: {path}")
    return data

def require_mapping(v:Any,path:str)->dict[str,Any]:
    if not isinstance(v,dict): raise ValidationError(f"{path} must be an object")
    return v

def require_list(v:Any,path:str)->list[Any]:
    if not isinstance(v,list): raise ValidationError(f"{path} must be a list")
    return v

def require_string(v:Any,path:str)->str:
    if not isinstance(v,str) or not v.strip(): raise ValidationError(f"{path} must be a non-empty string")
    return v

def _norm_ts(text:str)->str: return text[:-1]+"+00:00" if text.endswith("Z") else text

def parse_iso_timestamp(v:Any,path:str)->datetime:
    text=_norm_ts(require_string(v,path))
    try: out=datetime.fromisoformat(text)
    except ValueError as exc: raise ValidationError(f"{path} must be an ISO-8601 timestamp") from exc
    if out.tzinfo is None: out=out.replace(tzinfo=timezone.utc)
    return out.astimezone(timezone.utc)

def try_ts(v:Any)->datetime|None:
    if not isinstance(v,str) or not v.strip(): return None
    try: out=datetime.fromisoformat(_norm_ts(v.strip()))
    except ValueError: return None
    if out.tzinfo is None: out=out.replace(tzinfo=timezone.utc)
    return out.astimezone(timezone.utc)

def num(v:Any)->float|None:
    if isinstance(v,bool) or v is None: return None
    try: out=float(v) if isinstance(v,(int,float,str)) and str(v).strip() else None
    except ValueError: return None
    return out if out is not None and math.isfinite(out) else None

def cfg_list(config:dict[str,Any],default:list[str],*keys:str)->list[str]:
    v:Any=config
    for k in keys:
        if not isinstance(v,dict): return default.copy()
        v=v.get(k)
    return [str(x).upper() for x in v if str(x).strip()] if isinstance(v,list) and v else default.copy()

def cfg_required_sources(config:dict[str,Any])->list[str]:
    rows=config.get("sources") if isinstance(config,dict) else None
    out=[str(k) for k,v in rows.items() if isinstance(v,dict) and bool(v.get("required"))] if isinstance(rows,dict) else []
    return out or DEFAULT_REQUIRED_SOURCES.copy()

def cfg_exchange_sources(config:dict[str,Any])->list[dict[str,Any]]:
    ex=config.get("exchange_crosschecks") if isinstance(config,dict) else None
    rows=ex.get("sources") if isinstance(ex,dict) else None
    return [r for r in rows if isinstance(r,dict) and r.get("name")] if isinstance(rows,list) else []

def cfg_enabled_exchanges(config:dict[str,Any])->list[str]:
    return [str(r["name"]) for r in cfg_exchange_sources(config) if bool(r.get("enabled",True))]

def cfg_disabled_exchanges(config:dict[str,Any])->list[str]:
    return [str(r["name"]) for r in cfg_exchange_sources(config) if not bool(r.get("enabled",True))]

def freshness_tolerance(config:dict[str,Any])->int:
    q=config.get("quality") if isinstance(config,dict) else None
    try: return max(int(q.get("freshness_tolerance_minutes",180)),1) if isinstance(q,dict) else 180
    except (TypeError,ValueError): return 180

def peg_threshold(config:dict[str,Any])->float:
    q=config.get("quality") if isinstance(config,dict) else None
    val=num(q.get("stablecoin_peg_warning_threshold_pct")) if isinstance(q,dict) else None
    return val if val and val>0 else 1.0

def required_symbols(config:dict[str,Any])->list[str]: return cfg_list(config,DEFAULT_REQUIRED_SYMBOLS,"assets","required_symbols")
def major_stablecoins(config:dict[str,Any])->list[str]: return cfg_list(config,DEFAULT_MAJOR_STABLECOINS,"defillama","major_stablecoins")

def validate_source_status(name:str,payload:Any)->None:
    p=require_mapping(payload,f"sources.{name}")
    status=require_string(p.get("status"),f"sources.{name}.status")
    if status not in VALID_SOURCE_STATUSES: raise ValidationError(f"sources.{name}.status must be one of: {', '.join(sorted(VALID_SOURCE_STATUSES))}")
    if "fetched_at_utc" in p: parse_iso_timestamp(p["fetched_at_utc"],f"sources.{name}.fetched_at_utc")

def validate_market_shape(snapshot:dict[str,Any])->None:
    assets=require_list(require_mapping(snapshot.get("market"),"market").get("assets"),"market.assets")
    for i,a in enumerate(assets):
        item=require_mapping(a,f"market.assets[{i}]")
        require_string(item.get("id"),f"market.assets[{i}].id"); require_string(item.get("symbol"),f"market.assets[{i}].symbol")
        if "price_usd" not in item: raise ValidationError(f"market.assets[{i}].price_usd is required")

def validate_exchange_shape(snapshot:dict[str,Any])->None:
    ex=require_mapping(snapshot.get("exchange_crosscheck"),"exchange_crosscheck")
    if "strategy" in ex: require_string(ex["strategy"],"exchange_crosscheck.strategy")
    if ex.get("selected") is not None: require_string(ex["selected"],"exchange_crosscheck.selected")
    if "sources" in ex:
        for name,rows in require_mapping(ex["sources"],"exchange_crosscheck.sources").items():
            for i,row in enumerate(require_list(rows,f"exchange_crosscheck.sources.{name}")):
                item=require_mapping(row,f"exchange_crosscheck.sources.{name}[{i}]")
                require_string(item.get("symbol"),f"exchange_crosscheck.sources.{name}[{i}].symbol")
                if "price" in item and num(item.get("price")) is None: raise ValidationError(f"exchange_crosscheck.sources.{name}[{i}].price must be numeric")
        return
    if "binance" not in ex: raise ValidationError("exchange_crosscheck.sources or exchange_crosscheck.binance is required")
    for i,row in enumerate(require_list(ex["binance"],"exchange_crosscheck.binance")):
        item=require_mapping(row,f"exchange_crosscheck.binance[{i}]"); require_string(item.get("symbol"),f"exchange_crosscheck.binance[{i}].symbol")
        if "last_price" not in item: raise ValidationError(f"exchange_crosscheck.binance[{i}].last_price is required")

def validate_defi_shape(snapshot:dict[str,Any])->None:
    defi=require_mapping(snapshot.get("defi"),"defi")
    if "total_tvl_usd" not in defi: raise ValidationError("defi.total_tvl_usd is required")
    require_list(defi.get("stablecoins"),"defi.stablecoins")

def source_findings(snapshot:dict[str,Any],config:dict[str,Any],generated_at:datetime|None)->tuple[list[str],list[str]]:
    block:list[str]=[]; warn:list[str]=[]
    sources=snapshot.get("sources") if isinstance(snapshot.get("sources"),dict) else {}
    required=set(cfg_required_sources(config)); optional=set(cfg_enabled_exchanges(config)); tol=freshness_tolerance(config)
    for name,p in sources.items():
        if not isinstance(p,dict) or p.get("status")=="skipped": continue
        ts=try_ts(p.get("fetched_at_utc"))
        if ts is None:
            (block if name in required else warn if name in optional else warn).append(f"source {name} fetched_at_utc is missing or unparseable"); continue
        if generated_at and abs((generated_at-ts).total_seconds())/60>tol:
            (block if name in required else warn if name in optional else warn).append(f"source {name} fetched_at_utc is outside {tol} minute tolerance")
    for name in required:
        if name not in sources: block.append(f"required source missing: {name}")
    return block,warn

def market_findings(snapshot:dict[str,Any],config:dict[str,Any],generated_at:datetime|None)->tuple[list[str],list[str]]:
    block:list[str]=[]; warn:list[str]=[]; tol=freshness_tolerance(config)
    assets=(snapshot.get("market") or {}).get("assets") if isinstance(snapshot.get("market"),dict) else None
    if not isinstance(assets,list): return ["market.assets must be a list"],warn
    by_symbol={str(a.get("symbol")).upper():a for a in assets if isinstance(a,dict) and a.get("symbol")}
    for sym in required_symbols(config):
        a=by_symbol.get(sym)
        if not a: block.append(f"required market asset missing: {sym}"); continue
        checks=[("price_usd","> 0",lambda x:x>0),("market_cap_usd","> 0",lambda x:x>0),("volume_24h_usd",">= 0",lambda x:x>=0)]
        for field,label,pred in checks:
            v=num(a.get(field))
            if v is None or not pred(v): block.append(f"market asset {sym} {field} must be {label}")
        if num(a.get("market_cap_rank")) is None: block.append(f"market asset {sym} market_cap_rank is required")
        for field in MARKET_CHANGE_FIELDS:
            if num(a.get(field)) is None: block.append(f"market asset {sym} {field} is required and must be numeric")
        updated=try_ts(a.get("last_updated"))
        if updated is None: block.append(f"market asset {sym} last_updated is missing or unparseable")
        elif generated_at and abs((generated_at-updated).total_seconds())/60>tol: block.append(f"market asset {sym} last_updated is outside {tol} minute tolerance")
    return block,warn

def defi_findings(snapshot:dict[str,Any],config:dict[str,Any])->tuple[list[str],list[str]]:
    block:list[str]=[]; warn:list[str]=[]
    defi=snapshot.get("defi") if isinstance(snapshot.get("defi"),dict) else {}
    tvl=num(defi.get("total_tvl_usd"))
    if tvl is None or tvl<=0: block.append("defi.total_tvl_usd must be > 0")
    rows=defi.get("stablecoins")
    if not isinstance(rows,list) or not rows: return block+["defi.stablecoins must be a non-empty list"],warn
    by_symbol={str(r.get("symbol")).upper():r for r in rows if isinstance(r,dict) and r.get("symbol")}
    for sym in major_stablecoins(config):
        row=by_symbol.get(sym)
        if not row: block.append(f"major stablecoin missing: {sym}"); continue
        price=num(row.get("price_usd")); circ=num(row.get("circulating_usd"))
        if price is None or price<=0: block.append(f"major stablecoin {sym} price_usd must be > 0")
        elif abs(price-1.0)*100>peg_threshold(config): warn.append(f"major stablecoin {sym} price deviates from USD peg by {abs(price-1.0)*100:.2f}%")
        if circ is None or circ<=0: block.append(f"major stablecoin {sym} circulating_usd must be > 0")
    return block,warn

def collect_sanity_findings(snapshot:dict[str,Any],config:dict[str,Any])->tuple[list[str],list[str]]:
    run=snapshot.get("run") if isinstance(snapshot.get("run"),dict) else {}; generated=try_ts(run.get("generated_at_utc"))
    block=[] if generated else ["run.generated_at_utc is missing or unparseable"]; warn:list[str]=[]
    for b,w in (source_findings(snapshot,config,generated),market_findings(snapshot,config,generated),defi_findings(snapshot,config)):
        block.extend(b); warn.extend(w)
    return block,warn

def classify_snapshot_quality(snapshot:dict[str,Any],config:dict[str,Any]|None=None)->dict[str,Any]:
    config=config or {}; sources=snapshot.get("sources") if isinstance(snapshot.get("sources"),dict) else {}; ex=snapshot.get("exchange_crosscheck") if isinstance(snapshot.get("exchange_crosscheck"),dict) else {}
    required=cfg_required_sources(config); optional=cfg_enabled_exchanges(config); disabled=cfg_disabled_exchanges(config)
    block:list[str]=[]; warn:list[str]=[]
    for name in required:
        p=sources.get(name)
        if not isinstance(p,dict): block.append(f"required source missing: {name}"); continue
        if p.get("status")!="ok": block.append(f"required source {name} has status: {p.get('status')}")
    ok_optional=[]; selected=ex.get("selected")
    for name in optional:
        p=sources.get(name)
        if not isinstance(p,dict): warn.append(f"optional exchange source missing: {name}"); continue
        status=p.get("status")
        if status=="ok": ok_optional.append(name)
        elif status in {"warning","error"}: warn.append(f"optional exchange source {name} has status: {status}")
        elif status=="skipped" and not selected: warn.append(f"optional exchange source {name} was skipped before any source succeeded")
        elif status not in VALID_SOURCE_STATUSES: warn.append(f"optional exchange source {name} has unknown status: {status}")
    if optional and bool((config.get("exchange_crosschecks") or {}).get("required",False)) and not ok_optional: block.append("required exchange cross-check strategy had no successful source")
    elif optional and not ok_optional: warn.append("no optional exchange cross-check source succeeded")
    b,w=collect_sanity_findings(snapshot,config); block.extend(b); warn.extend(w)
    for item in snapshot.get("errors",[]) if isinstance(snapshot.get("errors"),list) else []:
        text=str(item)
        (block if any(text.startswith(f"{name} ") for name in required) else warn).append(text)
    block=list(dict.fromkeys(block)); warn=list(dict.fromkeys(warn))
    status="invalid" if block else "valid-degraded" if warn else "valid-ok"
    return {"status":status,"required_sources":required,"optional_exchange_sources":optional,"disabled_sources":disabled,"blocking_issues":block,"non_blocking_warnings":warn}

def validate_quality(snapshot:dict[str,Any],config:dict[str,Any])->dict[str,Any]:
    computed=classify_snapshot_quality(snapshot,config); embedded=snapshot.get("quality")
    if embedded is not None:
        payload=require_mapping(embedded,"quality"); status=require_string(payload.get("status"),"quality.status")
        if status not in VALID_QUALITY_STATUSES: raise ValidationError(f"quality.status must be one of: {', '.join(sorted(VALID_QUALITY_STATUSES))}")
        if status!=computed["status"]: raise ValidationError(f"quality.status is {status}, but computed quality status is {computed['status']}")
        require_list(payload.get("blocking_issues",[]),"quality.blocking_issues"); require_list(payload.get("non_blocking_warnings",[]),"quality.non_blocking_warnings")
    if computed["status"]=="invalid": raise ValidationError("snapshot quality is invalid: "+"; ".join(computed["blocking_issues"]))
    return computed

def validate_snapshot(path:Path,config:dict[str,Any]|None=None)->dict[str,Any]:
    try: snapshot=json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc: raise ValidationError(f"invalid JSON: {exc}") from exc
    snapshot=require_mapping(snapshot,"$"); missing=sorted(REQUIRED_TOP_LEVEL_KEYS-set(snapshot))
    if missing: raise ValidationError(f"missing top-level keys: {', '.join(missing)}")
    require_string(snapshot.get("schema_version"),"schema_version"); run=require_mapping(snapshot.get("run"),"run")
    missing_run=sorted(REQUIRED_RUN_KEYS-set(run))
    if missing_run: raise ValidationError(f"missing run keys: {', '.join(missing_run)}")
    parse_iso_timestamp(run["generated_at_utc"],"run.generated_at_utc"); parse_iso_timestamp(run["generated_at_local"],"run.generated_at_local")
    require_string(run["timezone"],"run.timezone"); require_string(run["cadence"],"run.cadence")
    sources=require_mapping(snapshot.get("sources"),"sources")
    if not sources: raise ValidationError("sources must include at least one source status")
    for name,payload in sources.items(): validate_source_status(name,payload)
    validate_market_shape(snapshot); validate_exchange_shape(snapshot); validate_defi_shape(snapshot)
    require_list(snapshot.get("warnings"),"warnings"); require_list(snapshot.get("errors"),"errors")
    return validate_quality(snapshot,config or {})

def iter_snapshot_files(path:Path)->list[Path]:
    if path.is_file(): return [path]
    if path.is_dir(): return sorted(path.rglob("*_source_snapshot.json"))
    raise SystemExit(f"Path not found: {path}")

def main()->int:
    args=parse_args()
    try: config=load_config(Path(args.config))
    except ValidationError as exc: print(f"{args.config}: {exc}",file=sys.stderr); return 1
    files=iter_snapshot_files(Path(args.path))
    if not files: print(f"No *_source_snapshot.json files found under {args.path}",file=sys.stderr); return 1
    failures=[]; counts={s:0 for s in sorted(VALID_QUALITY_STATUSES)}; warnings=[]
    for path in files:
        try: q=validate_snapshot(path,config)
        except ValidationError as exc: failures.append(f"{path}: {exc}"); continue
        counts[q["status"]]+=1
        if q["status"]=="valid-degraded": warnings.extend(f"{path}: {w}" for w in q["non_blocking_warnings"])
    if failures:
        for f in failures: print(f,file=sys.stderr)
        return 1
    summary=", ".join(f"{k}={v}" for k,v in sorted(counts.items()) if v)
    print(f"Validated {len(files)} source snapshot file(s). Quality: {summary or 'none'}.")
    for w in warnings: print(f"warning: {w}",file=sys.stderr)
    return 0

if __name__=="__main__": raise SystemExit(main())
