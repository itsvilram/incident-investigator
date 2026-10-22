# INC-06: Portfolio screen failing, logs clean

**Verdict:** root cause identified

Portfolio screen failures since 13:43 are caused by a memory leak in portfolio-service v3.8.0 (chg-7001) which keeps per-user holdings snapshots in memory without proper eviction. This caused memory exhaustion, pod OOMKills, and sidecar log-shipping termination, which explains why application logs appeared clean.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 9 · LLM calls: 5 · tokens: 44123 · latency: 16.7s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Memory leak in portfolio-service v3.8.0 deployment | portfolio-service | bad_deploy | 0.90 | `chg-7001` v3.8.0 introduced in-memory per-user holdings snapshots<br>`metric:portfolio-service:mem_pct` Memory usage saturated to 106.64% at 13:44<br>`metric:portfolio-service:pod_restarts` Pod restarts began rising at 13:42<br>`log-00664` Kubernetes logged multiple OOMKilled events for portfolio-service containers<br>`log-00626` fluent-bit sidecar OOMKilled, explaining why application logs appeared clean/empty | - |
| 2 | Traffic surge overloading portfolio-service | portfolio-service | traffic_spike | 0.05 | - | `metric:portfolio-service:rps` Request rate remained stable without anomalous surge<br>`metric:mobile-bff:rps` Client BFF request rate remained completely normal |

## Facts (evidence-backed)

- portfolio-service v3.8.0 was deployed on 2026-10-08 at 18:20 with summary 'keep per-user holdings snapshots in memory'. (`chg-7001`)
- portfolio-service memory usage hit 106.64% saturation at 13:44. (`metric:portfolio-service:mem_pct`)
- portfolio-service pod restarts began at 13:42. (`metric:portfolio-service:pod_restarts`)
- portfolio-service and mobile-bff error rates spiked starting around 13:40-13:43. (`metric:portfolio-service:error_rate_pct`, `metric:mobile-bff:error_rate_pct`)
- Kubernetes logged portfolio-service pods and fluent-bit being OOMKilled starting at 13:40. (`log-00626`, `log-00664`)

## Assumptions (not proven)

- The holdings snapshots kept in memory lack proper TTL or LRU eviction policies, leading to unbounded growth.
- The lack of application logs was entirely due to the fluent-bit sidecar being OOMKilled.

## Evidence gaps

- Application-level exception stack traces were unavailable due to fluent-bit OOMKill.

## Timeline

- 18:20 portfolio-service v3.8.0 deployed with in-memory per-user holdings snapshots (`chg-7001`)
- 12:53 portfolio-service memory usage begins upward creep (`metric:portfolio-service:mem_pct`)
- 13:40 portfolio-service error rate spikes and fluent-bit sidecar OOMKilled (`metric:portfolio-service:error_rate_pct`)
- 13:42 portfolio-service pod restarts begin (`metric:portfolio-service:pod_restarts`)
- 13:43 mobile-bff error rate spikes due to downstream failures (`metric:mobile-bff:error_rate_pct`)
- 13:44 First container OOMKilled logged for portfolio-service (`log-00664`)
- 14:05 Incident reported by on-call SRE

## Recommended actions

- **immediate**: Roll back portfolio-service to version 3.7.2. Removes the memory leak introduced in v3.8.0 and restores portfolio screen stability. (`chg-7001`, `metric:portfolio-service:error_rate_pct`)
- **immediate**: Restart or adjust fluent-bit sidecar memory limits. Restores log shipping to inspect application logs correctly. (`log-00626`)
- **short_term**: Implement proper cache bounds/eviction or externalize caching to redis-cache. Prevents future container OOMs when holding snapshots in memory. (`chg-7001`, `log-00664`)
