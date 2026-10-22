# H01: Logins rejected after OTP

**Verdict:** root cause identified

Logins failed after the OTP step due to JWT validation errors caused by time drift on node pool np-3 following an infrastructure node image update.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 11 · LLM calls: 5 · tokens: 56010 · latency: 25.73s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Node Clock Drift on Node Pool np-3 | kubernetes | network_dns | 0.92 | `chg-9296` Node pool np-3 image updated at 13:36, switching time sync to systemd-timesyncd.<br>`log-00607` Kubernetes logs show clock offset warnings exceeding 5s on node np-3-a1 starting at 13:39:27.<br>`metric:auth-service:error_rate_pct` auth-service error rate spikes at 13:40:00.<br>`log-00613` auth-service error logs show JWT validation failure due to tokens issued in the future (iat skew) on pod auth-service-6f7d-k2x9p on node np-3-a1 starting at 13:40:09. | - |
| 2 | Delayed Bug in auth-service Release v7.2.0 | auth-service | bad_deploy | 0.08 | `chg-8214` auth-service v7.2.0 deployed two days prior. | `log-00613` Errors specifically name clock/iat skew and tie directly to node np-3-a1 rather than code logic. |

## Facts (evidence-backed)

- About a third of logins failed with errors starting at 2026-10-16T13:40:00+00:00 in auth-service and mobile-bff. (`metric:auth-service:error_rate_pct`, `metric:mobile-bff:error_rate_pct`)
- Node pool np-3 image was updated at 2026-10-16T13:36:00+00:00, changing time synchronization from chrony to systemd-timesyncd. (`chg-9296`)
- Kubernetes reported node np-3-a1 clock offset exceeding 5s threshold starting at 2026-10-16T13:39:27+00:00. (`log-00607`)
- auth-service pods running on node np-3-a1 rejected JWTs with token issued in the future starting at 2026-10-16T13:40:09+00:00. (`log-00613`)

## Assumptions (not proven)

- Pods scheduled on other nodes or node pools without clock skew continue to validate tokens successfully, accounting for the ~33% failure rate matching traffic on node np-3-a1.

## Evidence gaps

- Exact pod distribution across node pools to verify whether exactly 1/3 of traffic landed on np-3-a1.

## Timeline

- 16:00 auth-service v7.2.0 deployed (`chg-8214`)
- 13:36 Node pool np-3 node image updated, switching time sync from chrony to systemd-timesyncd (`chg-9296`)
- 13:39 Kubernetes logs first clock offset warning of ~99s on node np-3-a1 (`log-00607`)
- 13:40 auth-service and mobile-bff error rates spike (`metric:auth-service:error_rate_pct`)
- 13:40 auth-service logs first JWT validation failure due to future iat skew on pod auth-service-6f7d-k2x9p (`log-00613`)

## Recommended actions

- **immediate**: Reschedule or restart pods on node np-3-a1 or force systemd-timesyncd resynchronization on node pool np-3. Corrects the ~95s clock offset causing JWT validation failures. (`chg-9296`, `log-00607`, `log-00613`)
- **short_term**: Investigate why systemd-timesyncd failed to synchronize time correctly on node image 2026.10.3. Prevents future regressions during node pool updates. (`chg-9296`)
- **long_term**: Add monitoring and alerts for node clock drift exceeding 5 seconds across all Kubernetes node pools. Ensures rapid detection of time sync failures before customer impact occurs. (`log-00607`)
