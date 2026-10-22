# INC-06: Portfolio screen failing, logs clean

**Verdict:** root cause identified

Portfolio-service experienced memory exhaustion (OOM kills) due to an unevicted in-memory cache introduced in v3.8.0, causing request failures and error rate spikes in both portfolio-service and mobile-bff.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 7 · LLM calls: 4 · tokens: 46541 · latency: 12.53s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Memory exhaustion via in-memory holdings snapshots | portfolio-service | resource_exhaustion | 0.90 | `chg-7001` Deployed v3.8.0 which keeps per-user holdings snapshots in memory.<br>`metric:portfolio-service:mem_pct` Memory usage climbed steadily and saturated at 106.64%.<br>`log-00664` Kubernetes logged repeated OOMKilled events for portfolio-service pods.<br>`metric:portfolio-service:error_rate_pct` Error rate spiked to ~30% starting around 13:43 UTC.<br>`metric:mobile-bff:error_rate_pct` Mobile BFF error rate spiked similarly due to dependency failure. | - |

## Facts (evidence-backed)

- portfolio-service v3.8.0 was deployed on 2026-10-08 with the summary 'keep per-user holdings snapshots in memory'. (`chg-7001`)
- portfolio-service memory usage hit saturation (106.64%) at 13:44 UTC. (`metric:portfolio-service:mem_pct`)
- Kubernetes logged OOMKilled events for portfolio-service starting at 13:44:35 UTC. (`log-00664`)
- portfolio-service error rates jumped starting at 13:43 UTC. (`metric:portfolio-service:error_rate_pct`)
- mobile-bff error rates jumped starting at 13:43 UTC. (`metric:mobile-bff:error_rate_pct`)

## Assumptions (not proven)

- The in-memory snapshots accumulated without eviction until memory limits were exhausted under load.

## Evidence gaps

- Detailed heap profile per user session in portfolio-service v3.8.0.

## Timeline

- 18:20 portfolio-service v3.8.0 deployed with in-memory snapshots (`chg-7001`)
- 12:53 portfolio-service memory usage starts abnormal upward trend (`metric:portfolio-service:mem_pct`)
- 13:42 portfolio-service pod restarts begin (`metric:portfolio-service:pod_restarts`)
- 13:43 portfolio-service and mobile-bff error rates begin spiking (`metric:portfolio-service:error_rate_pct`)
- 13:44 First OOMKilled event logged for portfolio-service pod (`log-00664`)
- 14:05 Incident reported by on-call SRE Kabir

## Recommended actions

- **immediate**: Roll back portfolio-service to v3.7.2. Removes the in-memory holdings snapshot feature causing memory leaks and OOM kills. (`chg-7001`)
- **short_term**: Implement TTL or eviction policies on in-memory caches before re-deploying. Prevents unbounded memory growth in future releases. (`chg-7001`, `metric:portfolio-service:mem_pct`)
