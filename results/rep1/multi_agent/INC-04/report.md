# INC-04: DB connection errors in payments

**Verdict:** root cause identified

An incident occurred at 2026-10-06T13:14:00+00:00 causing database connection errors in payments-api and ledger-service. The investigation confirms that a configuration change (chg-8919) at 13:12 UTC reduced ledger-service database pool max size from 50 to 5, resulting in immediate connection pool exhaustion and elevated error rates.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 1 · tool calls: 7 · LLM calls: 11 · tokens: 56904 · latency: 53.09s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Database connection pool size reduction in ledger-service | ledger-service | config_change | 0.95 | `chg-8919` Config change reduced ledger-service db.pool.max_size from 50 to 5 right before onset<br>`metric:ledger-service:latency_p99_ms` Latency began rising sharply starting at 13:14 UTC<br>`metric:ledger-service:error_rate_pct` Error rate surged starting at 13:15 UTC<br>`log-00466` Ledger-service logged HikariPool-1 connection timeout errors with active=5 and high waiting requests<br>`log-00465` Payments-api logged downstream connection acquisition failures when calling ledger-service | - |
| 2 | Routine deployment regression in event-bus | event-bus | bad_deploy | 0.02 | `chg-8200` Routine deploy chg-8200 occurred on event-bus shortly before the incident | `chg-8919` Directly links the connection pool exhaustion to ledger-service configuration change rather than event-bus<br>`log-00466` Logs specifically point to ledger-service database connection pool exhaustion rather than event-bus failures |

## Facts (evidence-backed)

- ledger-service latency_p99_ms began rising at 2026-10-06T13:14:00+00:00, reaching a peak of 7278.17ms at 13:41:00+00:00. (`metric:ledger-service:latency_p99_ms`)
- ledger-service error_rate_pct started its anomalous increase at 2026-10-06T13:15:00+00:00, peaking at 10.25%. (`metric:ledger-service:error_rate_pct`)
- payments-api error_rate_pct started its anomalous increase at 2026-10-06T13:15:00+00:00, peaking at 8.26%. (`metric:payments-api:error_rate_pct`)
- ledger-service first logged HikariPool-1 connection timeout errors at 2026-10-06T13:15:05+00:00 indicating connection pool exhaustion (total=5, active=5, idle=0, waiting=434). (`log-00466`)
- payments-api first logged downstream connection acquisition failures when calling ledger-service at 2026-10-06T13:15:02+00:00. (`log-00465`)
- A configuration change chg-8919 occurred on ledger-service at 2026-10-06T13:12:00+00:00, normalizing db.pool.max_size from 50 to 5. (`chg-8919`)

## Assumptions (not proven)

- The reduction of the connection pool size to 5 was inadequate for handling normal traffic volume received by ledger-service.

## Evidence gaps

- none

## Timeline

- 12:35 Routine deploy chg-8200 on event-bus (`chg-8200`)
- 12:36 Routine deploy chg-8270 on fraud-service (`chg-8270`)
- 13:12 Config change chg-8919 on ledger-service normalizing db.pool.max_size from 50 to 5 (`chg-8919`)
- 13:14 ledger-service latency_p99_ms begins anomalous increase (`metric:ledger-service:latency_p99_ms`)
- 13:15 ledger-service and payments-api error rates begin anomalous increase (`metric:ledger-service:error_rate_pct`)
- 13:15 payments-api logs downstream connection acquisition failures (`log-00465`)
- 13:15 ledger-service logs HikariPool-1 connection timeout errors (`log-00466`)

## Recommended actions

- **immediate**: Immediate rollback or update of ledger-service configuration to restore db.pool.max_size back to 50.. Configuration change chg-8919 directly caused database connection pool exhaustion and elevated error rates. (`chg-8919`, `log-00466`, `metric:ledger-service:error_rate_pct`)
- **short_term**: Review configuration sync automation to ensure changes do not inappropriately override critical resource parameters.. The change was introduced via config-sync normalizing parameters across services without accounting for specific throughput needs. (`chg-8919`)
- **long_term**: Implement validation checks and automated alerting for database connection pool parameters and pool exhaustion metrics across all core microservices.. Ensures similar misconfigurations are caught and alerted before causing widespread customer-facing payment failures. (`log-00466`, `metric:ledger-service:latency_p99_ms`)
