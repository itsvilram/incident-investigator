# INC-10: Login failures, OTP not received

**Verdict:** root cause identified

Login failures and OTP not received issues started at 2026-10-13T13:40:00+00:00 because the external dependency otp-provider began returning 503 Service Unavailable errors and experiencing high latency. This caused synchronous authentication requests to fail in auth-service, which cascaded into error rate increases in mobile-bff.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 2 · tool calls: 11 · LLM calls: 19 · tokens: 103898 · latency: 71.73s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | External Third-Party Outage: otp-provider Service Degradation | otp-provider | third_party_outage | 0.95 | `metric:auth-service:error_rate_pct` auth-service error rate spiked sharply from 0.33% to ~33.65% starting precisely at 13:40.<br>`metric:otp-provider:error_rate_pct` otp-provider error rate spiked from baseline 0.3% to a peak of 80.04% at 13:52, starting precisely at 13:40.<br>`metric:otp-provider:latency_p99_ms` otp-provider p99 latency jumped from 907.65 ms to 5495.16 ms starting at 13:40.<br>`log-00604` auth-service logs explicitly show OTP send failures because otp-provider responded with 503 Service Unavailable starting at 13:40:13.<br>`metric:mobile-bff:error_rate_pct` mobile-bff error rate increased starting at 13:41 due to its synchronous dependency on auth-service. | `metric:otp-provider:rps` otp-provider request rate remained completely stable with no traffic surges or volume anomalies during the incident window. |
| 2 | Auth-Service v7.1.3 Deployment Bug / Integration Interaction | auth-service | bad_deploy | 0.05 | `chg-9363` auth-service v7.1.3 was deployed 35 minutes prior to the onset at 13:05 with changes to limit OTP resends to 3 per 10 minutes.<br>`log-00660` auth-service logged that OTP resend limits were reached starting at 13:42. | `log-00604` The primary error is an explicit 503 Service Unavailable returned by otp-provider, and otp-provider metrics independently confirm severe vendor-side degradation starting at the exact same minute (13:40). |

## Facts (evidence-backed)

- auth-service error rate spiked to 34.07% starting at 2026-10-13T13:40:00+00:00. (`metric:auth-service:error_rate_pct`)
- mobile-bff error rate increased to 3.98% starting at 2026-10-13T13:41:00+00:00. (`metric:mobile-bff:error_rate_pct`)
- auth-service logs show repeated OTP send failures because otp-provider responded with 503 Service Unavailable, first seen at 2026-10-13T13:40:13+00:00. (`log-00604`)
- auth-service depends synchronously on otp-provider, user-db, and redis-session. (`dep:auth-service->otp-provider`, `dep:auth-service->user-db`, `dep:auth-service->redis-session`)
- mobile-bff depends on auth-service. (`dep:mobile-bff->auth-service`)
- auth-service was deployed at 2026-10-13T13:05:00+00:00 with summary auth-service v7.1.3: limit OTP resends to 3 per 10 minutes. (`chg-9363`)
- otp-provider error rate spiked starting at 13:40, going from a baseline of 0.3% to a peak of 80.04% at 13:52. (`metric:otp-provider:error_rate_pct`)
- otp-provider p99 latency spiked starting at 13:40, going from a baseline of 907.65 ms to a peak of 5495.16 ms at 13:56. (`metric:otp-provider:latency_p99_ms`)
- otp-provider request rate remained stable with no traffic anomalies during the incident window. (`metric:otp-provider:rps`)

## Assumptions (not proven)

- The external vendor (otp-provider) experienced internal infrastructure or capacity failures starting at 13:40 independent of client traffic volume.

## Evidence gaps

- none

## Timeline

- 13:05 auth-service v7.1.3 deployed, limiting OTP resends to 3 per 10 minutes (`chg-9363`)
- 13:40 otp-provider error rate and p99 latency spike; auth-service error rate spikes (`metric:otp-provider:error_rate_pct`)
- 13:40 auth-service logs first OTP send failure due to otp-provider 503 Service Unavailable response (`log-00604`)
- 13:41 mobile-bff error rate increases due to upstream auth-service dependency failures (`metric:mobile-bff:error_rate_pct`)
- 13:42 auth-service logs that OTP resend limit reached for user (`log-00660`)

## Recommended actions

- **immediate**: Contact the external otp-provider vendor support to report the 503 Service Unavailable errors and high latency starting at 13:40.. External metrics and logs directly show otp-provider is experiencing a major outage. (`metric:otp-provider:error_rate_pct`, `metric:otp-provider:latency_p99_ms`, `log-00604`)
- **short_term**: Implement fallback routing or secondary SMS/OTP vendor integration within auth-service if available.. Mitigates total login failure impact when the primary external provider becomes unavailable. (`log-00604`, `dep:auth-service->otp-provider`)
- **long_term**: Establish cross-vendor SLA monitoring and automated circuit breakers for external third-party dependencies.. Prevents cascading login failures and improves user feedback transparency during external vendor outages. (`metric:auth-service:error_rate_pct`, `metric:otp-provider:error_rate_pct`)
