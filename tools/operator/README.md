# CryptoPulse operator toolkit

This directory contains the read-only `operator-toolkit/v1` approved under issue #509.
It is an evidence and diagnostics interface, not a workflow engine and not a repository administration surface.

## Slice A commands

```bash
<trusted-runtime-root>/tools/operator/cp doctor [--json|--evidence]
<trusted-runtime-root>/tools/operator/cp snapshot [--repo PATH] [--json|--evidence]
```

`doctor` checks the local prerequisites and authenticated read capability. `snapshot` records bounded local repository observations together with authoritative remote `main` identity/protection information when GitHub exposes it. Neither command pushes, mutates refs, dispatches workflows, changes settings, deploys, publishes or reads secret values.

## Slice B review-support commands

```bash
<trusted-runtime-root>/tools/operator/cp candidate <PR> [--json|--evidence]
<trusted-runtime-root>/tools/operator/cp ci <run-id> [--json|--evidence]
<trusted-runtime-root>/tools/operator/cp review-pack <PR> [--json|--evidence]
```

`candidate` reconstructs the authoritative PR base/head/tree/parent identities together with complete commit, changed-file, check, review, issue-comment, review-comment and review-thread state. `ci` reconstructs one exact GitHub Actions run and its attempt-specific jobs and steps. `review-pack` aggregates a current PR candidate with the required exact-head Actions evidence needed for review.

Slice B is evidence-only. Candidate-controlled repository content is data and is never checked out, imported, sourced, built, tested or otherwise executed. In particular, `review-pack` does not run candidate validation locally and does not create a candidate worktree for execution. If current protected-main/base binding, required-check context plus App binding, exact-head Actions provenance, complete pagination or safe bounded representation cannot be proved, the command returns `INCOMPLETE` rather than falling back to local execution. A completed required check or bound required run that conclusively fails is reported as `FAIL`.

Review/comment bodies are included only within fixed trusted-code size budgets and only when the defensive evidence sanitizer accepts them. A body that cannot be represented safely is omitted with bounded identity metadata and makes the affected evidence incomplete. Workflow logs are not emitted or persisted; failure context is restricted to bounded job/step metadata.

## Slice C privileged-readback commands

```bash
<trusted-runtime-root>/tools/operator/cp auth [--json|--evidence]
<trusted-runtime-root>/tools/operator/cp protection [--json|--evidence]
<trusted-runtime-root>/tools/operator/cp environment <name> [--json|--evidence]
<trusted-runtime-root>/tools/operator/cp publication [--json|--evidence]
```

Slice C remains read-only and is intended for an already-authorised owner/admin GitHub credential. `auth` reports whether that identity can completely read each privileged GitHub surface required by this slice without echoing tokens or relying only on token-scope strings. A valid login with insufficient or unsupported privileged read access is `INCOMPLETE`, not `PASS`.

`protection` reconstructs current protected-`main` identity, classic required-status-check strictness and context/App bindings, complete repository ruleset enumeration, and typed detail for the deterministic-publication ruleset. `environment` reconstructs one URL-encoded environment name together with complete deployment branch policies, Actions variables, and secret names/metadata only. Secret values are never requested.

`publication` composes fresh current readback for the inert deterministic-publication control plane: protected `main`, the strict GitHub-Actions-bound required check, ruleset `20795849`, publication App `4618782` / `cryptopulse-deterministic-pub`, environment `deterministic-publication-control`, protected environment secret-name presence, App identity variables, repository activation state, and the required exact installation-scope invariant.

GitHub does not currently expose that App installation scope through the permitted ordinary owner/admin credential. The documented `GET /user/installations` and `GET /user/installations/{installation_id}/repositories` representations require a GitHub App user access token, which is outside the accepted Slice C credential boundary. The toolkit therefore does not call those endpoints, does not authenticate as the publication App, and does not use a private key, JWT or installation token. `auth` marks the installation-scope capabilities unreadable and `publication` preserves all otherwise readable current control-plane evidence while returning overall `INCOMPLETE` with `publication-app-installation-scope-incomplete`. The exact scope invariant is not weakened, inferred from historical provisioning evidence, or converted into `PASS`/`FAIL` without current proof.

`DETERMINISTIC_PUBLICATION_ACTIVATION` must remain absent or `disabled`. A readable `pilot` or `recurring` value is retained as a failed assertion, but the composite remains `INCOMPLETE` while the required installation-scope assertion is unreadable. `DETERMINISTIC_PUBLICATION_PILOT_RUN_ID`, when present while activation is disabled, is reported only as bounded configuration metadata and does not create authority.

All supported Slice C collection reads are centrally paginated and fail closed on permission denial, malformed representation, count mismatch, duplicate/ambiguous variable names or any other inability to prove completeness. `protection` and `environment` remain independently usable and may reach `PASS` or `FAIL` from their own complete evidence. Candidate-controlled values are never executed, and no Slice C command changes settings, dispatches workflows, merges, deploys or publishes.

After a separately reviewed and authorised Slice C merge, the operational owner-local proof should use the exact merged trusted runtime and run once:

```bash
<trusted-runtime-root>/tools/operator/cp auth --evidence
<trusted-runtime-root>/tools/operator/cp protection --evidence
<trusted-runtime-root>/tools/operator/cp environment deterministic-publication-control --evidence
<trusted-runtime-root>/tools/operator/cp publication --evidence
```

For the current owner/admin credential model, `auth` and `publication` are expected to report the stable installation-scope `INCOMPLETE` boundary until GitHub exposes an authorised read representation or a separately governed credential design is accepted. `protection` and `environment` should still be evaluated normally. Any other `INCOMPLETE`, any failed assertion, unexpected credential-like output or state drift is evidence to adjudicate rather than a reason to fall back to historical provisioning prose.

## Slice D project-proof commands

```bash
<trusted-runtime-root>/tools/operator/cp pages [--json|--evidence]
<trusted-runtime-root>/tools/operator/cp live [--json|--evidence]
<trusted-runtime-root>/tools/operator/cp provenance [--json|--evidence]
<trusted-runtime-root>/tools/operator/cp contracts [--json|--evidence]
```

Slice D consumes the repository's existing deterministic publication and proof authorities; it does not create a second deployment or live-site verifier.

`pages` completely enumerates `Publish CryptoPulse Pages` workflow runs, selects the newest applicable `main` run deterministically, requires successful `build` and `deploy` jobs, and reports the exact deployed commit/run/attempt. If protected `main` has advanced since that deployment, the command calls the deployment publication-equivalent only when complete GitHub compare evidence proves that every intervening changed path is outside the frozen Pages trigger/path set. A Pages-affecting advance without a successful newer matching deployment is `FAIL`; incomplete comparison or run evidence is `INCOMPLETE`.

`live` first consumes the same successful Pages proof primitive, then completely enumerates `Verify CryptoPulse Live Pages` runs. An exact `workflow_dispatch` run can prove its inspected commit from the run's own `head_sha`, so a completed successful run at the effective Pages deployment SHA may proceed to the expected `verify` job and retained-artefact checks. For the repository's automatic `workflow_run` path, however, the Actions run REST metadata exposes the triggered verifier run's own default-branch execution SHA, not the triggering Pages run's `github.event.workflow_run.head_sha` that `verify-live-pages.yml` actually checks out and records as `DEPLOYMENT_COMMIT`. Slice D does not download/reinterpret `result.json`, parse workflow logs, or change the verifier workflow to create a new binding representation, so automatic `workflow_run` evidence fails closed as `INCOMPLETE` with `live-workflow-run-source-binding-unavailable` rather than treating the outer run SHA as deployment proof. The selected exact-bound dispatch run must also have one successful `verify` job and exactly one retained, non-expired `cryptopulse-live-site-evidence` artefact whose run/head metadata matches that selected verification run. The command never dispatches or reruns the workflow itself and makes no separate CDN observation.

`provenance` aggregates the exact chain already proved by those primitives: trusted operator runtime → protected `main` → effective Pages deployment → exact-bound live verification → retained live-evidence artefact. It does not weaken an `INCOMPLETE` live binding, inspect mutable rolling branches, execute candidate/site code, infer market/report provenance, or substitute historical issue prose for current GitHub evidence.

`contracts` reports the reviewed project contract index and fixed operational boundaries used to interpret Slice D evidence:

```text
deterministic-site-publication/v3
phase15-public-temporal-evidence/v1
reader-facing-evidence-experience/v1
operator-toolkit/v1

publication authority: main only
publication activation expectation: absent/disabled
Pages workflow: Publish CryptoPulse Pages / .github/workflows/pages.yml
live verification workflow: Verify CryptoPulse Live Pages / .github/workflows/verify-live-pages.yml
live evidence artefact: cryptopulse-live-site-evidence
public base URL: https://8ft0-ai.github.io/crypto-pulse/
```

The Pages trigger/path set used by `pages` is trusted non-secret operator configuration and is regression-checked against `.github/workflows/pages.yml`; later workflow drift therefore cannot silently change the equivalence calculation without repository validation noticing. All Slice D GitHub calls remain fixed read-only `GET` surfaces with complete pagination. None of these commands merges, dispatches/reruns workflows, changes publication activation, writes settings/credentials, deploys or publishes.

After a separately reviewed and authorised Slice D merge, the operational owner-local proof should use the exact merged trusted runtime and run once:

```bash
<trusted-runtime-root>/tools/operator/cp pages --evidence
<trusted-runtime-root>/tools/operator/cp live --evidence
<trusted-runtime-root>/tools/operator/cp provenance --evidence
<trusted-runtime-root>/tools/operator/cp contracts --evidence
```

An automatic `workflow_run` `INCOMPLETE` with `live-workflow-run-source-binding-unavailable` is the expected fail-closed boundary under the current accepted metadata-only design. Any other `INCOMPLETE`, any `FAIL`, sanitisation rejection or identity drift is evidence to adjudicate rather than bypass.

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

The final `git status` must be empty. The launcher and runtime checks also compare the operator index/worktree with `HEAD`, reject untracked operator files and reject hidden index states such as `assume-unchanged`/`skip-worktree`; the recorded launcher/config/package identities are therefore not accepted merely because ordinary status output is empty. The toolkit then verifies through read-only GitHub evidence that the runtime commit is identical to, or an ancestor of, current protected `main`. A dirty or object-mismatched runtime is an `ERROR`; unavailable or ambiguous protected-main provenance is `INCOMPLETE`, never `PASS`.

Do not place candidate directories on `PYTHONPATH`, source candidate shell files, or run a candidate copy of the launcher. The launcher uses Python isolated mode, clears ambient Python path variables and ignores ambient `PATH` for interpreter/Git selection. Supported macOS executable locations are the fixed system/Homebrew paths encoded by the launcher/process adapter (`/usr/bin`, `/usr/local/bin`, `/opt/homebrew/bin`, plus the Python.org `.../Versions/Current/bin/python3` location). Python must be >= 3.12. `gh` must resolve from one of those approved absolute system/Homebrew locations; candidate/current-directory executables are not selected.

## Output and exit contract

Evidence uses `CRYPTOPULSE_OPERATOR_EVIDENCE/v1` and binds both the inspected state and the producing runtime identity. The canonical JSON payload is UTF-8 with sorted keys and compact separators; its SHA-256 is transport integrity only.

Exit codes:

- `0` — `PASS`
- `2` — `FAIL`
- `3` — `INCOMPLETE`
- `4` — expected invocation/prerequisite/authentication `ERROR`
- `5` — unexpected internal `ERROR`

Raw API payloads, headers, subprocess environments, workflow logs and credential values are not emitted as governed evidence.
