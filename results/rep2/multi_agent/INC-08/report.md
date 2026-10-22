# INC-08: Payments slow, logs full of warnings

**Verdict:** root cause identified

Payments were slow due to a latency spike in payments-api caused by its synchronous dependency, ledger-service. The ledger-service latency spike was triggered by the full rollout of the ledger.reconciliation_v2 feature flag from 10% to 100% at 13:18 UTC, immediately preceding the onset of the latency anomaly at 13:19 UTC in ledger-service and 13:20 UTC in payments-api.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 1 · tool calls: 13 · LLM calls: 10 · tokens: 61357 · latency: 24.15s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Ledger reconciliation feature flag rollout causes latency spike | ledger-service | feature_flag | 0.95 | `chg-9802` Feature flag change at 13:18 UTC immediately precedes the ledger-service latency spike at 13:19 UTC.<br>`metric:ledger-service:latency_p99_ms` Shows ledger-service p99 latency spiking sharply upward starting at 13:19.<br>`metric:payments-api:latency_p99_ms` Shows payments-api p99 latency spiking starting at 13:20.<br>`dep:payments-api->ledger-service` Confirms synchronous dependency from payments-api to ledger-service. | `metric:ledger-service:cpu_pct` Ledger-service CPU percentage showed no notable anomaly during the incident window.<br>`metric:ledger-service:error_rate_pct` Ledger-service error rate remained stable without an anomaly during the window. |
| 2 | Ledger database degradation causes cascading latency | ledger-db | resource_exhaustion | 0.10 | `log-00587` Ledger-service logged warnings about retrying calls to ledger-db starting at 12:23 UTC.<br>`metric:ledger-service:latency_p99_ms` Confirms ledger-service latency spike starting at 13:19 UTC.<br>`metric:payments-api:latency_p99_ms` Confirms payments-api latency spike starting at 13:20 UTC. | `chg-9802` Feature flag change at 13:18 UTC provides a much tighter temporal correlation to the sharp onset at 13:19 than database warnings occurring hours prior. |

## Facts (evidence-backed)

- payments-api p99 latency increased from baseline ~382.67ms to 3239.85ms at 2026-10-11T13:20:00+00:00, peaking at 3521.46ms at 13:27. (`metric:payments-api:latency_p99_ms`)
- ledger-service p99 latency increased from baseline ~120.79ms to 3196.98ms starting at 2026-10-11T13:19:00+00:00, peaking at 3364.94ms at 13:23:00+00:00. (`metric:ledger-service:latency_p99_ms`)
- TLS deprecation warnings in payments-api logs occurred continuously from 12:00:00+00:00 onwards, preceding the latency spike by over an hour. (`log-00001`, `log-03366`)
- ledger-service had a feature flag rollout chg-9802 (ledger.reconciliation_v2 from 10% to 100%) at 2026-10-11T13:18:00+00:00, which precedes the reported latency symptom onset at ~13:20 UTC. (`chg-9802`)
- payments-api depends synchronously on ledger-service. (`dep:payments-api->ledger-service`)

## Assumptions (not proven)

- The new reconciliation logic under ledger.reconciliation_v2 causes thread waiting or I/O waits rather than high CPU usage.

## Evidence gaps

- none

## Timeline

- 13:18 Feature flag ledger.reconciliation_v2 rolled out from 10% to 100% on ledger-service. (`chg-9802`)
- 13:19 ledger-service p99 latency begins to spike. (`metric:ledger-service:latency_p99_ms`)
- 13:20 payments-api p99 latency begins to spike. (`metric:payments-api:latency_p99_ms`)

## Recommended actions

- **immediate**: Roll back the ledger.reconciliation_v2 feature flag on ledger-service to 10% or disable it completely.. Directly mitigates the root cause introduced by chg-9802. (`chg-9802`)
- **short_term**: Investigate the ledger.reconciliation_v2 codebase for blocking calls or inefficient execution patterns that cause high latency without increasing CPU usage.. Prevents future regressions when attempting to roll out the feature flag again. (`chg-9802`, `metric:ledger-service:latency_p99_ms`)
- **long_term**: Implement strict performance and timeout safeguards for synchronous inter-service calls.. Limits blast radius when upstream dependencies like ledger-service experience unexpected processing delays. (`dep:payments-api->ledger-service`)
