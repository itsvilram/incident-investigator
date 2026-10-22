# H06: Payments slower than usual

**Verdict:** root cause identified

payments-api experienced a ~3x increase in p99 latency starting at 13:20 on 2026-10-15 due to downstream latency propagation from ledger-service and ledger-db. The root cause was configuration change chg-8940 at 13:18, which increased the ledger query batch size from 100 to 1000, causing larger database operations, CPU spikes, and slower query responses starting at 13:19.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 2 · tool calls: 13 · LLM calls: 19 · tokens: 94736 · latency: 76.11s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Ledger query batch size configuration change caused latency | ledger-service | config_change | 0.95 | `chg-8940` Configuration change modifying query batch size directly precedes the database and service latency increase.<br>`metric:ledger-service:latency_p99_ms` ledger-service p99 latency increased immediately following the configuration change.<br>`metric:ledger-db:latency_p99_ms` ledger-db p99 latency increased at the same time.<br>`log-00501` ledger-service logged slow ledger queries starting at 13:19.<br>`log-00499` ledger-db logged slow statements starting at 13:19.<br>`metric:payments-api:latency_p99_ms` payments-api latency spiked right after downstream ledger latency increased.<br>`dep:payments-api->ledger-service` Synchronous dependency links payments-api performance directly to ledger-service. | `metric:payments-api:error_rate_pct` Error rate and request rate remained stable, indicating successful completion rather than failure or timeouts. |
| 2 | Third-party UPI gateway or partner bank latency | upi-gateway | third_party_outage | 0.08 | `dep:payments-api->upi-gateway` payments-api depends synchronously on upi-gateway.<br>`metric:payments-api:latency_p99_ms` p99 latency increase matches external gateway slowness symptoms. | `chg-8940` An internal config change occurred precisely before onset, making internal config regression much more probable.<br>`metric:ledger-service:latency_p99_ms` ledger-service also degraded at the exact same time, aligning with the internal config change. |

## Facts (evidence-backed)

- payments-api p99 latency rose from a baseline of ~370-395 ms to 1252.38 ms at 2026-10-15T13:20:00+00:00, peaking at 1485.07 ms. (`metric:payments-api:latency_p99_ms`)
- payments-api request rate and error rate remained stable with no significant anomalies during the incident window. (`metric:payments-api:rps`, `metric:payments-api:error_rate_pct`)
- payments-api has synchronous dependencies on ledger-service, upi-gateway, fraud-service, and redis-cache, and an asynchronous dependency on event-bus. (`dep:payments-api->ledger-service`, `dep:payments-api->upi-gateway`, `dep:payments-api->fraud-service`, `dep:payments-api->redis-cache`, `dep:payments-api->event-bus`)
- A configuration change chg-8940 occurred on ledger-service at 2026-10-15T13:18:00+00:00 modifying the query batch size from 100 to 1000. (`chg-8940`)
- ledger-service p99 latency increased starting at 2026-10-15T13:19:00+00:00, with baseline 121.05 ms and peak 975.46 ms. (`metric:ledger-service:latency_p99_ms`)
- ledger-service began logging slow ledger queries starting at 2026-10-15T13:19:22+00:00. (`log-00501`)
- ledger-db p99 latency increased starting at 2026-10-15T13:19:00+00:00, moving from a baseline of 14.77 ms to a peak of 138.58 ms. (`metric:ledger-db:latency_p99_ms`)
- ledger-db CPU usage increased starting at 2026-10-15T13:19:00+00:00, peaking at 52.86%. (`metric:ledger-db:cpu_pct`)
- ledger-db logged slow SQL statements starting at 2026-10-15T13:19:06+00:00. (`log-00499`)

## Assumptions (not proven)

- Synchronous calls from payments-api wait for ledger-service transactions to complete, causing request duration to track the increased database and ledger-service latency.

## Evidence gaps

- none

## Timeline

- 13:18 Configuration change chg-8940 increases ledger query batch size from 100 to 1000 on ledger-service. (`chg-8940`)
- 13:19 ledger-service and ledger-db p99 latency metrics begin to increase; ledger-db CPU usage rises. (`metric:ledger-service:latency_p99_ms`)
- 13:19 ledger-db logs slow SQL statements. (`log-00499`)
- 13:19 ledger-service logs slow ledger queries. (`log-00501`)
- 13:20 payments-api p99 latency increases significantly (onset of reported symptoms). (`metric:payments-api:latency_p99_ms`)

## Recommended actions

- **immediate**: Roll back configuration change chg-8940 on ledger-service to revert the query batch size from 1000 back to 100.. Reverting the configuration change directly eliminates the root cause of the increased database load and latency propagation. (`chg-8940`)
- **short_term**: Monitor ledger-service, ledger-db, and payments-api p99 latency metrics to confirm recovery after rollback.. Ensures that latency returns to established baseline levels following remediation. (`metric:payments-api:latency_p99_ms`, `metric:ledger-service:latency_p99_ms`, `metric:ledger-db:latency_p99_ms`)
- **long_term**: Implement pre-deployment query performance and batch size impact testing for database-interacting configurations.. Prevents similar query size configuration regressions from impacting downstream synchronous clients in the future. (`chg-8940`, `log-00501`)
