# INC-06: Portfolio screen failing, logs clean

**Verdict:** root cause identified

An incident occurred where about 30% of portfolio screen loads failed starting at 13:43 on 2026-10-09. The root cause was identified as memory exhaustion in portfolio-service due to the deployment of version v3.8.0 (chg-7001), which introduced in-memory per-user holdings snapshots. This caused memory usage to steadily climb starting at 12:53, reach full saturation at 13:44, and trigger container OOM kills and pod restarts starting at 13:42. Consequently, portfolio-service and mobile-bff experienced connection resets and error rate spikes starting at 13:43.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 1 · tool calls: 8 · LLM calls: 12 · tokens: 70329 · latency: 37.42s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Portfolio-service Memory Exhaustion via v3.8.0 Snapshot Feature | portfolio-service | resource_exhaustion | 0.95 | `chg-7001` Deployed portfolio-service v3.8.0 which explicitly stores per-user holdings snapshots in memory.<br>`metric:portfolio-service:mem_pct` Shows memory usage starting an upward climb at 12:53 and reaching saturation (106.64%) just before the incident.<br>`metric:portfolio-service:pod_restarts` Pod restarts began at 13:42, right before the error spike.<br>`metric:portfolio-service:error_rate_pct` Error rate spiked sharply starting at 13:43.<br>`log-00645` mobile-bff logged upstream connection reset errors calling portfolio-service starting at 13:43. | `metric:portfolio-service:latency_p99_ms` p99 latency remained flat without significant anomaly during the window, though failing/restarting pods drop requests rather than hanging. |
| 2 | Portfolio-db v1.1.0 Release Causes Blocking and Memory Pressure | portfolio-db | bad_deploy | 0.10 | `chg-9271` portfolio-db was deployed with v1.1.0 shortly before the incident onset.<br>`metric:portfolio-service:mem_pct` portfolio-service memory saturation occurred after the database deploy.<br>`metric:portfolio-service:error_rate_pct` portfolio-service error rate rose sharply after the database update. | `metric:portfolio-service:latency_p99_ms` p99 latency did not show an increase as would typically be expected from database blocking or slow queries.<br>`metric:portfolio-service:cpu_pct` CPU utilization remained completely normal and flat, inconsistent with heavy database serialization or query parsing overhead. |

## Facts (evidence-backed)

- portfolio-service was deployed with v3.8.0 keeping per-user holdings snapshots in memory on 2026-10-08T18:20:00+00:00. (`chg-7001`)
- portfolio-db was deployed with v1.1.0 on 2026-10-09T12:27:00+00:00. (`chg-9271`)
- portfolio-service memory percentage showed an anomaly starting upward from 12:53, reaching a peak of 106.64% at 13:44 and becoming saturated. (`metric:portfolio-service:mem_pct`)
- portfolio-service pod restarts began upward from 13:42, reaching a peak of 2.09 restarts/min at 13:46. (`metric:portfolio-service:pod_restarts`)
- portfolio-service error rate spiked starting at 2026-10-09T13:43:00+00:00, reaching a peak of 32.73%. (`metric:portfolio-service:error_rate_pct`)
- mobile-bff error rate increased starting at 2026-10-09T13:43:00+00:00, reaching a peak of 10.23%. (`metric:mobile-bff:error_rate_pct`)
- mobile-bff logged upstream portfolio-service connection reset errors starting at 2026-10-09T13:43:00+00:00. (`log-00645`, `log-01080`)
- mobile-bff calls portfolio-service synchronously. (`dep:mobile-bff->portfolio-service`)

## Assumptions (not proven)

- The in-memory holdings snapshots accumulate without proper eviction or are large enough under normal production loads to exceed container memory limits.

## Evidence gaps

- none

## Timeline

- 18:20 portfolio-service v3.8.0 deployed keeping per-user holdings snapshots in memory. (`chg-7001`)
- 12:27 portfolio-db v1.1.0 deployed. (`chg-9271`)
- 12:53 portfolio-service memory percentage begins upward climb from baseline 75.09%. (`metric:portfolio-service:mem_pct`)
- 13:42 portfolio-service pod restarts begin. (`metric:portfolio-service:pod_restarts`)
- 13:43 portfolio-service and mobile-bff error rates spike; mobile-bff logs upstream connection resets to portfolio-service. (`metric:portfolio-service:error_rate_pct`)
- 13:44 portfolio-service memory saturation peaks at 106.64%. (`metric:portfolio-service:mem_pct`)

## Recommended actions

- **immediate**: Roll back portfolio-service to version v3.7.2 to remove the in-memory per-user holdings snapshot feature.. Version v3.8.0 introduced the snapshot storage that directly leads to memory saturation and container OOM kills. (`chg-7001`, `metric:portfolio-service:mem_pct`, `metric:portfolio-service:pod_restarts`)
- **long_term**: Implement a memory limit increase or proper eviction policy for user holdings snapshots if the v3.8.0 feature is to be re-introduced.. Prevents future memory exhaustion and container restarts caused by unmanaged in-memory data growth. (`chg-7001`, `metric:portfolio-service:mem_pct`)
