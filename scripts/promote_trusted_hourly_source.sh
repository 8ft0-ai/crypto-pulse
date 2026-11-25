#!/usr/bin/env bash
# Opt-in, accepted-hour source-only promotion. No hourly Markdown output.
# Requires an independently verified immutable accepted-hour + intent bundle.
set -euo pipefail

: "${GH_READ_TOKEN:?}"
: "${GH_APP_TOKEN:?}"
: "${APP_SLUG:?}"
: "${SOURCE_PATH:?}"
: "${SOURCE_HOUR:?}"
: "${SOURCE_SHA256:?}"
: "${SOURCE_FILE:?}"
: "${GITHUB_REPOSITORY:?}"
: "${GITHUB_RUN_ID:?}"
: "${GITHUB_RUN_ATTEMPT:?}"
: "${GITHUB_SHA:?}"
: "${RUNNER_TEMP:?}"

[[ "$GITHUB_REF" == "refs/heads/main" ]]
[[ "$GITHUB_EVENT_NAME" == "workflow_dispatch" || "$GITHUB_EVENT_NAME" == "schedule" ]]
[[ "$SOURCE_SHA256" =~ ^[0-9a-f]{64}$ ]]
[[ "$SOURCE_HOUR" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:00:00Z$ ]]
[[ "$SOURCE_PATH" =~ ^data/crypto/hourly/[0-9]{4}/[0-9]{2}/[0-9]{2}/[A-Za-z0-9_-]+_source_snapshot\.json$ ]]
[[ "$GITHUB_RUN_ID" =~ ^[1-9][0-9]*$ ]]
[[ "$GITHUB_RUN_ATTEMPT" == "1" ]]
[[ "$GITHUB_SHA" =~ ^[0-9a-f]{40}$ ]]

gh_read() { GH_TOKEN="$GH_READ_TOKEN" gh api "$@"; }
gh_app() { GH_TOKEN="$GH_APP_TOKEN" gh api "$@"; }
proof="$RUNNER_TEMP/source-promotion-proof.json"
current_main="$(gh_read "/repos/$GITHUB_REPOSITORY/commits/main" --jq '.sha')"
[[ "$current_main" =~ ^[0-9a-f]{40}$ ]]

# Read-only token for source fetch. No default checkout credentials persist.
read_auth="$(printf 'x-access-token:%s' "$GH_READ_TOKEN" | base64 -w0)"
git -c "http.https://github.com/.extraheader=AUTHORIZATION: basic $read_auth" \
  fetch --no-tags origin main
[[ "$(git rev-parse refs/remotes/origin/main)" == "$current_main" ]]
git merge-base --is-ancestor "$GITHUB_SHA" "$current_main"

if git cat-file -e "$current_main:$SOURCE_PATH" 2>/dev/null; then
  prior_digest="$(git show "$current_main:$SOURCE_PATH" | sha256sum | awk '{print $1}')"
  [[ "$prior_digest" == "$SOURCE_SHA256" ]] || {
    echo "Conflicting source snapshot already on protected main." >&2
    exit 1
  }
  jq -nc --arg status "already-trusted-identical" --arg path "$SOURCE_PATH" \
    --arg sha256 "$SOURCE_SHA256" --arg main "$current_main" \
    '{status:$status,source_path:$path,snapshot_sha256:$sha256,protected_main_sha:$main}' > "$proof"
  echo "Accepted hour already on protected main with identical bytes; no merge."
  exit 0
fi
[[ "$(sha256sum "$SOURCE_FILE" | awk '{print $1}')" == "$SOURCE_SHA256" ]]
# No second trusted-main source file may claim the same UTC observation hour.
# The source path check above handles identical pre-existing files idempotently.
existing_hour_count="$(SOURCE_HOUR="$SOURCE_HOUR" python - <<'PYCODE'
import os,sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "scripts"))
from deterministic_site_publication import count_observation_hour
print(count_observation_hour(Path.cwd(), os.environ["SOURCE_HOUR"]))
PYCODE
)"
[[ "$existing_hour_count" == "0" ]] || {
  echo "Different protected-main source already claims the same UTC hour." >&2
  exit 1
}
branch="automation/source-only-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
git checkout -b "$branch" "$current_main"
mkdir -p "$(dirname "$SOURCE_PATH")"
cp "$SOURCE_FILE" "$SOURCE_PATH"
git add -- "$SOURCE_PATH"
[[ "$(git diff --cached --name-only)" == "$SOURCE_PATH" ]]
git config user.name "${APP_SLUG}[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git commit -m "Promote verified hourly source evidence ${GITHUB_RUN_ID}"
candidate_head="$(git rev-parse HEAD)"
[[ "$candidate_head" =~ ^[0-9a-f]{40}$ ]]
[[ "$(git diff --name-only "$current_main" "$candidate_head")" == "$SOURCE_PATH" ]]

app_auth="$(printf 'x-access-token:%s' "$GH_APP_TOKEN" | base64 -w0)"
git -c "http.https://github.com/.extraheader=AUTHORIZATION: basic $app_auth" \
  push --force-with-lease="refs/heads/$branch:" origin "HEAD:refs/heads/$branch"
[[ "$(gh_app "/repos/$GITHUB_REPOSITORY/git/ref/heads/$branch" --jq '.object.sha')" == "$candidate_head" ]]

pr_body="$RUNNER_TEMP/source-only-pr.md"
cat > "$pr_body" <<EOF
## Trusted accepted-hour source evidence only

Immutable ingestion run: ${GITHUB_RUN_ID}, attempt ${GITHUB_RUN_ATTEMPT}.
Exact source path: \`${SOURCE_PATH}\`.
Snapshot SHA-256: \`${SOURCE_SHA256}\`.
Expected protected-main base: \`${current_main}\`.

The preceding ingestion job accepted one UTC-hour source receipt and uploaded an immutable intent and snapshot. This job independently revalidated all three, committed only the approved source JSON, and requires exact-head GitHub CI before App-authorised protected-main promotion.

No hourly market report, model inference, cadence change or site output is included.
EOF
GH_TOKEN="$GH_APP_TOKEN" gh pr create --repo "$GITHUB_REPOSITORY" \
  --base main --head "$branch" --draft \
  --title "Promote accepted hourly crypto source ${GITHUB_RUN_ID}" \
  --body-file "$pr_body"
pr_number="$(GH_TOKEN="$GH_APP_TOKEN" gh pr list --repo "$GITHUB_REPOSITORY" \
  --state open --head "$branch" --json number --jq '.[0].number')"
[[ "$pr_number" =~ ^[1-9][0-9]*$ ]]
check_pr() {
  gh_app "/repos/$GITHUB_REPOSITORY/pulls/$pr_number" | jq -e \
    --arg head "$candidate_head" --arg base "$current_main" --arg branch "$branch" \
    --arg author "${APP_SLUG}[bot]" --argjson draft "$1" \
    '.state == "open" and .draft == $draft
     and .head.sha == $head and .head.ref == $branch
     and .base.ref == "main" and .base.sha == $base
     and .head.repo.id == .base.repo.id and .user.login == $author' >/dev/null
}
check_pr true
gh_app "/repos/$GITHUB_REPOSITORY/pulls/$pr_number/files?per_page=100" | jq -e \
  --arg path "$SOURCE_PATH" \
  'length == 1 and .[0].filename == $path and .[0].status == "added"
   and .[0].deletions == 0' >/dev/null

# The App-authored PR triggers the normal independent GitHub Actions PR CI.
# Do not silently treat creation or source-job success as CI acceptance.
ci_run_id=""
ci_ok=0
for attempt in $(seq 1 80); do
  runs="$(gh_read --method GET "/repos/$GITHUB_REPOSITORY/actions/runs" \
    -f event=pull_request -f "head_sha=$candidate_head" -F per_page=100)"
  ci_row="$(jq -c --arg sha "$candidate_head" --arg branch "$branch" \
    '[.workflow_runs[] | select(.name == "Validate CryptoPulse PR"
      and .head_sha == $sha and .head_branch == $branch)] | sort_by(.id) | last // empty' <<<"$runs")"
  if [[ -n "$ci_row" ]]; then
    state="$(jq -r '.status' <<< "$ci_row")"
    conclusion="$(jq -r '.conclusion // ""' <<< "$ci_row")"
    ci_run_id="$(jq -r '.id' <<< "$ci_row")"
    if [[ "$state" == "completed" ]]; then
      [[ "$conclusion" == "success" ]] || {
        echo "Exact-head independent PR CI did not pass." >&2
        exit 1
      }
      ci_ok=1
      break
    fi
  fi
  sleep 12
done
[[ "$ci_ok" == 1 ]] || {
  echo "Exact-head CI acceptance not available within bounded wait." >&2
  exit 1
}
gh_read "/repos/$GITHUB_REPOSITORY/commits/$candidate_head/check-runs?per_page=100" | jq -e \
  '[.check_runs[] | select(.name == "Build site and check generated output"
   and .app.slug == "github-actions" and .conclusion == "success")] | length == 1' >/dev/null

# Final independent identity, scope and main-base rechecks, before and after
# marking ready. Protected main can only be updated by the existing App route.
[[ "$(gh_read "/repos/$GITHUB_REPOSITORY/commits/main" --jq '.sha')" == "$current_main" ]]
check_pr true
GH_TOKEN="$GH_APP_TOKEN" gh pr ready "$pr_number" --repo "$GITHUB_REPOSITORY"
check_pr false
[[ "$(gh_read "/repos/$GITHUB_REPOSITORY/commits/main" --jq '.sha')" == "$current_main" ]]
gh_app "/repos/$GITHUB_REPOSITORY/pulls/$pr_number/files?per_page=100" | jq -e \
  --arg path "$SOURCE_PATH" \
  'length == 1 and .[0].filename == $path and .[0].status == "added"
   and .[0].deletions == 0' >/dev/null
merge="$(gh_app --method PUT "/repos/$GITHUB_REPOSITORY/pulls/$pr_number/merge" \
  -f "sha=$candidate_head" -f merge_method=merge)"
merged_sha="$(jq -er '.sha' <<<"$merge")"
[[ "$(jq -r '.merged' <<<"$merge")" == "true" ]]
[[ "$merged_sha" =~ ^[0-9a-f]{40}$ ]]
[[ "$(gh_read "/repos/$GITHUB_REPOSITORY/commits/main" --jq '.sha')" == "$merged_sha" ]]
gh_read "/repos/$GITHUB_REPOSITORY/commits/$merged_sha" | jq -e \
  --arg base "$current_main" \
  '.parents[0].sha == $base and (.parents | length) == 2' >/dev/null
# Re-read published blob from GitHub's source API, not the local candidate.
published="$RUNNER_TEMP/published-source.json"
gh_read -H "Accept: application/vnd.github.raw+json" \
  "/repos/$GITHUB_REPOSITORY/contents/$SOURCE_PATH?ref=$merged_sha" > "$published"
[[ "$(sha256sum "$published" | awk '{print $1}')" == "$SOURCE_SHA256" ]]

jq -nc --arg status "merged" --arg path "$SOURCE_PATH" \
  --arg sha256 "$SOURCE_SHA256" --arg source_run "$GITHUB_RUN_ID" \
  --arg pr "$pr_number" --arg base "$current_main" \
  --arg head "$candidate_head" --arg merged "$merged_sha" \
  --arg ci_run "$ci_run_id" \
  '{status:$status,source_path:$path,snapshot_sha256:$sha256,
    source_run_id:$source_run,pull_request_number:$pr,
    expected_main_base_sha:$base,candidate_head_sha:$head,
    merge_commit_sha:$merged,independent_ci_run_id:$ci_run}' > "$proof"
echo "SOURCE_ONLY_PROTECTED_MAIN_ACCEPTANCE_PASS"
