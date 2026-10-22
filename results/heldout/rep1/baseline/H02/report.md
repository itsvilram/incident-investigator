# H02: Payments timing out

**Verdict:** root cause identified

Payments timed out starting at 2026-10-17T13:06:00Z due to a cascade of statement timeouts in ledger-service caused by database connection pool saturation and write lock contention in ledger-db.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 12 · LLM calls: 5 · tokens: 68714 · latency: 19.18s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Database connection pool saturation and statement timeouts in ledger-db | ledger-db | resource_exhaustion | 0.90 | `metric:payments-api:error_rate_pct` Shows payments-api error rate spiking at 13:06:00Z.<br>`metric:ledger-db:connections_active` Shows active connections on ledger-db surging from ~45 to ~180 starting at 13:05:00Z.<br>`metric:ledger-db:latency_p99_ms` Shows ledger-db latency spiking starting at 13:05:00Z.<br>`log-00445` Shows ledger-service hitting statement timeouts on INSERT INTO ledger_entries starting at 13:06:04Z.<br>`log-00443` Shows payments-api timing out waiting on ledger-service POST /entries starting at 13:06:02Z. | `metric:ledger-db:cpu_pct` ledger-db CPU dropped rather than increased during the incident, pointing to connection waiting/blocking rather than heavy query compute. |
| 2 | Config change on payments-api ledger client logging introduced performance degradation | payments-api | config_change | 0.10 | `chg-9660` A config change modified ledger client logging from INFO to DEBUG at 13:02:00Z, shortly before the incident onset. | `log-00445` Errors originate in ledger-db and ledger-service statement timeouts on database inserts, not in client logging routines. |

## Facts (evidence-backed)

- Payments-api error rate and p99 latency anomalies started at 2026-10-17T13:06:00Z. (`metric:payments-api:error_rate_pct`, `metric:payments-api:latency_p99_ms`)
- Ledger-service error rate and latency anomalies started at 2026-10-17T13:05:00Z / 13:06:00Z. (`metric:ledger-service:error_rate_pct`, `metric:ledger-service:latency_p99_ms`)
- Ledger-db active connections jumped from ~45 to ~180 at 2026-10-17T13:05:00Z. (`metric:ledger-db:connections_active`)
- Ledger-service logged statement timeouts on INSERT INTO ledger_entries starting at 2026-10-17T13:06:04Z. (`log-00445`)
- Payments-api logged timeouts waiting for ledger-service POST /entries starting at 2026-10-17T13:06:02Z. (`log-00443`)
- Config change chg-9660 updated payments-api ledger client log level to DEBUG at 2026-10-17T13:02:00Z. (`chg-9660`)

## Assumptions (not proven)

- The surge in active database connections reaching ~180 corresponds to maximum connection pool capacity, causing subsequent queries to queue and hit statement timeouts.
- The drop in ledger-db CPU usage is due to threads waiting on locks or connection acquisition.

## Evidence gaps

- Exact connection pool maximum limit configuration for ledger-service was not inspected directly.
- Detailed query execution plans and row lock contention telemetry were not available.

## Timeline

- 13:02 Config change chg-9660 applied to payments-api changing ledger client log level to DEBUG (`chg-9660`)
- 13:05 ledger-db active connections spike to 180 and p99 latency jumps (`metric:ledger-db:connections_active`)
- 13:06 Error rate and latency anomalies register on payments-api and ledger-service (`metric:payments-api:error_rate_pct`)
- 13:06 First payments-api timeout error logged for ledger-service POST /entries (`log-00443`)
- 13:06 First ledger-service statement timeout logged for INSERT INTO ledger_entries (`log-00445`)
- 13:35 Incident reported by payments on-call

## Recommended actions

- **immediate**: Kill or cancel stuck or long-running transactions on ledger-db holding locks.. Active connections are saturated and queries are hitting 10s statement timeouts due to lock contention. (`metric:ledger-db:connections_active`, `log-00445`)
- **immediate**: Scale up database connection limits or restart connection pools on ledger-service.. Exhausted connection pools prevent new write requests from being processed. (`metric:ledger-db:connections_active`)
- **short_term**: Investigate database query execution plans for INSERT INTO ledger_entries to identify locking bottlenecks.. Prevents recurrence of database write deadlocks and connection saturation. (`log-00445`)
- **short_term**: Implement circuit breakers and bulkhead isolation between payments-api and ledger-service.. Prevents downstream database saturation from completely blocking payment front-ends. (`log-00443`)
- **long_term**: Add automated alerting for database active connection pool saturation exceeding 80% capacity.. Early warning before connection exhaustion leads to user-facing timeouts. (`metric:ledger-db:connections_active`)
