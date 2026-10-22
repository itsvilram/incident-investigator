# H06: Payments slower than usual

**Verdict:** root cause identified

Payments-api p99 latency spiked 3x due to a ledger-service configuration change (chg-8940) increasing query batch sizes, which heavily increased CPU utilization and latency on ledger-db.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 13 · LLM calls: 6 · tokens: 91559 · latency: 17.02s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Ledger query batch size configuration change increased DB load | ledger-service | config_change | 0.90 | `chg-8940` Config change increased query batch size from 100 to 1000 at 13:18, immediately preceding the database and latency spikes.<br>`metric:ledger-db:cpu_pct` Ledger-db CPU spiked from ~31% to ~48% at 13:19, right after the config change.<br>`metric:ledger-service:latency_p99_ms` Ledger-service latency spiked starting at 13:19.<br>`metric:payments-api:latency_p99_ms` Payments-api p99 latency increased 3x starting at 13:20.<br>`log-00501` Ledger-service logged numerous slow ledger queries starting at 13:19:22. | - |
| 2 | Network congestion in cluster datapath | payments-api | network_dns | 0.10 | `metric:payments-api:latency_p99_ms` General latency increase across dependent services. | `chg-8940` The timing perfectly correlates with a ledger-service config change and database resource contention rather than generalized network failure. |

## Facts (evidence-backed)

- Payments-api p99 latency rose from baseline (~381ms) to a peak of 1,485ms, with the anomaly starting at 2026-10-15T13:20:00+00:00. (`metric:payments-api:latency_p99_ms`)
- Payments-api RPS, error rate, CPU, memory, and pod restarts remained normal without anomalies. (`metric:payments-api:rps`, `metric:payments-api:error_rate_pct`, `metric:payments-api:cpu_pct`, `metric:payments-api:mem_pct`, `metric:payments-api:pod_restarts`)
- A config change (chg-8940) modified query.batch_size from 100 to 1000 in ledger-service at 2026-10-15T13:18:00+00:00. (`chg-8940`)
- Ledger-service p99 latency increased starting at 2026-10-15T13:19:00+00:00. (`metric:ledger-service:latency_p99_ms`)
- Ledger-db CPU utilization spiked from ~31% to ~48% starting at 2026-10-15T13:19:00+00:00. (`metric:ledger-db:cpu_pct`)
- Ledger-db p99 latency spiked starting at 2026-10-15T13:19:00+00:00. (`metric:ledger-db:latency_p99_ms`)
- Ledger-service logged 155 occurrences of slow ledger queries beginning at 2026-10-15T13:19:22+00:00. (`log-00501`)
- Payments-api depends synchronously on ledger-service, and ledger-service depends synchronously on ledger-db. (`dep:payments-api->ledger-service`, `dep:ledger-service->ledger-db`)

## Assumptions (not proven)

- Increasing query.batch_size from 100 to 1000 caused database queries to fetch significantly larger result sets or perform heavier table scans in ledger-db, directly driving up database CPU usage and query execution time.

## Evidence gaps

- none

## Timeline

- 13:18 Config change chg-8940 applied: ledger-service query batch size increased from 100 to 1000. (`chg-8940`)
- 13:19 Ledger-db CPU utilization and p99 latency spike begin. (`metric:ledger-db:cpu_pct`)
- 13:19 First slow ledger query warning logged by ledger-service. (`log-00501`)
- 13:20 Payments-api p99 latency anomaly begins. (`metric:payments-api:latency_p99_ms`)
- 14:00 Incident reported by payments on-call (Arjun).

## Recommended actions

- **immediate**: Revert configuration change chg-8940 on ledger-service (query.batch_size back to 100).. Will immediately relieve pressure on ledger-db and restore normal latencies. (`chg-8940`, `metric:ledger-db:cpu_pct`)
- **short_term**: Review database query execution plans and index coverage for queries affected by large batch sizes.. Ensures optimal database performance if larger batch sizes are required in the future. (`hist-2026-0811`)
- **long_term**: Implement automated canary deployments or staged rollouts for configuration changes.. Catches latency anomalies and regressions before 100% of traffic is impacted. (`chg-8940`)
