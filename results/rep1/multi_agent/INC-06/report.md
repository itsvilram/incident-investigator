# INC-06: Portfolio screen failing, logs clean

**Verdict:** root cause identified

Since ~13:45, about 30% of portfolio screen loads failed. Investigation revealed that portfolio-service experienced memory saturation (99.8% memory usage) and subsequent pod crashes starting at 13:42 due to v3.8.0 deployment (chg-7001), which kept per-user holdings snapshots in memory. This caused portfolio-service to stop producing logs after 13:37 and resulted in upstream connection reset errors for mobile-bff starting at 13:43.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 1 · tool calls: 10 · LLM calls: 12 · tokens: 64016 · latency: 58.07s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Portfolio-service memory exhaustion via in-memory per-user holdings snapshots (v3.8.0) | portfolio-service | resource_exhaustion | 0.95 | `chg-7001` Introduced the in-memory holdings snapshots feature change on portfolio-service.<br>`metric:portfolio-service:mem_pct` Shows portfolio-service memory is fully saturated at 99.8%.<br>`metric:portfolio-service:pod_restarts` Shows portfolio-service pod restarts spiking starting at 13:42.<br>`metric:portfolio-service:error_rate_pct` Shows portfolio-service error rate spiking at 13:43.<br>`log-00645` Shows mobile-bff receiving connection reset errors from portfolio-service starting at 13:43.<br>`log-00608` Explains the clean-logs observation as portfolio-service ceased producing logs entirely after 13:37 during pod restarts. | `metric:portfolio-service:mem_pct` Reported as flat at 99.8% rather than showing a continuous gradual ramp-up leading directly to 13:42. |
| 2 | Portfolio-db v1.1.0 release regression causing connection pool exhaustion or query deadlocks | portfolio-db | bad_deploy | 0.05 | `chg-9271` Routine release deploy on portfolio-db occurred shortly before the incident onset at 12:27 on Oct 9.<br>`metric:portfolio-service:pod_restarts` Matches the timing of portfolio-service crashes following database issues.<br>`log-00645` Upstream connection resets correspond to downstream database dependency failures. | `metric:portfolio-service:mem_pct` Portfolio-service memory is at 99.8% saturation, directly pointing to in-memory caching changes rather than database response anomalies. |

## Facts (evidence-backed)

- portfolio-service error rate anomaly started at 2026-10-09T13:43:00+00:00, peaking at 32.73%. (`metric:portfolio-service:error_rate_pct`)
- portfolio-service pod restarts anomaly started at 2026-10-09T13:42:00+00:00. (`metric:portfolio-service:pod_restarts`)
- mobile-bff error rate anomaly started at 2026-10-09T13:43:00+00:00, peaking at 10.23%. (`metric:mobile-bff:error_rate_pct`)
- mobile-bff logs show recurring upstream connection reset errors from portfolio-service starting at 2026-10-09T13:43:00+00:00. (`log-00645`, `log-01080`)
- portfolio-service produced zero logs after its last entry at 2026-10-09T13:37:38+00:00 during the incident window, explaining the clean-logs observation. (`log-00608`)
- portfolio-service was deployed with v3.8.0 on 2026-10-08T18:20:00+00:00, introducing in-memory per-user holdings snapshots. (`chg-7001`)
- portfolio-db received a routine release deploy (v1.1.0) on 2026-10-09T12:27:00+00:00. (`chg-9271`)
- portfolio-service memory percentage (mem_pct) was at 99.8% (saturated). (`metric:portfolio-service:mem_pct`)

## Assumptions (not proven)

- Memory saturation at 99.8% triggers OOM killer or runtime crash leading to pod restarts and silence when holding cache grows over time.

## Evidence gaps

- none

## Timeline

- 18:20 portfolio-service deployed with v3.8.0 introducing in-memory per-user holdings snapshots (`chg-7001`)
- 12:27 portfolio-db deployed with v1.1.0 routine release (`chg-9271`)
- 13:37 portfolio-service ceased producing logs entirely during pod crashes (`log-00608`)
- 13:42 portfolio-service pod restarts anomaly begins (`metric:portfolio-service:pod_restarts`)
- 13:43 portfolio-service and mobile-bff error rate anomalies begin, and connection reset errors start appearing in mobile-bff logs (`metric:portfolio-service:error_rate_pct`)

## Recommended actions

- **immediate**: Rollback portfolio-service from version v3.8.0 to v3.7.2 to remove the in-memory per-user holdings snapshots feature.. Deployment chg-7001 introduced the in-memory holdings snapshots causing memory saturation and pod restarts. (`chg-7001`, `metric:portfolio-service:mem_pct`, `metric:portfolio-service:pod_restarts`)
- **long_term**: Implement strict memory limits, pagination, or external caching for user holdings snapshots before reintroducing any in-memory caching features in portfolio-service.. Prevents future resource exhaustion and pod crashes caused by unrestricted memory accumulation of user data. (`chg-7001`, `metric:portfolio-service:mem_pct`)
