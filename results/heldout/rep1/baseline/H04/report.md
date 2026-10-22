# H04: Mobile app users locked out

**Verdict:** root cause identified

Mobile app users experienced widespread failures starting at 13:29 due to an aggressive rate limit config change (chg-9849) on mobile-bff that dropped requests exceeding 100 req/s per IP.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 8 · LLM calls: 4 · tokens: 39395 · latency: 14.18s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Edge rate limit config change too aggressive | mobile-bff | config_change | 0.92 | `chg-9849` Config change at 13:28 tightened per-client-IP rate limit from 1000 to 100.<br>`metric:mobile-bff:error_rate_pct` Error rate anomaly started at 13:29 and peaked at ~30%.<br>`log-00575` Logs started showing rate limit exceeded for client IPs right after the change. | - |
| 2 | auth-service deployment failure | auth-service | bad_deploy | 0.08 | `chg-9803` auth-service was deployed at 13:00. | `metric:auth-service:error_rate_pct` auth-service error rate remained stable and low after deploy. |

## Facts (evidence-backed)

- mobile-bff error rate anomaly started at 2026-10-19T13:29:00+00:00 (`metric:mobile-bff:error_rate_pct`)
- Edge rate limit per_ip_rps was changed from 1000 to 100 at 2026-10-19T13:28:00+00:00 (`chg-9849`)
- auth-service was deployed at 2026-10-19T13:00:00+00:00 (`chg-9803`)

## Assumptions (not proven)

- Mobile app clients aggregate requests behind shared proxy exit IPs, exceeding 100 req/s.

## Evidence gaps

- Exact distribution of mobile client IP addresses and NAT sizes.

## Timeline

- 13:00 auth-service deployed (`chg-9803`)
- 13:28 mobile-bff rate limit tightened (`chg-9849`)
- 13:29 First rate limit exceeded log in mobile-bff (`log-00575`)
- 13:30 mobile-bff error rate jumps to 26.64% (`metric:mobile-bff:error_rate_pct`)

## Recommended actions

- **immediate**: Roll back ratelimit.per_ip_rps on mobile-bff to previous value of 1000. Restores service for mobile clients affected by HTTP 429 errors. (`chg-9849`, `log-00575`)
