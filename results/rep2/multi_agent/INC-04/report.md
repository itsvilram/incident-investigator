# INC-04: DB connection errors in payments

**Verdict:** root cause identified

An incident occurred resulting in intermittent database connection errors in payment confirmations due to a configuration change that reduced the maximum database connection pool size on ledger-service from 50 to 5. This triggered connection pool exhaustion, elevated latency, and increased error rates across ledger-service and payments-api starting at 2026-10-06T13:14:00+00:00.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 1 · tool calls: 15 · LLM calls: 13 · tokens: 77302 · latency: 38.01s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Configuration Change Reducing Database Connection Pool Size Exhausts Ledger Service Connections | ledger-service | config_change | 0.95 | `chg-8919` Config change on ledger-service at 13:12 reduced db.pool.max_size from 50 to 5, immediately preceding the onset.<br>`metric:ledger-service:latency_p99_ms` Ledger-service latency anomaly began at 13:14, right after the config change.<br>`metric:ledger-service:error_rate_pct` Ledger-service error rate spiked starting at 13:15.<br>`metric:payments-api:error_rate_pct` Payments-api error rate spiked starting at 13:15 as calls to ledger-service failed.<br>`log-00466` Ledger-service logs show HikariPool connection timeouts indicating pool exhaustion (total=5, active=5) starting at 13:15.<br>`log-00465` Payments-api logs show errors calling ledger-service due to inability to acquire connections starting at 13:15. | - |
| 2 | Upstream Traffic Surge Overwhelming Ledger Service | payments-api | traffic_spike | 0.05 | `metric:payments-api:error_rate_pct` Payments-api error rates spiked during the incident. | `metric:payments-api:rps` Payments-api RPS shows no abnormal surge or traffic spike during the window.<br>`chg-8919` The config change at 13:12 provides a direct and sufficient explanation for connection exhaustion without needing a traffic spike. |

## Facts (evidence-backed)

- Payments-api error rate spiked up starting at 2026-10-06T13:15:00+00:00, reaching a peak of 8.26% at 13:47. (`metric:payments-api:error_rate_pct`)
- Ledger-service error rate spiked starting at 2026-10-06T13:15:00+00:00, reaching a peak of 10.25% at 13:45. (`metric:ledger-service:error_rate_pct`)
- Ledger-service p99 latency anomaly began at 2026-10-06T13:14:00+00:00, reaching a peak of 7278.17ms. (`metric:ledger-service:latency_p99_ms`)
- Ledger-service logs show HikariPool connection timeouts indicating pool exhaustion (total=5, active=5, idle=0, waiting) starting at 2026-10-06T13:15:05+00:00. (`log-00466`)
- Payments-api logs show errors calling ledger-service due to inability to acquire connections starting at 2026-10-06T13:15:02+00:00. (`log-00465`)
- Ledger-db active connections and cpu percentage dropped significantly starting at 2026-10-06T13:13:00+00:00. (`metric:ledger-db:connections_active`, `metric:ledger-db:cpu_pct`)
- Ledger-service underwent a config change on 2026-10-06 at 13:12 normalizing db.pool.max_size from 50 to 5. (`chg-8919`)

## Assumptions (not proven)

- The configuration change applied successfully across all running instances of ledger-service instantly.

## Evidence gaps

- none

## Timeline

- 13:12 Config-sync normalizes db.pool.max_size from 50 to 5 on ledger-service (`chg-8919`)
- 13:13 Ledger-db active connections and cpu percentage drop significantly (`metric:ledger-db:connections_active`)
- 13:14 Ledger-service p99 latency anomaly begins (`metric:ledger-service:latency_p99_ms`)
- 13:15 Ledger-service and payments-api error rates spike (`metric:ledger-service:error_rate_pct`)
- 13:15 Payments-api logs errors calling ledger-service due to inability to acquire connections (`log-00465`)
- 13:15 Ledger-service logs HikariPool connection timeouts indicating pool exhaustion (`log-00466`)

## Recommended actions

- **immediate**: Revert the database connection pool configuration change on ledger-service back to 50. Configuration change chg-8919 reduced max pool size to 5, which directly caused database connection pool exhaustion and subsequent errors across dependent services. (`chg-8919`, `log-00466`, `metric:ledger-service:error_rate_pct`)
- **short_term**: Implement validation checks in the config-sync tool to prevent excessively low database connection pool sizes relative to service concurrency and traffic load. Prevents automated or manual normalization changes from blindly overriding required service resource bounds. (`chg-8919`)
- **long_term**: Establish comprehensive automated alerting for sudden drops in database active connections and abnormal database pool wait times. Ensures early detection of connection pool constraints before customer-facing request failures cascade. (`metric:ledger-db:connections_active`, `log-00466`)
