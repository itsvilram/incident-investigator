# INC-03: Checkout timeouts on UPI pay

**Verdict:** root cause identified

An incident involving checkout timeouts on UPI payments occurred on 2026-10-04, with symptoms beginning at 13:41 UTC. The investigation concluded that an external third-party latency spike in the partner-bank-api caused upstream worker pool exhaustion in upi-gateway, which subsequently triggered timeouts and error rate spikes in payments-api and mobile-bff.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 1 · tool calls: 12 · LLM calls: 12 · tokens: 95695 · latency: 39.8s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Partner Bank API Latency Spike Causing Worker Exhaustion | partner-bank-api | third_party_outage | 0.95 | `metric:partner-bank-api:latency_p99_ms` Shows partner-bank-api latency spike beginning at 13:41 UTC, which precedes all other dependent service anomalies.<br>`metric:upi-gateway:latency_p99_ms` Shows upi-gateway latency anomaly starting at 13:43 UTC, directly following the partner bank latency increase.<br>`log-00742` Confirms upi-gateway workers were exhausted because they were waiting on partner-bank-api.<br>`log-00698` Shows payments-api timing out when calling upi-gateway.<br>`metric:payments-api:latency_p99_ms` Shows payments-api latency p99 anomaly starting at 13:45 UTC. | - |
| 2 | Fraud Service Configuration Change Induced Processing Delays | fraud-service | config_change | 0.05 | `chg-9502` Configuration change on fraud-service occurred shortly before the incident onset. | `metric:partner-bank-api:latency_p99_ms` Latency started rising at 13:41 UTC, whereas logs specifically show workers waiting on partner-bank-api rather than fraud-service.<br>`log-00742` Worker pool exhaustion is explicitly attributed to waiting on partner-bank-api, not fraud-service. |

## Facts (evidence-backed)

- upi-gateway latency p99 anomaly started at 2026-10-04T13:43:00+00:00, reaching a peak of 10665.76ms. (`metric:upi-gateway:latency_p99_ms`)
- upi-gateway error rate anomaly started at 2026-10-04T13:46:00+00:00, peaking at 13.72%. (`metric:upi-gateway:error_rate_pct`)
- payments-api latency p99 anomaly started at 2026-10-04T13:45:00+00:00, reaching a peak of 10772.92ms. (`metric:payments-api:latency_p99_ms`)
- payments-api error rate anomaly started at 2026-10-04T13:47:00+00:00, peaking at 12.58%. (`metric:payments-api:error_rate_pct`)
- payments-api CPU usage anomaly started at 2026-10-04T13:46:00+00:00, reaching a peak of 57.2%. (`metric:payments-api:cpu_pct`)
- payments-api logged repeated timeout errors calling upi-gateway POST /v2/collect after 10000ms. (`log-00698`)
- mobile-bff error rate anomaly started at 2026-10-04T13:47:00+00:00, peaking at 4.67%. (`metric:mobile-bff:error_rate_pct`)
- upi-gateway logged worker pool exhaustion rejecting requests due to being busy waiting on partner-bank-api. (`log-00742`)
- partner-bank-api latency p99 anomaly started at 2026-10-04T13:41:00+00:00, peaking at 9237.07ms. (`metric:partner-bank-api:latency_p99_ms`)
- fraud-service configuration was modified at 2026-10-04T13:30:00+00:00 to raise velocity threshold from 5 to 7 transactions/min. (`chg-9502`)

## Assumptions (not proven)

- The underlying cause of the partner-bank-api latency is an external issue at the partner bank.

## Evidence gaps

- query_logs(service=upi-gateway) returned partial data

## Timeline

- 13:30 fraud-service rules changed to raise velocity threshold from 5 to 7 transactions/min (`chg-9502`)
- 13:41 partner-bank-api latency_p99 anomaly begins, reaching baseline to 8349.7 ms (`metric:partner-bank-api:latency_p99_ms`)
- 13:43 upi-gateway latency_p99 anomaly begins (`metric:upi-gateway:latency_p99_ms`)
- 13:45 payments-api latency_p99 anomaly begins and partner-bank-api error rate anomaly begins (`metric:payments-api:latency_p99_ms`)
- 13:46 payments-api CPU usage anomaly begins and upi-gateway error rate anomaly begins (`metric:payments-api:cpu_pct`)
- 13:47 payments-api error rate and mobile-bff error rate anomalies begin, alongside upi-gateway worker pool exhaustion logs (`metric:payments-api:error_rate_pct`)

## Recommended actions

- **immediate**: Coordinate with the external partner bank provider to investigate the root cause of the latency spike on partner-bank-api.. The incident root cause stems directly from performance degradation at partner-bank-api beginning at 13:41 UTC. (`metric:partner-bank-api:latency_p99_ms`, `log-00742`)
- **short_term**: Implement circuit breakers or aggressive timeout fallbacks between upi-gateway and partner-bank-api to prevent thread and worker pool exhaustion.. Worker pool exhaustion at upi-gateway caused widespread downstream cascading timeout failures in payments-api. (`log-00742`, `log-00698`)
- **long_term**: Review alerting thresholds for upstream external dependencies to detect third-party latency anomalies before worker pools are fully exhausted.. Early detection of external dependency issues can prevent cascading checkout failures for end users. (`metric:partner-bank-api:latency_p99_ms`, `metric:upi-gateway:error_rate_pct`)
