# INC-01: Payments failing after lunch

**Verdict:** root cause identified

Payments failed starting at 14:03 UTC on 2026-10-02 due to a code regression introduced by the deployment of payments-api v2.14.0 (chg-9890) at 14:02 UTC. The deployment refactored payment-intent validation and bumped the json library, resulting in NullPointerExceptions when processing null payer_vpa values.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 1 · tool calls: 8 · LLM calls: 11 · tokens: 62283 · latency: 36.15s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | payments-api deployment code regression | payments-api | bad_deploy | 0.95 | `chg-9890` A deployment on payments-api occurred at 14:02 UTC, precisely one minute before the error onset.<br>`metric:payments-api:error_rate_pct` payments-api error rate began rising steeply at 14:03 UTC.<br>`log-00759` payments-api began throwing NullPointerExceptions at 14:03:05 UTC in PaymentIntentValidator due to a null payer_vpa.<br>`metric:mobile-bff:error_rate_pct` mobile-bff error rate increased starting at 14:03 UTC due to upstream dependencies failing.<br>`log-00758` mobile-bff logged upstream 500 errors from payments-api starting at 14:03:01 UTC. | - |
| 2 | Simultaneous client payload change from mobile app | mobile-bff | unknown | 0.08 | `log-00759` The error specifically mentions that payer_vpa is null. | `chg-9890` A payments-api deployment occurred at 14:02 UTC, making a code-side validation change far more probable than an uncoordinated client payload change across all users at the exact same minute. |

## Facts (evidence-backed)

- mobile-bff error rate increased starting at 14:03 UTC, peaking at 6.29% at 14:09. (`metric:mobile-bff:error_rate_pct`)
- payments-api error rate increased starting at 14:03 UTC, peaking at 20.29% at 14:07. (`metric:payments-api:error_rate_pct`)
- payments-api CPU usage increased starting at 14:03 UTC, peaking at 48.63% at 14:19. (`metric:payments-api:cpu_pct`)
- mobile-bff logged upstream 500 errors from payments-api starting at 14:03:01 UTC. (`log-00758`)
- payments-api logged NullPointerExceptions due to payer_vpa being null starting at 14:03:05 UTC. (`log-00759`)
- payments-api was deployed (chg-9890) at 2026-10-02T14:02:00+00:00 with refactored payment-intent validation and a bumped json library. (`chg-9890`)

## Assumptions (not proven)

- The refactored validation logic in payments-api v2.14.0 fails to guard against null payer_vpa values.

## Evidence gaps

- none

## Timeline

- 14:02 payments-api v2.14.0 deployed with refactored payment-intent validation (`chg-9890`)
- 14:03 mobile-bff logs upstream 500 errors from payments-api (`log-00758`)
- 14:03 mobile-bff and payments-api error rates begin rising (`metric:payments-api:error_rate_pct`)
- 14:03 payments-api logs NullPointerException in PaymentIntentValidator due to null payer_vpa (`log-00759`)

## Recommended actions

- **immediate**: Roll back payments-api to version 2.13.4 to restore previous payment-intent validation logic.. Deployment chg-9890 introduced a code regression causing NullPointerExceptions and spiking error rates immediately after release. (`chg-9890`, `log-00759`, `metric:payments-api:error_rate_pct`)
- **short_term**: Add null safety checks and comprehensive unit tests for payer_vpa handling in PaymentIntentValidator.. Prevent future regressions from null payload fields during validation refactoring. (`log-00759`, `chg-9890`)
- **long_term**: Implement strict pre-release validation tests and canary deployments for payments-api changes.. Catch validation regressions and unhandled null pointer exceptions before full production rollout. (`chg-9890`, `metric:payments-api:error_rate_pct`)
