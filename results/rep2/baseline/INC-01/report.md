# INC-01: Payments failing after lunch

**Verdict:** root cause identified

Deployment of payments-api v2.14.0 introduced a NullPointerException regression in PaymentIntentValidator.java:88 when payer_vpa is null, causing approximately 15-20% failure rates across payment attempts starting at 14:03.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 8 · LLM calls: 4 · tokens: 48476 · latency: 14.69s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | payments-api v2.14.0 deployment introduces a NullPointerException during PaymentIntentValidator validation when payer_vpa is null | payments-api | bad_deploy | 0.95 | `chg-9890` Deployment of payments-api v2.14.0 at 14:02:00 explicitly refactored payment-intent validation.<br>`metric:payments-api:error_rate_pct` Error rate spiked sharply starting at 14:03:00, reaching over 20%.<br>`metric:mobile-bff:error_rate_pct` Mobile-bff error rate mirrored the spike starting at 14:03:00.<br>`log-00759` NullPointerException at PaymentIntentValidator.validate(PaymentIntentValidator.java:88): payer_vpa is null started immediately after deploy at 14:03:05.<br>`log-00758` mobile-bff logged upstream 500 errors responding to POST /v1/payments/intent starting at 14:03:01. | - |
| 2 | Upstream NPCI switch or UPI Gateway degradation causing request failures | upi-gateway | dependency_failure | 0.05 | - | `metric:upi-gateway:error_rate_pct` upi-gateway error rate remained entirely stable and normal (~0.25%) throughout the incident window.<br>`log-00759` Errors are internal NullPointerExceptions in payments-api code, not gateway timeouts or external failures. |

## Facts (evidence-backed)

- payments-api error rate spiked starting at 14:03:00, peaking at 20.29%. (`metric:payments-api:error_rate_pct`)
- mobile-bff error rate spiked starting at 14:03:00, peaking at 6.29%. (`metric:mobile-bff:error_rate_pct`)
- payments-api v2.14.0 was deployed at 2026-10-02T14:02:00+00:00 with summary 'payments-api v2.14.0: refactor payment-intent validation, bump json library'. (`chg-9890`)
- payments-api began logging NullPointerException at PaymentIntentValidator.validate(PaymentIntentValidator.java:88): payer_vpa is null at 14:03:05. (`log-00759`)
- mobile-bff logged upstream payments-api responded 500 errors starting at 14:03:01. (`log-00758`)
- upi-gateway error rate remained stable with no anomaly during the incident window. (`metric:upi-gateway:error_rate_pct`)

## Assumptions (not proven)

- The code refactor in payments-api v2.14.0 altered field handling such that requests lacking or having null payer_vpa are no longer safely defaulted or filtered before reaching validation.

## Evidence gaps

- Exact request payloads containing null payer_vpa were not inspected via raw packet or full request log inspection.

## Timeline

- 12:22 market-data-service v6.7.0 deployed (`chg-9177`)
- 12:23 market-data-service v1.17.0 deployed (`chg-9557`)
- 14:02 payments-api v2.14.0 deployed (`chg-9890`)
- 14:03 Error rate anomaly begins on payments-api and mobile-bff (`metric:payments-api:error_rate_pct`)
- 14:03 mobile-bff logs first upstream 500 error from payments-api (`log-00758`)
- 14:03 payments-api logs first NullPointerException in PaymentIntentValidator (`log-00759`)
- 14:20 Incident INC-01 reported by on-call SRE Priya

## Recommended actions

- **immediate**: Rollback payments-api to version v2.13.4. Rolls back the bad deployment chg-9890 which introduced the NullPointerException regression. (`chg-9890`, `log-00759`)
- **short_term**: Fix null safety in PaymentIntentValidator.java. Ensures requests with missing or null payer_vpa are safely validated or rejected with proper client error responses instead of unhandled 500 exceptions. (`log-00759`)
- **long_term**: Add integration test coverage for null or missing payment intent fields. Prevents similar validation regressions from passing CI/CD pipelines. (`chg-9890`)
