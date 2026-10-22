# INC-08: Payments slow, logs full of warnings

**Verdict:** root cause identified

Payments-api latency spiked due to downstream database bottlenecks caused by rolling out the unoptimized ledger.reconciliation_v2 feature flag on ledger-service.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 19 · LLM calls: 7 · tokens: 115188 · latency: 48.19s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Feature flag rollout of ledger.reconciliation_v2 introduced unoptimized queries saturating ledger-db CPU | ledger-db | feature_flag | 0.90 | `chg-9802` Feature flag rollout increased to 100% just before latency and CPU spikes.<br>`log-02040` ledger-service logged feature flag active at 100%.<br>`metric:ledger-db:cpu_pct` ledger-db CPU jumped to 94.84% right after the flag rollout.<br>`metric:ledger-db:latency_p99_ms` ledger-db p99 latency spiked simultaneously with CPU.<br>`metric:payments-api:latency_p99_ms` payments-api p99 latency increased as a consequence of synchronous dependency on ledger-service/ledger-db. | `log-00001` TLS deprecation warnings existed before the incident and do not correlate with the sudden onset. |
| 2 | Upstream upi-gateway degradation | upi-gateway | dependency_failure | 0.05 | - | `metric:upi-gateway:latency_p99_ms` upi-gateway latency remained completely stable throughout the incident window. |

## Facts (evidence-backed)

- payments-api p99 latency anomaly started at 2026-10-11T13:20:00+00:00 and peaked at 3521.46ms. (`metric:payments-api:latency_p99_ms`)
- Feature flag ledger.reconciliation_v2 was rolled out from 10% to 100% at 2026-10-11T13:18:00+00:00. (`chg-9802`, `log-02040`)
- ledger-db CPU usage spiked to 94.84% at 2026-10-11T13:34:00+00:00, with latency anomaly starting at 13:19:00+00:00. (`metric:ledger-db:cpu_pct`, `metric:ledger-db:latency_p99_ms`)
- TLS deprecation warnings in payments-api logs occurred continuously from 12:00:00+00:00 onwards. (`log-00001`)

## Assumptions (not proven)

- The ledger.reconciliation_v2 feature flag introduced new database queries or logic that lack proper indexing on ledger-db.

## Evidence gaps

- Detailed slow query text and execution plans from ledger-db were not directly available.

## Timeline

- 12:00 Telemetry window opens and TLS deprecation warnings begin logging in payments-api. (`log-00001`)
- 13:18 Feature flag ledger.reconciliation_v2 rollout increased from 10% to 100%. (`chg-9802`)
- 13:18 ledger-service logs feature flag active at 100%. (`log-02040`)
- 13:19 ledger-db latency anomaly begins and CPU starts spiking. (`metric:ledger-db:latency_p99_ms`)
- 13:20 payments-api latency anomaly onset. (`metric:payments-api:latency_p99_ms`)

## Recommended actions

- **immediate**: Roll back feature flag ledger.reconciliation_v2 to 10% or OFF.. Directly mitigates the database CPU saturation caused by the new reconciliation code path. (`chg-9802`, `metric:ledger-db:cpu_pct`)
- **short_term**: Audit and optimize queries executed by ledger.reconciliation_v2.. Ensures future rollouts do not cause resource exhaustion on ledger-db. (`metric:ledger-db:cpu_pct`)
