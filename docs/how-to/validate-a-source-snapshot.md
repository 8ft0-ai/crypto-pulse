# Validate a source snapshot

> **Mode:** How-to  
> **Audience:** CryptoPulse contributors, operators and reviewers  
> **Outcome:** Validate one checked-in source snapshot or a directory of snapshots against the current schema and quality configuration.

## Validate one checked-in snapshot

From the repository root, run:

```bash
python scripts/validate_crypto_snapshot.py \
  data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json
```

The command uses [`config/crypto_sources.yml`](../../config/crypto_sources.yml) by default. A successful result prints a summary similar to:

```text
Validated 1 source snapshot file(s). Quality: valid-ok=1.
```

The exact accepted quality may be `valid-ok` or `valid-degraded`, depending on the checked-in snapshot and current configuration.

## Validate a directory

Pass a directory to validate every matching snapshot beneath it:

```bash
python scripts/validate_crypto_snapshot.py data/crypto/hourly/2026/07/08
```

Only files ending in `_source_snapshot.json` are selected recursively.

## Use an explicit configuration

```bash
python scripts/validate_crypto_snapshot.py \
  data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json \
  --config config/crypto_sources.yml
```

Use a reviewed repository configuration. Do not create a weaker local configuration merely to make an invalid snapshot pass.

## Interpret the result

| Result | Command behaviour | Meaning |
| --- | --- | --- |
| `valid-ok` | Exit status `0` | Required structure and quality checks pass without non-blocking warnings. |
| `valid-degraded` | Exit status `0`, warnings on standard error | The snapshot is structurally valid and usable under the configured degraded-data policy, but limitations must remain visible. |
| `invalid` | Exit status `1`, failure details on standard error | A blocking source, structure, freshness, consistency or quality rule failed. |

The validator also returns exit status `1` when the path does not exist, the directory contains no matching snapshots, the configuration is invalid or the JSON cannot be parsed.

## Review degraded output

For `valid-degraded`, read every `warning:` line and inspect the snapshot's embedded `quality` block. Do not convert missing or degraded evidence into a positive market conclusion.

The validator checks that any embedded quality status agrees with the status recomputed from the current configuration. A mismatch is rejected.

## Validate before dependent work

Run source validation before:

- building an evidence bundle;
- dispatching a governed-analysis workflow;
- generating or reviewing a report from the snapshot;
- changing source-quality documentation or fixtures.

The validation command performs no network collection and does not modify the snapshot.

For the complete repository layout, see [Repository layout](../reference/repository-layout.md). For the detailed quality states and source-criticality rules, see [Source snapshot quality](../reference/source-snapshot-quality.md).
