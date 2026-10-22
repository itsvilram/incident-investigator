# INC-03: Checkout timeouts on UPI pay

**Verdict:** root cause identified

UPI checkout timeouts were caused by severe latency degradation on partner-bank-api, which exhausted worker pools on upi-gateway and triggered cascading 10-second timeout errors on payments-api.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 9 · LLM calls: 6 · tokens: 56303 · latency: 16.1s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | External Partner Bank API Degradation | partner-bank-api | third_party_outage | 0.90 | `log-00742` upi-gateway worker pool exhausted waiting on partner-bank-api<br>`metric:upi-gateway:latency_p99_ms` upi-gateway latency spiked dramatically starting at 13:43<br>`log-00698` payments-api timed out calling upi-gateway POST /v2/collect<br>`metric:payments-api:latency_p99_ms` payments-api latency jumped to ~9s starting at 13:45<br>`hist-2026-0618` Past incident shows similar symptom signature during partner bank degradation | - |
| 2 | Internal Code Deploy or Config Change | payments-api | bad_deploy | 0.05 | - | `chg:none` No deployments found for payments-api or upi-gateway in the 24-hour window |

## Facts (evidence-backed)

- payments-api p99 latency jumped from ~380ms to over 10s starting at 2026-10-04T13:45:00+00:00. (`metric:payments-api:latency_p99_ms`)
- payments-api error rate jumped to ~11% starting at 2026-10-04T13:47:00+00:00. (`metric:payments-api:error_rate_pct`)
- payments-api logged timeout errors calling upi-gateway POST /v2/collect after 10000ms. (`log-00698`)
- upi-gateway reported worker pool exhausted (200/200 busy) with most workers waiting on partner-bank-api. (`log-00742`)
- No deployments occurred for payments-api or upi-gateway in the past 24 hours. ()

## Assumptions (not proven)

- External telemetry accurately reflects degradation on partner-bank-api since direct server logs are absent.

## Evidence gaps

- Lack of direct server-side logs and metrics from external vendor partner-bank-api.
- Partial log shard timeout during query_logs for upi-gateway.

## Timeline

- 13:43 upi-gateway p99 latency starts spiking above baseline. (`metric:upi-gateway:latency_p99_ms`)
- 13:45 payments-api p99 latency jumps significantly. (`metric:payments-api:latency_p99_ms`)
- 13:46 payments-api logs first 10-second timeout error calling upi-gateway. (`log-00698`)
- 13:47 payments-api and upi-gateway error rates spike to ~11%. (`metric:payments-api:error_rate_pct`)
- 13:47 upi-gateway logs worker pool exhaustion waiting on partner-bank-api. (`log-00742`)
- 14:10 Incident INC-03 reported by on-call SRE Kabir.

## Recommended actions

- **immediate**: Notify partner bank operations team regarding ongoing degradation and request status on partner-bank-api.. The root cause originates in the external partner bank API. (`log-00742`)
- **immediate**: Enable or lower circuit breaker thresholds on upi-gateway to fast-fail requests during partner bank degradation.. Prevents worker pool exhaustion and cascading request pile-ups inside upi-gateway and payments-api. (`log-00742`, `log-00698`, `hist-2026-0618`)
- **short_term**: Implement fallback routing to alternative partner banks or payment gateways.. Maintains customer transaction success rates when primary partner APIs fail. (`hist-2026-0618`)
