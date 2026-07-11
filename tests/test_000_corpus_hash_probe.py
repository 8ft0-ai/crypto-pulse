from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATHS = (
    "data/crypto/hourly/2026/07/08/1434_AEST_source_snapshot.json",
    "data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json",
    "data/crypto/hourly/2026/07/08/2031_AEST_source_snapshot.json",
)
values = "\n".join(f"{path}={hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}" for path in PATHS)
raise SystemExit("CORPUS_HASH_LOCKS\n" + values)
