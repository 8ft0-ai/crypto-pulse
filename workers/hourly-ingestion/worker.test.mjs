import test from "node:test";
import assert from "node:assert/strict";
import { dispatchSlot, slotForEvent } from "./worker.mjs";

const HOUR_START = Date.UTC(2026, 10, 4, 1);
const AT_07 = HOUR_START + 7 * 60_000;
const AT_10 = HOUR_START + 10 * 60_000;
const TOKEN = "never-print-this-token";
const event = { scheduledTime: AT_07 };

function capture() {
  const lines = [];
  return { lines, log: { log: line => lines.push(JSON.parse(line)) } };
}

test("Cloudflare UTC :07 minute controls slot despite seconds of delivery jitter", () => {
  assert.deepEqual(slotForEvent(AT_07, AT_10), {
    hour: "2026-11-04T01:00:00Z",
    correlation: "cp-2026110401",
  });
  assert.deepEqual(slotForEvent(AT_07 + 21_332, AT_10), slotForEvent(AT_07, AT_10));
  assert.deepEqual(slotForEvent(AT_07 + 59_999, AT_10), slotForEvent(AT_07, AT_10));
  assert.throws(() => slotForEvent(AT_07 + 60_000, AT_10), /UTC :07/);
  assert.throws(() => slotForEvent(AT_07, HOUR_START + 30 * 60_000), /deadline/);
  assert.throws(() => slotForEvent(AT_07, AT_07 - 1), /early/);
  assert.throws(() => slotForEvent(Number.NaN, AT_10), /invalid/);
});

test("worker has no acceptance path for expired slots or missing secrets", async () => {
  const out = capture();
  let calls = 0;
  const fetchImpl = async () => { calls += 1; throw new Error("unexpected network"); };
  await dispatchSlot(event, { GITHUB_DISPATCH_TOKEN: TOKEN }, {
    nowMs: HOUR_START + 31 * 60_000, fetchImpl, log: out.log,
  });
  await dispatchSlot(event, {}, { nowMs: AT_10, fetchImpl, log: out.log });
  assert.equal(calls, 0);
  assert.equal(out.lines[0].outcome, "refused");
  assert.equal(out.lines[1].outcome, "credential-missing");
});

test("only one exact main workflow dispatch, followed by bounded correlation lookup", async () => {
  const out = capture();
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url, options });
    if (calls.length === 1) return { status: 204 };
    return {
      ok: true,
      json: async () => ({
        workflow_runs: [{
          display_title: "Crypto source ingestion cp-2026110401",
          head_branch: "main", event: "workflow_dispatch",
          created_at: "2026-11-04T01:10:01Z", id: 123, run_attempt: 1,
        }],
      }),
    };
  };
  await dispatchSlot(event, { GITHUB_DISPATCH_TOKEN: TOKEN }, { nowMs: AT_10, fetchImpl, log: out.log });
  assert.equal(calls.length, 2);
  assert.match(calls[0].url, /\/ingest-crypto-sources.yml\/dispatches$/);
  assert.equal(calls[0].options.method, "POST");
  assert.deepEqual(JSON.parse(calls[0].options.body), {
    ref: "main",
    inputs: { intended_hour_utc: "2026-11-04T01:00:00Z", dispatch_correlation_id: "cp-2026110401" },
  });
  assert.match(calls[1].url, /event=workflow_dispatch&per_page=100/);
  assert.equal(out.lines[0].outcome, "dispatch-accepted-run-pending");
  assert.equal(out.lines[1].outcome, "dispatch-accepted-run-observed");
  assert.equal(out.lines[1].run_id, 123);
  assert.ok(!JSON.stringify(out.lines).includes(TOKEN), "secret must never appear in receipts");
});

test("204 without correlated run stays pending and must not redispatch", async () => {
  const out = capture();
  let calls = 0;
  await dispatchSlot(event, { GITHUB_DISPATCH_TOKEN: TOKEN }, {
    nowMs: AT_10, log: out.log,
    fetchImpl: async () => {
      calls += 1;
      return calls === 1
        ? { status: 204 }
        : { ok: true, json: async () => ({ workflow_runs: [] }) };
    },
  });
  assert.equal(calls, 2);
  assert.equal(out.lines[0].outcome, "dispatch-accepted-run-pending");
  assert.equal(out.lines[0].run_id, null);
});

test("timeout, HTTP failure and duplicate correlation are never retried", async () => {
  const out = capture();
  let calls = 0;
  await dispatchSlot(event, { GITHUB_DISPATCH_TOKEN: TOKEN }, {
    nowMs: AT_10, log: out.log,
    fetchImpl: async () => { calls += 1; throw new Error("token=" + TOKEN); },
  });
  await dispatchSlot(event, { GITHUB_DISPATCH_TOKEN: TOKEN }, {
    nowMs: AT_10, log: out.log,
    fetchImpl: async () => { calls += 1; return { status: 429 }; },
  });
  assert.equal(calls, 2);
  assert.equal(out.lines[0].outcome, "dispatch-ambiguous");
  assert.equal(out.lines[1].outcome, "dispatch-not-confirmed");
  assert.equal(out.lines[1].http_status, 429);
  assert.ok(!JSON.stringify(out.lines).includes(TOKEN));
});

test("ambiguous multiple run matches never claim run identity", async () => {
  const out = capture();
  let calls = 0;
  const match = { display_title: "Crypto source ingestion cp-2026110401", head_branch: "main", event: "workflow_dispatch", created_at: "2026-11-04T01:10:01Z", id: 1, run_attempt: 1 };
  await dispatchSlot(event, { GITHUB_DISPATCH_TOKEN: TOKEN }, {
    nowMs: AT_10, log: out.log,
    fetchImpl: async () => (++calls === 1)
      ? { status: 204 }
      : { ok: true, json: async () => ({ workflow_runs: [match, { ...match, id: 2 }] }) },
  });
  assert.equal(out.lines[0].outcome, "dispatch-accepted-run-pending");
  assert.equal(out.lines[0].run_id, null);
});
