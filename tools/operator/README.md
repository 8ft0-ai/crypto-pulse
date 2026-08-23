# CryptoPulse operator toolkit

This directory contains the read-only `operator-toolkit/v1` foundation approved under issue #509.
It is an evidence and diagnostics interface, not a workflow engine and not a repository administration surface.

## Slice A commands

```bash
<trusted-runtime-root>/tools/operator/cp doctor [--json|--evidence]
<trusted-runtime-root>/tools/operator/cp snapshot [--repo PATH] [--json|--evidence]
```

`doctor` checks the local prerequisites and authenticated read capability. `snapshot` records bounded local repository observations together with authoritative remote `main` identity/protection information when GitHub exposes it. Neither command pushes, mutates refs, dispatches workflows, changes settings, deploys, publishes or reads secret values.

## Trusted runtime requirement

Governed evidence must never be produced by running `./tools/operator/cp` from an arbitrary working tree. The runtime root must be a clean immutable checkout of an exact reviewed CryptoPulse commit that has entered protected `main` (or an equivalently reviewed immutable installation). Candidate copies of the launcher, package and `operator.toml` are inspection data only.

A typical owner-local materialisation, after the implementation commit has merged, is:

```bash
git fetch origin main
RUNTIME_SHA=<exact-reviewed-commit-that-entered-main>
RUNTIME_ROOT="$HOME/.local/share/cryptopulse/operator/$RUNTIME_SHA"
git cat-file -e "$RUNTIME_SHA^{commit}"
git worktree add --detach "$RUNTIME_ROOT" "$RUNTIME_SHA"
git -C "$RUNTIME_ROOT" status --porcelain=v1 --untracked-files=all
"$RUNTIME_ROOT/tools/operator/cp" doctor --evidence
```

The final `git status` must be empty. The toolkit independently binds its commit/tree/launcher/config/package identities and verifies through read-only GitHub evidence that the runtime commit is identical to, or an ancestor of, current protected `main`. A dirty runtime is an `ERROR`; unavailable or ambiguous protected-main provenance is `INCOMPLETE`, never `PASS`.

Do not place candidate directories on `PYTHONPATH`, source candidate shell files, or run a candidate copy of the launcher. The launcher uses Python isolated mode and clears ambient Python path variables; package/config resolution is rooted at the trusted launcher directory.

## Output and exit contract

Evidence uses `CRYPTOPULSE_OPERATOR_EVIDENCE/v1` and binds both the inspected state and the producing runtime identity. The canonical JSON payload is UTF-8 with sorted keys and compact separators; its SHA-256 is transport integrity only.

Exit codes:

- `0` — `PASS`
- `2` — `FAIL`
- `3` — `INCOMPLETE`
- `4` — expected invocation/prerequisite/authentication `ERROR`
- `5` — unexpected internal `ERROR`

Raw API payloads, headers, subprocess environments and credential values are not emitted as governed evidence.
