# INC-12: UPI payments failing for some users

**Verdict:** root cause identified

Approximately 8% of UPI payments began failing at 14:07 on 2026-10-07 due to an incorrect routing configuration update on upi-gateway. The configuration change (chg-9824) shifted @okbank handles to partner-bank-api /v3/collect, which resulted in HTTP 404 Not Found errors from partner-bank-api and subsequent U30 route failure errors in payments-api.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 1 · tool calls: 8 · LLM calls: 11 · tokens: 58547 · latency: 24.52s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Routing Configuration Update on upi-gateway Introduced Invalid Endpoint Path for @okbank | upi-gateway | config_change | 0.95 | `chg-9824` Configuration change updating @okbank handles to partner-bank-api /v3/collect occurred at 14:06, immediately preceding the anomaly.<br>`metric:payments-api:error_rate_pct` payments-api error rate rose sharply starting at 14:07.<br>`metric:upi-gateway:error_rate_pct` upi-gateway error rate rose sharply starting at 14:07.<br>`log-00788` upi-gateway logs show partner-bank-api returning 404 Not Found for POST /v3/collect starting at 14:07.<br>`log-00790` payments-api logs report failures due to upi-gateway error U30 (route failure) starting at 14:07. | - |
| 2 | Concurrent payments-api Deployment (v2.15.0) Caused Routing Incompatibilities | payments-api | bad_deploy | 0.05 | `chg-9649` payments-api v2.15.0 deployed at 14:05, just before the incident onset. | `log-00788` The root cause of failure is explicitly partner-bank-api returning 404 for /v3/collect, which directly links to the upi-gateway routing table configuration change (chg-9824).<br>`chg-9824` The specific targeted failure affecting only @okbank users matches the routing table update precisely. |

## Facts (evidence-backed)

- The error rate anomaly for payments-api began at 2026-10-07T14:07:00+00:00, jumping from a baseline of ~0.28% to 7.54% and peaking at 8.71%. (`metric:payments-api:error_rate_pct`)
- The error rate anomaly for upi-gateway began at 2026-10-07T14:07:00+00:00, jumping from a baseline of ~0.25% to 8.57% and reaching 10.28%. (`metric:upi-gateway:error_rate_pct`)
- payments-api logs report UPI collect failures due to upi-gateway error U30 (route failure). (`log-00790`)
- upi-gateway logs report partner-bank-api returning 404 Not Found for collect requests. (`log-00788`)
- A deploy for payments-api v2.15.0 occurred on 2026-10-07 at 14:05:00+00:00. (`chg-9649`)
- A configuration change for upi-gateway updating routing handles for @okbank to partner-bank-api /v3/collect occurred on 2026-10-07 at 14:06:00+00:00. (`chg-9824`)

## Assumptions (not proven)

- The partner-bank-api service does not support /v3/collect or expects a different path for collect requests.

## Evidence gaps

- none

## Timeline

- 14:05 A deploy for payments-api v2.15.0 occurred. (`chg-9649`)
- 14:06 A configuration change for upi-gateway updated routing handles for @okbank to partner-bank-api /v3/collect. (`chg-9824`)
- 14:07 The error rate anomaly for payments-api and upi-gateway began. (`metric:payments-api:error_rate_pct`)
- 14:07 upi-gateway logs report partner-bank-api POST /v3/collect returned 404 Not Found for handle 690a8@okbank. (`log-00788`)
- 14:07 payments-api logs report UPI collect failed due to upi-gateway error U30 (route failure). (`log-00790`)

## Recommended actions

- **immediate**: Rollback the upi-gateway routing table configuration change to revert @okbank handles back to /v2/collect or the correct active endpoint path.. The incident was directly triggered by the configuration change pointing @okbank handles to a non-existent endpoint path (/v3/collect), causing HTTP 404 errors and transaction failures. (`chg-9824`, `log-00788`, `log-00790`)
- **short_term**: Verify partner-bank-api documentation and test endpoint paths before applying future gateway routing updates.. Ensuring pre-deployment validation of upstream/third-party API paths prevents mismatch issues. (`chg-9824`, `log-00788`)
- **long_term**: Implement automated validation checks in the upi-gateway routing configuration pipeline to catch invalid or unverified downstream endpoints.. Automation reduces human error during manual or programmatic routing updates. (`chg-9824`)
