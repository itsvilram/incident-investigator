# INC-03: Checkout timeouts on UPI pay

**Verdict:** root cause identified

UPI checkout timeouts and payments-api latency spikes were caused by performance degradation in the external partner-bank-api, which caused upi-gateway worker threads to block and exhaust the worker pool, leading to timeouts across payments-api.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 12 · LLM calls: 5 · tokens: 68769 · latency: 15.91s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Partner Bank API Latency Degradation | partner-bank-api | third_party_outage | 0.85 | `log-00657` upi-gateway logs show slow calls to partner-bank-api starting at 13:42.<br>`log-00742` upi-gateway worker pool exhausted waiting on partner-bank-api.<br>`log-00698` payments-api timing out calling upi-gateway.<br>`metric:payments-api:latency_p99_ms` p99 latency jumped significantly starting at 13:45. | `metric:partner-bank-api:rps` Metrics backend returned partial data missing latency and error rate metrics. |
| 2 | upi-gateway Worker Pool Exhaustion | upi-gateway | resource_exhaustion | 0.55 | `log-00742` Worker pool exhausted (200/200 busy), rejecting requests. | `hist-2026-0530` Worker pool size of 200 was previously deemed sufficient under normal conditions; exhaustion is secondary to downstream slowness. |

## Facts (evidence-backed)

- payments-api error rate and p99 latency spiked starting around 13:45-13:47 UTC. (`metric:payments-api:error_rate_pct`, `metric:payments-api:latency_p99_ms`)
- upi-gateway logged slow responses from partner-bank-api starting at 13:42:16 UTC. (`log-00657`)
- upi-gateway worker pool became exhausted and rejected requests starting at 13:47:40 UTC. (`log-00742`)
- No code deployments occurred for payments-api or upi-gateway in the preceding 24 hours. (`get_deployments`)

## Assumptions (not proven)

- External partner-bank-api experienced database or internal service degradation causing synchronous calls to hang.
- Customer-facing UPI payment timeouts correlate directly with the payments-api and upi-gateway request timeouts.

## Evidence gaps

- Metrics backend returned partial data missing error rate and p99 latency for partner-bank-api.
- Log shards timed out resulting in incomplete log match counts for upi-gateway.

## Timeline

- 13:30 fraud-service velocity threshold configuration change (`chg-9502`)
- 13:42 First slow call to partner-bank-api logged by upi-gateway (`log-00657`)
- 13:43 upi-gateway p99 latency anomaly starts (`metric:upi-gateway:latency_p99_ms`)
- 13:45 payments-api p99 latency anomaly starts (`metric:payments-api:latency_p99_ms`)
- 13:46 First payments-api timeout error calling upi-gateway (`log-00698`)
- 13:47 payments-api and mobile-bff error rate anomalies start (`metric:payments-api:error_rate_pct`)
- 13:47 upi-gateway worker pool exhaustion and request rejection (`log-00742`)
- 14:10 Incident reported by on-call SRE

## Recommended actions

- **immediate**: Coordinate with partner bank ops team to verify partner-bank-api performance.. Partner bank degradation is the root cause of downstream worker pool exhaustion and payment timeouts. (`log-00657`, `log-00742`)
- **immediate**: Implement or tune circuit breakers on upi-gateway for partner-bank-api calls.. Failing fast prevents thread starvation and worker pool exhaustion during third-party degradation. (`log-00742`, `hist-2026-0618`)
- **long_term**: Add non-blocking I/O or asynchronous patterns for external dependency calls.. Protects internal gateways from being bottlenecked by synchronous third-party API latency. (`log-00742`)
