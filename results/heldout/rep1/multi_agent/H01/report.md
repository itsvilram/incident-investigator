# H01: Logins rejected after OTP

**Verdict:** root cause identified

An infrastructure node pool patch at 13:36:00 UTC updated node pool np-3 and changed time synchronization from chrony to systemd-timesyncd, causing a +99s clock offset on node np-3-a1. This clock skew caused auth-service pods running on that node to reject incoming JWTs due to 'token issued in the future (iat skew)' starting at 13:40:00 UTC, leading to user login failures.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 2 · tool calls: 10 · LLM calls: 18 · tokens: 103007 · latency: 52.56s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Node image update time-sync configuration shift causes clock skew and JWT iat validation failure | kubernetes | network_dns | 0.95 | `chg-9296` Infrastructure update changing time sync method occurred at 13:36:00 UTC, four minutes prior to the incident onset.<br>`log-00607` Kubernetes node log explicitly shows clock offset +99s on node np-3-a1 starting at 13:39:27.<br>`log-00613` auth-service pod on node np-3-a1 explicitly logged JWT validation failure due to iat skew starting at 13:40:09 UTC.<br>`metric:auth-service:error_rate_pct` auth-service error rate spiked sharply from 0.28% to over 30% starting at 13:40:00 UTC.<br>`log-00616` mobile-bff received 401 responses from auth-service starting at 13:40:18 UTC. | - |
| 2 | Delayed bug in auth-service session refresh release triggered by standard time validation | auth-service | bad_deploy | 0.05 | `chg-8214` auth-service was deployed to version v7.2.0 two days prior to the incident.<br>`metric:auth-service:error_rate_pct` auth-service error rate increased dramatically during the incident. | `chg-9296` The incident onset correlates precisely with the time-sync infrastructure change at 13:36:00 UTC rather than the deployment time two days prior. |

## Facts (evidence-backed)

- auth-service error rate spiked from baseline 0.28% to 32.36% at 2026-10-16T13:40:00+00:00. (`metric:auth-service:error_rate_pct`)
- mobile-bff error rate spiked from baseline 0.32% to 5.93% at 2026-10-16T13:40:00+00:00. (`metric:mobile-bff:error_rate_pct`)
- auth-service began logging JWT validation errors due to iat skew starting at 2026-10-16T13:40:09+00:00. (`log-00613`)
- mobile-bff began logging 401 responses from auth-service for POST /v1/session starting at 2026-10-16T13:40:18+00:00. (`log-00616`)
- An infrastructure change on kubernetes node pool np-3 (new node image 2026.10.3, time sync: chrony -> systemd-timesyncd) occurred at 2026-10-16T13:36:00+00:00. (`chg-9296`)
- Kubernetes logs began showing clock synchronization warnings on node np-3-a1 starting at 13:39:27, showing a clock offset of +99s. (`log-00607`)

## Assumptions (not proven)

- The change from chrony to systemd-timesyncd caused an abrupt clock step or drift on node np-3-a1 rather than smooth synchronization.

## Evidence gaps

- none

## Timeline

- 16:00 auth-service was deployed to version v7.2.0 (`chg-8214`)
- 13:36 Infrastructure change on kubernetes node pool np-3 changing time sync from chrony to systemd-timesyncd (`chg-9296`)
- 13:39 Kubernetes node np-3-a1 logs clock offset +99s exceeding threshold (`log-00607`)
- 13:40 auth-service and mobile-bff error rates spike (`metric:auth-service:error_rate_pct`)
- 13:40 auth-service logs JWT validation failure due to iat skew on node np-3-a1 (`log-00613`)
- 13:40 mobile-bff logs 401 response from upstream auth-service (`log-00616`)

## Recommended actions

- **immediate**: Resync or reboot node np-3-a1 to correct the systemd-timesyncd clock drift immediately.. Node np-3-a1 has a +99s clock offset causing active JWT validation failures. (`log-00607`, `log-00613`)
- **short_term**: Roll back or re-configure time-sync settings on node pool np-3 from systemd-timesyncd back to chrony if desynchronization persists.. The clock drift was introduced directly following the node image update and time-sync configuration change. (`chg-9296`, `log-00607`)
- **long_term**: Implement strict pre-release validation for node pool images concerning time synchronization accuracy.. Prevents future infrastructure updates from silently altering time-sync mechanisms and causing cluster-wide authentication failures. (`chg-9296`)
