# INC-10: Login failures, OTP not received

**Verdict:** root cause identified

Login failures and missing OTPs were caused by a third-party outage at otp-provider starting at 13:40 UTC, which returned 503 Service Unavailable errors and elevated latency, cascading into auth-service and mobile-bff error rate spikes.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 2 · tool calls: 13 · LLM calls: 19 · tokens: 112842 · latency: 43.99s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Third-Party OTP Provider Outage | otp-provider | third_party_outage | 0.95 | `metric:otp-provider:error_rate_pct` otp-provider error rate spiked starting at 13:40 UTC, reaching a peak of 80.04%.<br>`metric:otp-provider:latency_p99_ms` otp-provider p99 latency increased starting at 13:40 UTC, peaking at ~5.5s.<br>`log-00604` Shows auth-service receiving 503 Service Unavailable errors from otp-provider starting at 13:40.<br>`metric:auth-service:error_rate_pct` Auth-service error rate sharply spiked starting at 13:40.<br>`metric:mobile-bff:error_rate_pct` Mobile-bff error rate spiked immediately after at 13:41 due to dependency on auth-service. | - |
| 2 | Auth-Service Deployment Regression | auth-service | bad_deploy | 0.05 | `chg-9363` A deployment occurred on auth-service shortly before the incident window at 13:05.<br>`log-00660` Users hit OTP resend limits starting at 13:42, which relates directly to the feature introduced in chg-9363. | `metric:otp-provider:error_rate_pct` otp-provider error rate spiked independently at 13:40, indicating provider-side failure rather than a client-triggered issue.<br>`metric:otp-provider:latency_p99_ms` otp-provider latency degraded significantly starting at 13:40.<br>`log-00604` Explicit 503 Service Unavailable responses indicate server-side vendor unavailability. |

## Facts (evidence-backed)

- auth-service error rate metric spiked starting at 2026-10-13T13:40:00+00:00, reaching a peak of 39.06% error rate. (`metric:auth-service:error_rate_pct`)
- mobile-bff error rate metric spiked starting at 2026-10-13T13:41:00+00:00, reaching 5.36% error rate. (`metric:mobile-bff:error_rate_pct`)
- notification-service showed no error rate or latency anomaly during the incident window. (`metric:notification-service:error_rate_pct`, `metric:notification-service:latency_p99_ms`)
- auth-service logs show frequent 503 Service Unavailable errors from otp-provider beginning at 2026-10-13T13:40:13+00:00. (`log-00604`, `log-01298`)
- auth-service users hit OTP resend limits starting at 2026-10-13T13:42:35+00:00 due to upstream delivery failures. (`log-00660`)
- auth-service was deployed at 2026-10-13T13:05:00+00:00 (chg-9363) with summary 'auth-service v7.1.3: limit OTP resends to 3 per 10 minutes'. (`chg-9363`)
- otp-provider error rate spiked starting at 13:40 UTC, reaching a peak of 80.04% at 13:52 UTC. (`metric:otp-provider:error_rate_pct`)
- otp-provider p99 latency increased starting at 13:40 UTC, reaching a peak of 5495.16 ms at 13:56 UTC. (`metric:otp-provider:latency_p99_ms`)
- otp-provider request rate (rps) remained normal without any anomaly during the incident window. (`metric:otp-provider:rps`)

## Assumptions (not proven)

- The root cause of otp-provider's degradation is internal to the third-party vendor's infrastructure, as request rates (rps) remained normal.

## Evidence gaps

- none

## Timeline

- 13:05 auth-service was deployed with v7.1.3 (limit OTP resends to 3 per 10 minutes) (`chg-9363`)
- 13:40 otp-provider error rate and latency spiked, and auth-service began logging 503 Service Unavailable errors (`metric:otp-provider:error_rate_pct`)
- 13:41 mobile-bff error rate spiked due to dependency on auth-service (`metric:mobile-bff:error_rate_pct`)
- 13:42 auth-service users hit OTP resend limits due to upstream delivery failures (`log-00660`)

## Recommended actions

- **immediate**: Coordinate with the external otp-provider vendor to investigate their infrastructure degradation and recovery status.. The root cause is an external service degradation at otp-provider starting at 13:40 UTC. (`metric:otp-provider:error_rate_pct`, `metric:otp-provider:latency_p99_ms`)
- **short_term**: Implement circuit breakers or fallback notification channels in auth-service to gracefully handle third-party OTP provider outages without exhausting user retry limits.. Failures from the external provider directly caused auth-service to return 503 errors and users to hit resend limits. (`log-00604`, `log-00660`)
- **long_term**: Establish secondary redundant OTP providers for automatic failover during third-party outages.. Single dependency on otp-provider caused a direct service outage impacting a third of all logins. (`dep:auth-service->otp-provider`, `metric:auth-service:error_rate_pct`)
