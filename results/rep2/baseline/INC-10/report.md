# INC-10: Login failures, OTP not received

**Verdict:** root cause identified

An incident involving login failures and OTP delivery issues was investigated. Telemetry confirms that error rates on auth-service and mobile-bff spiked starting around 13:40, caused by 503 Service Unavailable responses from the external otp-provider vendor.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 10 · LLM calls: 4 · tokens: 44254 · latency: 11.61s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Upstream vendor outage (otp-provider) | otp-provider | third_party_outage | 0.90 | `metric:auth-service:error_rate_pct` Shows error rate anomaly starting at 13:40:00<br>`metric:mobile-bff:error_rate_pct` Shows error rate anomaly starting at 13:41:00<br>`log-00604` Explicit log showing OTP send failed due to otp-provider 503 response<br>`dep:auth-service->otp-provider` Shows auth-service depends synchronously on otp-provider | - |
| 2 | Bad deployment of auth-service | auth-service | bad_deploy | 0.05 | - | `chg-9363` Deployment occurred at 13:05, whereas the symptom onset was at 13:40, too late to be caused by this deploy<br>`log-00604` Logs point explicitly to external vendor 503 errors rather than internal code errors |

## Facts (evidence-backed)

- auth-service error rate anomaly started at 2026-10-13T13:40:00+00:00 and peaked at 39.06% (`metric:auth-service:error_rate_pct`)
- mobile-bff error rate anomaly started at 2026-10-13T13:41:00+00:00 and peaked at 5.36% (`metric:mobile-bff:error_rate_pct`)
- auth-service logs show otp-provider responding with 503 Service Unavailable starting at 13:40:13 (`log-00604`, `log-01298`)
- auth-service version 7.1.3 was deployed at 2026-10-13T13:05:00+00:00 (`chg-9363`)
- auth-service depends synchronously on otp-provider (`dep:auth-service->otp-provider`)

## Assumptions (not proven)

- The external otp-provider vendor is experiencing an infrastructure outage resulting in HTTP 503 errors.

## Evidence gaps

- No direct internal telemetry or vendor status page data was available for otp-provider.

## Timeline

- 13:05 auth-service v7.1.3 deployed (`chg-9363`)
- 13:40 auth-service error rate anomaly begins (`metric:auth-service:error_rate_pct`)
- 13:40 First recorded OTP send failure due to otp-provider 503 (`log-00604`)
- 13:41 mobile-bff error rate anomaly begins (`metric:mobile-bff:error_rate_pct`)
- 14:00 Incident reported by on-call SRE Priya

## Recommended actions

- **immediate**: Contact otp-provider vendor support team regarding ongoing 503 Service Unavailable errors. External vendor is failing to serve OTP requests, directly causing login failures (`log-00604`)
- **short_term**: Implement a secondary SMS vendor fallback in auth-service. Prevents total login outage when a single external SMS provider fails (`dep:auth-service->otp-provider`)
