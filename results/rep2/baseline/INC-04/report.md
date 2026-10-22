# INC-04: DB connection errors in payments

**Verdict:** root cause identified

Database connection errors in payments-api were caused by a configuration sync job that inadvertently reduced the ledger-service connection pool size from 50 to 5, resulting in immediate pool exhaustion and connection timeouts starting at 13:15.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 10 · LLM calls: 4 · tokens: 40108 · latency: 14.41s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Database Connection Pool Exhaustion in Ledger Service due to Config Normalization | ledger-service | config_change | 0.95 | `chg-8919` Config change at 13:12 reduced db.pool.max_size from 50 to 5 for ledger-service.<br>`metric:ledger-service:error_rate_pct` Error rate anomaly started at 13:15 for ledger-service.<br>`metric:payments-api:error_rate_pct` Error rate anomaly started at 13:15 for payments-api due to downstream dependency failure.<br>`log-00466` Ledger service logs showed HikariPool timeout with 5 active and 0 idle connections starting at 13:15.<br>`log-00465` Payments API logs showed ledger-service POST /entries failing with 503 could not acquire connection starting at 13:15. | - |
| 2 | Traffic Surge Overloading Ledger Service | ledger-service | traffic_spike | 0.05 | - | `metric:ledger-service:rps` Request rate remained stable around ~280-310 req/s with no traffic surge during onset.<br>`metric:payments-api:rps` Request rate remained stable during onset. |

## Facts (evidence-backed)

- ledger-service depends synchronously on ledger-db. (`dep:ledger-service->ledger-db`)
- payments-api depends synchronously on ledger-service. (`dep:payments-api->ledger-service`)
- A config change chg-8919 modified ledger-service db.pool.max_size from 50 to 5 at 2026-10-06T13:12:00+00:00. (`chg-8919`)
- Error rates began rising for ledger-service and payments-api at 13:15. (`metric:ledger-service:error_rate_pct`, `metric:payments-api:error_rate_pct`)
- Ledger service logged HikariPool connection timeout errors indicating pool size 5 with 5 active connections. (`log-00466`)
- Payments API logged downstream connection errors calling ledger-service. (`log-00465`)

## Assumptions (not proven)

- The automated config sync script applied an incorrect normalization target of 5 instead of preserving higher sizing for ledger-service.

## Evidence gaps

- none

## Timeline

- 13:12 Config change chg-8919 executed on ledger-service setting db.pool.max_size to 5 (`chg-8919`)
- 13:14 P99 latency anomaly begins on ledger-service (`metric:ledger-service:latency_p99_ms`)
- 13:15 Error rate anomaly starts on ledger-service and payments-api (`metric:ledger-service:error_rate_pct`)
- 13:15 First payments-api error logged for ledger-service connection failure (`log-00465`)
- 13:15 First ledger-service connection timeout error logged (`log-00466`)
- 13:40 Incident reported by payments on-call

## Recommended actions

- **immediate**: Roll back config change chg-8919 and restore ledger-service db.pool.max_size to 50. Directly resolves connection pool exhaustion and restores successful payment confirmations. (`chg-8919`, `log-00466`)
- **short_term**: Audit automated config-sync jobs and normalization rules. Prevent future overrides of critical database connection pool settings. (`chg-8919`)
- **long_term**: Add alerting for database connection pool utilization approaching maximum capacity. Ensure early detection of pool exhaustion before request timeouts occur. (`metric:ledger-service:error_rate_pct`)
