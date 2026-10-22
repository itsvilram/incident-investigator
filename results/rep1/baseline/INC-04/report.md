# INC-04: DB connection errors in payments

**Verdict:** root cause identified

An automated configuration sync reduced the maximum database connection pool size in ledger-service from 50 to 5, leading to connection timeouts and error rate spikes in both ledger-service and payments-api.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 7 · LLM calls: 3 · tokens: 27047 · latency: 10.29s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Automated config change drastically reduced database pool size in ledger-service | ledger-service | config_change | 0.95 | `chg-8919` Config change reduced db.pool.max_size from 50 to 5 at 13:12.<br>`metric:ledger-service:error_rate_pct` Ledger service error rate spiked upward at 13:15.<br>`metric:ledger-service:latency_p99_ms` Ledger service p99 latency spiked starting at 13:14.<br>`log-00466` HikariPool errors show total=5 and active=5 with request timeouts starting at 13:15.<br>`log-00465` Payments-api received 503 errors when calling ledger-service starting at 13:15. | - |
| 2 | Traffic surge caused connection starvation | ledger-service | traffic_spike | 0.05 | `metric:ledger-service:rps` RPS remained at normal baseline levels. | `metric:ledger-service:rps` RPS showed no abnormal surge during the incident window. |

## Facts (evidence-backed)

- At 2026-10-06T13:12:00+00:00, config change chg-8919 normalized db.pool.max_size from 50 to 5 on ledger-service. (`chg-8919`)
- Error rates for both payments-api and ledger-service started increasing at 13:15. (`metric:payments-api:error_rate_pct`, `metric:ledger-service:error_rate_pct`)
- HikariPool errors reported connection timeouts with total=5 active=5. (`log-00466`)

## Assumptions (not proven)

- The configuration change chg-8919 was applied universally by platform-bot and incorrectly clamped the connection pool for ledger-service.

## Evidence gaps

- none

## Timeline

- 13:12 Config change chg-8919 applied to ledger-service reducing db.pool.max_size to 5. (`chg-8919`)
- 13:14 ledger-service latency p99 starts increasing. (`metric:ledger-service:latency_p99_ms`)
- 13:15 Error rate anomaly begins on payments-api and ledger-service. (`metric:ledger-service:error_rate_pct`)
- 13:15 First payments-api error logged for ledger-service connection failure. (`log-00465`)
- 13:15 First ledger-service connection timeout logged. (`log-00466`)
- 13:40 Incident INC-04 reported by on-call.

## Recommended actions

- **immediate**: Revert configuration change chg-8919 to restore ledger-service database connection pool size back to 50.. Directly resolves the resource constraint causing connection timeouts and payment confirmation failures. (`chg-8919`, `log-00466`)
- **long_term**: Add validation checks and guardrails to platform-bot configuration syncs.. Prevents automated config scripts from applying dangerously low pool size limits to backend services. (`chg-8919`)
