# INC-01: Payments failing after lunch

**Verdict:** root cause identified

A code deployment (chg-9890) to payments-api at 14:02 UTC introduced a NullPointerException in PaymentIntentValidator.java, causing payment failures starting at 14:03 UTC.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 9 · LLM calls: 4 · tokens: 46088 · latency: 30.47s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Code deploy bug in payments-api v2.14.0 | payments-api | bad_deploy | 0.95 | `chg-9890` Deployment of payments-api v2.14.0 occurred at 14:02 UTC, just one minute before symptoms started.<br>`metric:payments-api:error_rate_pct` Error rate spiked sharply at 14:03 UTC reaching 19.1%.<br>`metric:mobile-bff:error_rate_pct` Error rate spiked at 14:03 UTC reaching 5.31% due to downstream failures.<br>`log-00759` payments-api logs show NullPointerException at PaymentIntentValidator.validate starting at 14:03:05 UTC.<br>`log-00758` mobile-bff logs show upstream payments-api 500 errors starting at 14:03:01 UTC. | - |
| 2 | External UPI or NPCI gateway outage | npci-switch | third_party_outage | 0.05 | - | `metric:upi-gateway:error_rate_pct` upi-gateway error rate remained entirely normal around ~0.2% - 0.34% with no anomaly during the incident window. |

## Facts (evidence-backed)

- payments-api v2.14.0 was deployed at 2026-10-02T14:02:00+00:00 with changes to payment-intent validation. (`chg-9890`)
- Error rates for payments-api and mobile-bff increased sharply starting at 14:03:00+00:00. (`metric:payments-api:error_rate_pct`, `metric:mobile-bff:error_rate_pct`)
- payments-api logged NullPointerException at PaymentIntentValidator.java:88 starting at 14:03:05+00:00. (`log-00759`)
- mobile-bff logged upstream payments-api 500 responses starting at 14:03:01+00:00. (`log-00758`)
- upi-gateway error rates and latency exhibited no anomalies throughout the window. (`metric:upi-gateway:error_rate_pct`, `metric:upi-gateway:latency_p99_ms`)

## Assumptions (not proven)

- Mobile app clients sent payment payloads that triggered the null pointer condition in the newly introduced validation code.

## Evidence gaps

- none

## Timeline

- 14:02 payments-api v2.14.0 deployed (`chg-9890`)
- 14:03 Error rate anomaly begins on mobile-bff and payments-api (`metric:payments-api:error_rate_pct`)
- 14:03 mobile-bff logs first upstream 500 error from payments-api (`log-00758`)
- 14:03 payments-api logs first NullPointerException in PaymentIntentValidator (`log-00759`)
- 14:20 Incident reported by on-call SRE Priya

## Recommended actions

- **immediate**: Rollback payments-api from v2.14.0 to v2.13.4. Directly resolves the bad deployment causing widespread payment transaction failures. (`chg-9890`, `log-00759`)
- **short_term**: Fix null pointer check in PaymentIntentValidator.java. Ensure payer_vpa validation robustly handles null inputs before re-releasing the refactored validation logic. (`log-00759`)
