# H04: Mobile app users locked out

**Verdict:** root cause identified

Mobile app users experienced lockouts and errors starting at 13:29 due to a configuration change on mobile-bff that lowered the per-client-IP rate limit from 1000 rps to 100 rps. This immediately generated HTTP 429 rate limit exceeded warnings and caused a simultaneous drop in downstream auth-service request volume starting at 13:30.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 1 · tool calls: 10 · LLM calls: 13 · tokens: 78231 · latency: 41.1s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Mobile-bff edge rate limit set too low causing widespread HTTP 429 errors | mobile-bff | config_change | 0.95 | `chg-9849` Tightened the per-client-IP rate limit on mobile-bff at 13:28, exactly one minute before the symptom onset.<br>`metric:mobile-bff:error_rate_pct` Mobile-bff error rate spiked to nearly 30% starting at 13:29.<br>`log-00575` Logs confirm mobile-bff returning HTTP 429 rate limit exceeded warnings for client IPs starting at 13:29:03.<br>`metric:auth-service:rps` Auth-service RPS dropped simultaneously at 13:30 as traffic was blocked upstream. | - |
| 2 | Auth-service v7.2.1 deployment introduced login failures locking out mobile users | auth-service | bad_deploy | 0.02 | `chg-9803` Auth-service was deployed at 13:00 with v7.2.1. | `metric:auth-service:error_rate_pct` Auth-service error rate showed no anomaly during the incident window.<br>`metric:auth-service:latency_p99_ms` Auth-service latency showed no anomaly.<br>`chg-9849` A rate limit configuration change at 13:28 on mobile-bff provides a direct, time-correlated explanation for the error spike starting at 13:29. |

## Facts (evidence-backed)

- mobile-bff error rate anomaly began at 13:29, peaking at 29.99% at 13:39 (`metric:mobile-bff:error_rate_pct`)
- mobile-bff logged rate limit exceeded warnings returning HTTP 429 starting at 13:29:03 with log-00575 (`log-00575`)
- auth-service request throughput (rps) dropped anomaly began at 13:30, falling from a baseline of ~134 req/s to ~85 req/s (`metric:auth-service:rps`)
- auth-service was deployed at 2026-10-19T13:00:00+00:00 (v7.2.1: OTP SMS template copy) (`chg-9803`)
- mobile-bff had an edge rate limit configuration change at 2026-10-19T13:28:00+00:00, tightening the per-client-IP limit from 1000 to 100 rps (`chg-9849`)

## Assumptions (not proven)

- Normal mobile app client connection patterns generate aggregate request rates per IP exceeding 100 rps.

## Evidence gaps

- none

## Timeline

- 13:00 auth-service deployed v7.2.1 (`chg-9803`)
- 13:28 mobile-bff edge rate limit tightened from 1000 to 100 rps per client IP (`chg-9849`)
- 13:29 mobile-bff error rate anomaly begins and HTTP 429 rate limit errors start (`metric:mobile-bff:error_rate_pct`)
- 13:29 mobile-bff logs rate limit exceeded warning returning HTTP 429 (`log-00575`)
- 13:30 auth-service request throughput (rps) drops (`metric:auth-service:rps`)

## Recommended actions

- **immediate**: Immediate rollback or adjustment of the mobile-bff edge rate limit configuration back to 1000 rps or an appropriate higher threshold.. Configuration change chg-9849 directly caused the HTTP 429 rate limit errors and customer lockouts starting at 13:29. (`chg-9849`, `metric:mobile-bff:error_rate_pct`, `log-00575`)
- **long_term**: Review configuration change management processes for edge rate limits to prevent abrupt, unvalidated tightening.. Prevents similar widespread client-facing outages caused by overly restrictive gateway rate limits. (`chg-9849`)
