# INC-08: Payments slow, logs full of warnings

**Verdict:** root cause identified

payments-api experienced high p99 latency starting at 13:20 due to cascading latency from ledger-service and ledger-db, caused by the full rollout of the ledger.reconciliation_v2 feature flag at 13:18.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 15 · LLM calls: 6 · tokens: 81256 · latency: 15.83s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | ledger.reconciliation_v2 feature flag rollout overloaded ledger-db and ledger-service | ledger-service | feature_flag | 0.90 | `chg-9802` ledger.reconciliation_v2 rolled out from 10% to 100% at 13:18, right before latency spike<br>`metric:ledger-db:latency_p99_ms` ledger-db latency spiked at 13:19, reaching over 3.4s<br>`metric:ledger-db:cpu_pct` ledger-db CPU spiked to 94.84% starting at 13:19<br>`metric:payments-api:latency_p99_ms` payments-api p99 latency anomaly began at 13:20, jumping to ~3.3s | - |
| 2 | TLS deprecation warnings in payments-api caused performance degradation | payments-api | config_change | 0.05 | - | `log-00001` TLS deprecation warnings were present continuously since 12:00 when latency was normal<br>`metric:payments-api:latency_p99_ms` Latency anomaly started at 13:20, well after the constant presence of TLS warnings |

## Facts (evidence-backed)

- payments-api p99 latency anomaly started at 2026-10-11T13:20:00+00:00, jumping to over 3.3s. (`metric:payments-api:latency_p99_ms`)
- ledger.reconciliation_v2 rollout changed from 10% to 100% at 2026-10-11T13:18:00+00:00. (`chg-9802`)
- ledger-db CPU and p99 latency spiked upward starting at 2026-10-11T13:19:00+00:00. (`metric:ledger-db:cpu_pct`, `metric:ledger-db:latency_p99_ms`)
- payments-api makes synchronous dependency calls to ledger-service. (`dep:payments-api->ledger-service`)
- TLS deprecation warnings for legacy-psp occurred consistently throughout the investigation window. (`log-00001`, `log-03346`)

## Assumptions (not proven)

- The ledger.reconciliation_v2 feature flag introduced inefficient or resource-intensive queries that saturated ledger-db CPU.

## Evidence gaps

- Certain log shards experienced query timeouts during deep inspection of ledger-service logs.

## Timeline

- 12:00 Telemetry tracking begins; TLS warnings present in payments-api (`log-00001`)
- 13:18 ledger.reconciliation_v2 rolled out to 100% (`chg-9802`)
- 13:19 ledger-db CPU and p99 latency spike significantly (`metric:ledger-db:cpu_pct`)
- 13:20 payments-api p99 latency anomaly begins (`metric:payments-api:latency_p99_ms`)
- 13:25 payments-api error rate begins to rise (`metric:payments-api:error_rate_pct`)
- 13:45 Incident INC-08 reported by on-call

## Recommended actions

- **immediate**: Toggle the ledger.reconciliation_v2 feature flag back to 10% or OFF. Directly mitigates the ledger-db CPU saturation and restores p99 latency across ledger and payments services. (`chg-9802`, `metric:ledger-db:cpu_pct`)
- **short_term**: Optimize reconciliation_v2 database queries and indexing on ledger-db. Prevents database CPU exhaustion when reconciliation_v2 is eventually re-enabled. (`metric:ledger-db:cpu_pct`)
- **long_term**: Clean up legacy TLS client config warnings to reduce noise in logs. Eliminates warning log spam that misleads responders during incident triage. (`log-00001`)
