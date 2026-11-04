// Cloudflare Cron delivery only. GitHub retains all source validation and publication authority.
// This Worker has no HTTP handler and must not be deployed without separate cutover approval.
const API = "https://api.github.com/repos/8ft0-ai/crypto-pulse";
const WORKFLOW = "ingest-crypto-sources.yml";
const TITLE_PREFIX = "Crypto source ingestion ";

export function slotForEvent(scheduledTime, nowMs) {
  if (!Number.isSafeInteger(scheduledTime) || !Number.isFinite(nowMs)) {
    throw new Error("invalid scheduledTime/clock");
  }
  const scheduled = new Date(scheduledTime);
  if (Number.isNaN(scheduled.getTime()) || scheduled.getUTCMinutes() !== 7
      || scheduled.getUTCSeconds() !== 0 || scheduled.getUTCMilliseconds() !== 0) {
    throw new Error("cron event is not an exact UTC :07 slot");
  }
  const hourStart = Date.UTC(
    scheduled.getUTCFullYear(), scheduled.getUTCMonth(), scheduled.getUTCDate(),
    scheduled.getUTCHours(), 0, 0, 0,
  );
  if (nowMs < scheduledTime || nowMs >= hourStart + 30 * 60_000) {
    throw new Error("slot is early or after the frozen :30 UTC deadline");
  }
  const hour = new Date(hourStart).toISOString().replace(".000Z", "Z");
  const correlation = "cp-" + hour.slice(0, 13).replace(/[-T]/g, "");
  return { hour, correlation };
}

function receipt(log, fields) {
  // Never include request headers, credential, response body or source observations.
  log.log(JSON.stringify({ contract: "crypto-hour-dispatch/v1", ...fields }));
}

export async function dispatchSlot(controller, env, {
  nowMs = Date.now(), fetchImpl = fetch, log = console,
} = {}) {
  const scheduledTime = controller?.scheduledTime;
  let slot;
  try {
    slot = slotForEvent(scheduledTime, nowMs);
  } catch (error) {
    receipt(log, { scheduled_time: scheduledTime ?? null, outcome: "refused", reason: String(error.message) });
    return;
  }
  if (typeof env?.GITHUB_DISPATCH_TOKEN !== "string" || !env.GITHUB_DISPATCH_TOKEN.trim()) {
    receipt(log, { intended_hour_utc: slot.hour, correlation_id: slot.correlation, outcome: "credential-missing" });
    return;
  }
  const url = `${API}/actions/workflows/${WORKFLOW}/dispatches`;
  const headers = {
    Authorization: `Bearer ${env.GITHUB_DISPATCH_TOKEN}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "CryptoPulse-Hourly-Cron",
  };
  let result;
  try {
    result = await fetchImpl(url, {
      method: "POST",
      headers,
      signal: AbortSignal.timeout(10_000),
      body: JSON.stringify({
        ref: "main",
        inputs: { intended_hour_utc: slot.hour, dispatch_correlation_id: slot.correlation },
      }),
    });
  } catch {
    // A transport exception is ambiguous. Never send a second dispatch.
    receipt(log, { intended_hour_utc: slot.hour, correlation_id: slot.correlation, outcome: "dispatch-ambiguous" });
    return;
  }
  if (result.status !== 204) {
    receipt(log, {
      intended_hour_utc: slot.hour, correlation_id: slot.correlation,
      outcome: "dispatch-not-confirmed", http_status: result.status,
    });
    return;
  }

  receipt(log, {
    intended_hour_utc: slot.hour, correlation_id: slot.correlation,
    outcome: "dispatch-accepted-run-pending", run_id: null, run_attempt: null,
  });

  // The dispatch API returns no run ID. One bounded lookup is advisory only:
  // a missing/late run must be reconciled using the workflow's named run and receipt artifact.
  let run = null;
  try {
    const runs = await fetchImpl(
      `${API}/actions/workflows/${WORKFLOW}/runs?event=workflow_dispatch&per_page=100`,
      { method: "GET", headers, signal: AbortSignal.timeout(10_000) },
    );
    if (runs.ok) {
      const payload = await runs.json();
      const matches = (Array.isArray(payload.workflow_runs) ? payload.workflow_runs : [])
        .filter(item => item.display_title === TITLE_PREFIX + slot.correlation
          && item.head_branch === "main"
          && item.event === "workflow_dispatch"
          && Number.isSafeInteger(item.id) && item.id > 0
          && Number.isSafeInteger(item.run_attempt) && item.run_attempt > 0
          // Do not accidentally correlate a previous dispatch of the same UTC hour.
          && Number.isFinite(Date.parse(item.created_at))
          && Date.parse(item.created_at) >= nowMs - 3_000);
      if (matches.length === 1) {
        run = { id: matches[0].id, attempt: matches[0].run_attempt };
      }
    }
  } catch {
    // Lookup errors must not cause redispatch after HTTP 204.
  }
  if (run) {
    receipt(log, {
      intended_hour_utc: slot.hour, correlation_id: slot.correlation,
      outcome: "dispatch-accepted-run-observed",
      run_id: run.id, run_attempt: run.attempt,
    });
  }
}

export default {
  async scheduled(controller, env, _ctx) {
    await dispatchSlot(controller, env);
  },
};
