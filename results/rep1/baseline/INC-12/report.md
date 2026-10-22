# INC-12: UPI payments failing for some users

**Verdict:** root cause identified

An incorrect routing configuration change applied to upi-gateway redirected @okbank handles to an invalid /v3/collect endpoint on partner-bank-api, causing 404 Not Found errors, U30 route failure errors in payments-api, and an 8-10% failure rate in UPI payments.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 7 · LLM calls: 4 · tokens: 42014 · latency: 25.08s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Incorrect routing configuration update in upi-gateway | upi-gateway | config_change | 0.95 | `chg-9824` Routing table change moved @okbank handles to partner-bank-api /v3/collect at 14:06, immediately preceding the anomaly.<br>`metric:upi-gateway:error_rate_pct` Error rate spiked sharply at 14:07, right after the config change.<br>`log-00788` upi-gateway logged partner-bank-api POST /v3/collect returning 404 Not Found starting at 14:07.<br>`log-00790` payments-api logged UPI collect failures due to upi-gateway error U30 (route failure) starting at 14:07. | - |
| 2 | Code deployment in payments-api (v2.15.0) introduced transaction failures | payments-api | bad_deploy | 0.05 | `chg-9649` payments-api v2.15.0 was deployed at 14:05, just before the incident. | `log-00790` Logs show payments-api failed specifically because of upi-gateway error U30, not an internal application error from the new version.<br>`log-00788` Root cause originates downstream in upi-gateway calling partner-bank-api, which is independent of payments-api v2.15.0. |

## Facts (evidence-backed)

- payments-api error rate metric showed an upward anomaly starting at 2026-10-07T14:07:00+00:00, peaking at 8.89%. (`metric:payments-api:error_rate_pct`)
- upi-gateway error rate metric showed an upward anomaly starting at 2026-10-07T14:07:00+00:00, peaking at 10.28%. (`metric:upi-gateway:error_rate_pct`)
- payments-api version 2.15.0 was deployed at 2026-10-07T14:05:00+00:00. (`chg-9649`)
- upi-gateway routing config update moved @okbank handles to partner-bank-api /v3/collect at 2026-10-07T14:06:00+00:00. (`chg-9824`)
- upi-gateway logged partner-bank-api POST /v3/collect returning 404 Not Found for @okbank handles starting at 2026-10-07T14:07:03+00:00. (`log-00788`)
- payments-api logged UPI collect failures with upi-gateway error U30 (route failure) starting at 2026-10-07T14:07:07+00:00. (`log-00790`)

## Assumptions (not proven)

- @okbank users account for approximately 8% of total payment volume, aligning with the observed 8% customer impact and failure rate.
- The partner-bank-api does not implement or support the /v3/collect endpoint for these handles.

## Evidence gaps

- Direct API access logs from external vendor partner-bank-api are unavailable.

## Timeline

- 14:05 payments-api v2.15.0 deployed (`chg-9649`)
- 14:06 upi-gateway routing config updated for @okbank handles to use /v3/collect (`chg-9824`)
- 14:07 Error rate anomaly started on payments-api and upi-gateway (`metric:payments-api:error_rate_pct`)
- 14:07 upi-gateway began logging 404 Not Found errors from partner-bank-api (`log-00788`)
- 14:07 payments-api began logging U30 route failure errors (`log-00790`)
- 14:30 Incident INC-12 reported by on-call

## Recommended actions

- **immediate**: Roll back the upi-gateway routing configuration update to restore @okbank handle routing to /v2/collect.. The config change directly introduced the 404 Not Found errors and resulting payment failures. (`chg-9824`, `log-00788`, `log-00790`)
- **short_term**: Confirm endpoint contracts and support with partner-bank-api before attempting to migrate handles to /v3/collect in the future.. Ensures the external vendor supports the requested URI path before configuration is applied in production. (`chg-9824`, `log-00788`)
- **long_term**: Implement automated validation checks in the routing configuration pipeline to verify upstream endpoint availability.. Prevents similar configuration errors from reaching production unvalidated. (`chg-9824`)
