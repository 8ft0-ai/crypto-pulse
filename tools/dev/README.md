# CryptoPulse developer toolkit

`tools/dev/` is the repository-owned working-tree developer plane.

The commands here intentionally execute the current checkout. Their output is useful local development and validation output only; it is **not** trusted `CRYPTOPULSE_OPERATOR_EVIDENCE`. Authoritative GitHub, protected-main and CI evidence remains the responsibility of [`tools/operator/cp`](../operator/README.md).

## Supported environment

Primary owner platform: macOS. The launcher keeps inexpensive POSIX compatibility for Linux and WSL.

Prerequisites:

- Git;
- Python 3.12 or later;
- a CryptoPulse worktree whose `origin` is the canonical `8ft0-ai/crypto-pulse` GitHub repository;
- network access only when `bootstrap` needs to install dependencies.

GitHub CLI is not required.

## Slice A commands

Run commands by path from anywhere inside the worktree:

```bash
./tools/dev/cp-dev bootstrap
./tools/dev/cp-dev doctor
./tools/dev/cp-dev check
```

### `bootstrap`

Creates or repairs the repository-local `.venv` and installs `requirements-dev.txt`.

```bash
./tools/dev/cp-dev bootstrap
./tools/dev/cp-dev bootstrap --recreate
```

`--recreate` may remove only the exact repository-local `.venv`. It refuses symlinked, escaped or unproven targets. Bootstrap never installs into global/user Python, edits shell startup files, persists activation or removes unrelated directories.

### `doctor`

Runs read-only local diagnostics for Git/repository identity, host Python, `.venv`, declared dependencies and tracked `_site/` content. A dirty working tree is allowed. An untracked `_site/` directory is reported as disposable state rather than a failure.

`doctor` does not contact GitHub and does not require `gh`.

### `check`

Runs the local pre-PR mirror using `.venv/bin/python`:

1. `python -m unittest discover -s tests`;
2. `python scripts/validate_documentation.py`;
3. reject tracked `_site/` content;
4. `python -m site_generator`;
5. verify the expected generated artefacts.

GitHub Actions remains the authoritative PR acceptance gate and executes these checks directly rather than delegating acceptance to candidate-controlled `cp-dev check`.

## Exit codes

| Code | Meaning |
| ---: | --- |
| `0` | Command succeeded. |
| `2` | The requested command/check completed with one or more failures. |
| `3` | Usage, prerequisite, repository or environment error prevented valid execution. |
| `4` | Unexpected internal error. |

Human output uses `OK`, `FAILED` and `ERROR`. It deliberately does not use the operator toolkit's evidence envelope or trust semantics.

## Troubleshooting

If `.venv` is missing or invalid:

```bash
./tools/dev/cp-dev bootstrap --recreate
```

If local validation differs from CI, treat CI as authoritative and update the developer mirror only through reviewed repository changes.

Slice B commands such as `test`, `build`, `serve` and `clean` are not part of Slice A.
