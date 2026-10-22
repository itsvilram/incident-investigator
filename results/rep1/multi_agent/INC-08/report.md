# INC-08: Payments slow, logs full of warnings

**Verdict:** root cause identified

Payments-api p99 latency spiked starting at 2026-10-11T13:20:00+00:00 due to a synchronous dependency on ledger-service, which experienced immediate p99 latency degradation starting at 13:19:00+00:00. This upstream latency spike was directly triggered by the rollout of the ledger.reconciliation_v2 feature flag from 10% to 100% at 13:18:00+00:00.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 2 · tool calls: 13 · LLM calls: 22 · tokens: 129979 · latency: 73.23s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Ledger Service Feature Flag Rollout Contention | ledger-service | feature_flag | 0.95 | `chg-9802` Feature flag change occurred at 13:18 UTC, precisely 2 minutes before the payments-api latency spike onset.<br>`metric:ledger-service:latency_p99_ms` ledger-service p99 latency spiked starting at 13:19:00+00:00, immediately following the rollout.<br>`metric:payments-api:latency_p99_ms` payments-api p99 latency spiked sharply upward starting exactly at 13:20:00+00:00.<br>`dep:payments-api->ledger-service` Establishes the synchronous dependency path from payments-api to ledger-service. | `metric:payments-api:error_rate_pct` Error rate increased slightly later at 13:25 UTC rather than simultaneously with the 13:20 latency spike. |
| 2 | UPI Gateway Upstream Degradation | upi-gateway | third_party_outage | 0.05 | `dep:payments-api->upi-gateway` Establishes payments-api dependency on upi-gateway.<br>`log-01380` Shows warnings and retries calling upi-gateway prior to the incident.<br>`log-01553` Shows slow request intent logs on payments-api shortly before the onset. | `log-01380` The observed retries and slow requests occurred at 12:53 and 13:00, which are significantly earlier than the 13:20 onset.<br>`metric:payments-api:latency_p99_ms` The latency anomaly aligns precisely with ledger-service feature rollout rather than any new upi-gateway signal at 13:20. |

## Facts (evidence-backed)

- payments-api p99 latency spiked starting at 2026-10-11T13:20:00+00:00, jumping from a baseline of ~380ms to 3239.85ms. (`metric:payments-api:latency_p99_ms`)
- payments-api error rate increased starting at 2026-10-11T13:25:00+00:00, going from ~0.3% to ~1.2%. (`metric:payments-api:error_rate_pct`)
- TLS deprecation warnings for 'legacy-psp' have been logged continuously since 12:00:00+00:00, predating the latency spike. (`log-00001`, `log-03346`)
- payments-api directly depends on ledger-service, upi-gateway, fraud-service, redis-cache, and event-bus, and is called by mobile-bff. (`dep:mobile-bff->payments-api`, `dep:payments-api->ledger-service`, `dep:payments-api->upi-gateway`, `dep:payments-api->fraud-service`, `dep:payments-api->redis-cache`, `dep:payments-api->event-bus`)
- A feature flag rollout chg-9802 for ledger.reconciliation_v2 from 10% to 100% occurred on ledger-service at 2026-10-11T13:18:00+00:00. (`chg-9802`)
- Ledger-service latency_p99_ms experienced an anomaly starting at 2026-10-11T13:19:00+00:00, peaking at 3364.94 ms at 13:23:00+00:00. (`metric:ledger-service:latency_p99_ms`)

## Assumptions (not proven)

- ledger-service experienced internal computational or query overhead under 100% reconciliation_v2 traffic that propagated back to payments-api.

## Evidence gaps

- none

## Timeline

- 12:00 TLS deprecation warnings for legacy-psp start logging continuously on payments-api (`log-00001`)
- 13:18 Feature flag ledger.reconciliation_v2 rolled out from 10% to 100% on ledger-service (chg-9802) (`chg-9802`)
- 13:19 ledger-service p99 latency anomaly begins (`metric:ledger-service:latency_p99_ms`)
- 13:20 payments-api p99 latency anomaly begins (incident onset) (`metric:payments-api:latency_p99_ms`)
- 13:25 payments-api error rate begins to increase (`metric:payments-api:error_rate_pct`)

## Recommended actions

- **immediate**: Roll back the ledger.reconciliation_v2 feature flag on ledger-service to the previous 10% state.. Directly mitigates the latency introduced by the 100% reconciliation rollout. (`chg-9802`, `metric:ledger-service:latency_p99_ms`, `metric:payments-api:latency_p99_ms`)
- **short_term**: Investigate ledger-service reconciliation query performance and resource usage under full load.. Identifies why the 100% feature flag rollout caused p99 latency to spike on ledger-service. (`chg-9802`, `metric:ledger-service:latency_p99_ms`)
- **long_term**: Implement circuit breakers or asynchronous handling between payments-api and synchronous dependencies like ledger-service to prevent cascading latency spikes.. Protects payments-api from downstream performance degradation. (`dep:payments-api->ledger-service`, `metric:payments-api:latency_p99_ms`)
