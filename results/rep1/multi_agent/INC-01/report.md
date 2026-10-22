# INC-01: Payments failing after lunch

**Verdict:** root cause identified

An error rate surge on payments-api and mobile-bff started at 2026-10-02T14:03:00+00:00, exactly one minute after a deployment of payments-api v2.14.0 (chg-9890) which refactored payment-intent validation and bumped the JSON library. The deployment caused a NullPointerException in PaymentIntentValidator.java:88 due to payer_vpa being null, leading to 500 errors on payment attempts.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 1 · tool calls: 9 · LLM calls: 12 · tokens: 69118 · latency: 24.62s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Payments-API Refactor Bad Deploy | payments-api | bad_deploy | 0.95 | `chg-9890` Deploy of v2.14.0 at 14:02 UTC immediately preceded the onset of errors at 14:03 UTC.<br>`metric:payments-api:error_rate_pct` Payments-api error rate surged starting at 14:03 UTC.<br>`metric:mobile-bff:error_rate_pct` Mobile-bff error rate surged starting at 14:03 UTC.<br>`log-00758` Mobile-bff logged upstream errors indicating payments-api responded with 500 starting at 14:03 UTC.<br>`log-00759` Payments-api logged NullPointerException at PaymentIntentValidator.java:88 regarding payer_vpa being null starting at 14:03 UTC. | - |
| 2 | Mobile-BFF Client Payload Schema Change | mobile-bff | bad_deploy | 0.02 | `metric:mobile-bff:error_rate_pct` Mobile-bff error rate increased simultaneously.<br>`log-00758` Mobile-bff received 500 responses from payments-api. | `log-00759` Logs explicitly attribute the NullPointerException to payments-api internal validator code (PaymentIntentValidator.java:88), and no mobile-bff deployment occurred around that time. |

## Facts (evidence-backed)

- mobile-bff error rate started increasing at 2026-10-02T14:03:00Z, reaching a peak of 6.29% at 14:09:00Z. (`metric:mobile-bff:error_rate_pct`)
- payments-api error rate started increasing at 2026-10-02T14:03:00Z, reaching a peak of 20.29% at 14:07:00Z. (`metric:payments-api:error_rate_pct`)
- payments-api CPU usage increased starting at 2026-10-02T14:03:00Z, peaking at 48.63% at 14:19:00Z. (`metric:payments-api:cpu_pct`)
- mobile-bff logged upstream errors indicating payments-api responded with 500 for POST /v1/payments/intent starting at 2026-10-02T14:03:01Z. (`log-00758`)
- payments-api logged NullPointerException at PaymentIntentValidator.java:88 where payer_vpa is null, starting at 2026-10-02T14:03:05Z. (`log-00759`)
- A deploy for payments-api (v2.14.0, refactor payment-intent validation, bump json library) occurred at 2026-10-02T14:02:00+00:00 (chg-9890). (`chg-9890`)

## Assumptions (not proven)

- The refactored payment-intent validation logic in v2.14.0 incorrectly handles or strips the deserialization of payer_vpa under certain request payloads or json library behaviors.

## Evidence gaps

- none

## Timeline

- 14:02 Deploy of payments-api v2.14.0 (chg-9890) executed. (`chg-9890`)
- 14:03 Mobile-bff and payments-api error rate metrics begin to surge. (`metric:payments-api:error_rate_pct`)
- 14:03 Mobile-bff logs upstream 500 errors from payments-api for POST /v1/payments/intent. (`log-00758`)
- 14:03 Payments-api logs NullPointerException at PaymentIntentValidator.java:88 due to null payer_vpa. (`log-00759`)

## Recommended actions

- **immediate**: Rollback payments-api deployment v2.14.0 to the previous stable version (v2.13.4).. Directly mitigates the active bad deploy causing 500 errors and transaction failures. (`chg-9890`, `log-00759`)
- **short_term**: Fix the null check for payer_vpa inside PaymentIntentValidator.java and audit JSON library deserialization behavior.. Resolves the root cause of the NullPointerException introduced in the v2.14.0 refactor. (`log-00759`, `chg-9890`)
- **long_term**: Add automated integration tests covering validation behaviors with unpopulated or optional payment intent fields like payer_vpa.. Prevents similar deserialization or null-reference regressions during future validator refactors. (`log-00759`, `hist-2026-0702`)
