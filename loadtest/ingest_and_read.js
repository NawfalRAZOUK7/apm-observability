// loadtest/ingest_and_read.js
// ---------------------------------------------------------------------------
// k6 load test for the APM Observability API.
//
// It drives the platform end-to-end so the observability stack lights up:
//   - POST /api/requests/ingest/  (batches of realistic events)
//   - GET  /api/requests/         (paginated reads)
//   - GET  /api/requests/kpis/    (analytics read; TimescaleDB stacks only)
//
// A configurable share of ingested events carry a 5xx status_code, so the
// application error rate rises and the `HighErrorRate` Prometheus alert can
// move to PENDING/FIRING while the test runs.
//
// Usage:
//   k6 run loadtest/ingest_and_read.js
//   BASE_URL=https://localhost:8443 BATCH=50 ERROR_RATIO=0.1 k6 run --insecure-skip-tls-verify loadtest/ingest_and_read.js
// ---------------------------------------------------------------------------

import http from "k6/http";
import { check, sleep } from "k6";
import { Trend, Counter } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "https://localhost:8443";
const BATCH = parseInt(__ENV.BATCH || "50", 10); // events per ingest call
const ERROR_RATIO = parseFloat(__ENV.ERROR_RATIO || "0.1"); // share of 5xx events

// Custom metrics (visible in the k6 end-of-test summary).
const ingestLatency = new Trend("apm_ingest_latency", true);
const ingestedEvents = new Counter("apm_events_ingested");

const SERVICES = ["billing", "auth", "search", "checkout", "gateway"];
const ENDPOINTS = ["/api/v1/invoices", "/api/v1/login", "/api/v1/query", "/api/v1/pay"];
const METHODS = ["GET", "POST", "PUT", "DELETE"];

export const options = {
  scenarios: {
    ramp: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s", target: 10 }, // warm up
        { duration: "1m", target: 40 }, // ramp to load
        { duration: "1m", target: 40 }, // hold (watch dashboards/alerts)
        { duration: "30s", target: 0 }, // ramp down
      ],
      gracefulRampDown: "10s",
    },
  },
  // Performance gates: the test fails (non-zero exit) if these are breached.
  thresholds: {
    http_req_failed: ["rate<0.05"], // <5% transport-level failures
    http_req_duration: ["p(95)<800"], // 95th percentile under 800ms
    checks: ["rate>0.95"], // >95% of assertions pass
  },
};

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function makeEvent(i) {
  // ~ERROR_RATIO of events are 5xx to drive the application error rate up.
  const isError = Math.random() < ERROR_RATIO;
  const status = isError ? pick([500, 502, 503]) : pick([200, 201, 200, 200, 404]);
  return {
    time: new Date().toISOString(),
    service: pick(SERVICES),
    endpoint: pick(ENDPOINTS),
    method: pick(METHODS),
    status_code: status,
    latency_ms: Math.floor(Math.random() * 900) + 5,
    trace_id: `k6-${__VU}-${__ITER}-${i}`,
    user_ref: `user-${Math.floor(Math.random() * 1000)}`,
    tags: { env: "loadtest", vu: __VU },
  };
}

export default function () {
  // 1) Ingest a batch of events.
  const events = Array.from({ length: BATCH }, (_, i) => makeEvent(i));
  const res = http.post(`${BASE_URL}/api/requests/ingest/`, JSON.stringify(events), {
    headers: { "Content-Type": "application/json" },
    tags: { name: "ingest" },
  });
  ingestLatency.add(res.timings.duration);
  const ingestOk = check(res, {
    "ingest status is 200": (r) => r.status === 200,
    "ingest inserted events": (r) => {
      try {
        return (r.json("inserted") || 0) > 0;
      } catch (e) {
        return false;
      }
    },
  });
  if (ingestOk) ingestedEvents.add(BATCH);

  // 2) Read back the most recent requests (paginated list).
  const list = http.get(`${BASE_URL}/api/requests/?ordering=-time`, {
    tags: { name: "list" },
  });
  check(list, { "list status is 200": (r) => r.status === 200 });

  // 3) Analytics KPIs (200 on TimescaleDB stacks, 501 on SQLite dev).
  const kpis = http.get(`${BASE_URL}/api/requests/kpis/`, { tags: { name: "kpis" } });
  check(kpis, { "kpis reachable (200 or 501)": (r) => r.status === 200 || r.status === 501 });

  sleep(Math.random() * 0.5);
}
