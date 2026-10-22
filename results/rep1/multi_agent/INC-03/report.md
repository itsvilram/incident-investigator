# INC-03: Checkout timeouts on UPI pay

**Verdict:** root cause identified

Checkout timeouts on UPI pay occurred due to an external latency and error rate spike in partner-bank-api starting at 13:41. This caused upi-gateway worker pools to exhaust as requests blocked waiting on partner-bank-api, leading to upi-gateway latency spikes and timeouts that subsequently cascaded into payments-api and mobile-bff error rates.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 1 · tool calls: 13 · LLM calls: 13 · tokens: 101059 · latency: 54.21s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | External Partner Bank Latency Spike | partner-bank-api | third_party_outage | 0.95 | `metric:partner-bank-api:latency_p99_ms` Shows the earliest anomaly onset at 13:41 preceding all other service latencies.<br>`metric:upi-gateway:latency_p99_ms` Shows upi-gateway latency rising immediately after partner-bank-api at 13:43.<br>`log-00742` Shows upi-gateway worker pool exhaustion with workers waiting on partner-bank-api.<br>`metric:payments-api:latency_p99_ms` Shows payments-api latency jumping at 13:45 mirroring downstream delays. | - |
| 2 | UPI Gateway Worker Pool Concurrency Bottleneck | upi-gateway | resource_exhaustion | 0.05 | `log-00742` Confirms worker pool exhaustion (200/200 busy) on upi-gateway. | `metric:partner-bank-api:latency_p99_ms` Partner-bank-api latency started rising at 13:41, whereas upi-gateway metrics only started rising at 13:43, proving the fault originated upstream. |

## Facts (evidence-backed)

- partner-bank-api latency_p99_ms showed an anomaly starting upward from 13:41, reaching a peak of 9237.07 ms at 14:01. (`metric:partner-bank-api:latency_p99_ms`)
- upi-gateway latency_p99_ms showed an anomaly starting upward from 13:43. (`metric:upi-gateway:latency_p99_ms`)
- payments-api latency_p99_ms showed an anomaly starting upward from 13:45, reaching a peak of 10772.92 ms at 13:55. (`metric:payments-api:latency_p99_ms`)
- partner-bank-api error_rate_pct showed an anomaly starting upward from 13:45, reaching a peak of 4.56% at 13:49. (`metric:partner-bank-api:error_rate_pct`)
- payments-api logs showed continuous 10000ms timeouts calling upi-gateway POST /v2/collect beginning at 13:46:00. (`log-00698`)
- upi-gateway error_rate_pct showed an anomaly starting upward from 13:46. (`metric:upi-gateway:error_rate_pct`)
- payments-api error_rate_pct showed an anomaly starting upward from 13:47. (`metric:payments-api:error_rate_pct`)
- mobile-bff error_rate_pct showed an anomaly starting upward from 13:47. (`metric:mobile-bff:error_rate_pct`)
- upi-gateway experienced worker pool exhaustion (200/200 busy), rejecting requests with most workers waiting on partner-bank-api starting at 13:47. (`log-00742`)
- orders-service v1.25.0 was deployed at 2026-10-04T12:07:00+00:00. (`chg-9328`)
- ledger-service v6.7.0 was deployed at 2026-10-04T12:29:00+00:00. (`chg-9500`)
- fraud-service velocity threshold configuration was raised from 5 to 7 transactions/min at 2026-10-04T13:30:00+00:00. (`chg-9502`)

## Assumptions (not proven)

- The root cause inside partner-bank-api is entirely external and outside internal system logs.

## Evidence gaps

- query_logs(service=upi-gateway) returned partial data
- query_metrics(service=partner-bank-api) returned partial data

## Timeline

- 12:07 orders-service v1.25.0 routine release deployed (`chg-9328`)
- 12:29 ledger-service v6.7.0 routine release deployed (`chg-9500`)
- 13:30 fraud-service velocity threshold configuration raised from 5 to 7 transactions/min (`chg-9502`)
- 13:41 partner-bank-api latency_p99_ms begins anomaly rise (`metric:partner-bank-api:latency_p99_ms`)
- 13:43 upi-gateway latency_p99_ms begins anomaly rise (`metric:upi-gateway:latency_p99_ms`)
- 13:45 payments-api latency_p99_ms and partner-bank-api error_rate_pct begin anomaly rises (`metric:payments-api:latency_p99_ms`)
- 13:46 payments-api logs timeouts calling upi-gateway; upi-gateway error_rate_pct begins rising (`log-00698`)
- 13:47 upi-gateway worker pool exhausted; payments-api and mobile-bff error rates begin rising (`log-00742`)

## Recommended actions

- **immediate**: Coordinate with the external partner-bank-api provider to investigate their latency spike and error rates.. partner-bank-api is the upstream origin of the latency and failure chain. (`metric:partner-bank-api:latency_p99_ms`, `metric:partner-bank-api:error_rate_pct`)
- **short_term**: Implement circuit breakers and aggressive request shedding on upi-gateway for calls to partner-bank-api.. Prevents upi-gateway worker pool exhaustion and cascading failures to payments-api when partner-bank-api degrades. (`log-00742`, `metric:upi-gateway:latency_p99_ms`)
- **long_term**: Establish secondary redundant payment routes or fallback partner banks for UPI transactions.. Mitigates single-vendor external dependencies causing total feature degradation. (`dep:upi-gateway->partner-bank-api`, `metric:partner-bank-api:latency_p99_ms`)
