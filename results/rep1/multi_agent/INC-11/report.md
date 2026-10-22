# INC-11: Intermittent notification failures

**Verdict:** root cause identified

CoreDNS experienced an internal CPU saturation and latency spike starting at 13:23 UTC on 2026-10-14, which led to UDP query timeouts for external domains. This directly caused downstream getaddrinfo EAI_AGAIN resolution errors in notification-service beginning at 13:25 UTC, resulting in intermittent notification failures.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 2 · tool calls: 15 · LLM calls: 22 · tokens: 101853 · latency: 61.39s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Cluster CoreDNS service degradation | coredns | network_dns | 0.95 | `metric:coredns:error_rate_pct` Shows coredns error rates started rising at 13:23:00 UTC, directly preceding the notification-service error spike.<br>`metric:coredns:latency_p99_ms` Shows coredns p99 latency spiked from ~3ms to over 2112ms starting at 13:23:00 UTC.<br>`metric:coredns:cpu_pct` Shows coredns CPU utilization spiked past 100% starting at 13:23:00 UTC.<br>`log-00525` Shows coredns logging UDP timeout errors resolving sms-vendor.example.net starting at 13:24:03 UTC.<br>`metric:notification-service:error_rate_pct` Shows the exact onset of the error rate anomaly at 13:25:00 UTC, immediately following coredns degradation.<br>`log-00531` Shows persistent getaddrinfo EAI_AGAIN for push-provider starting at 13:25:05 UTC.<br>`log-00533` Shows persistent getaddrinfo EAI_AGAIN for sms-vendor starting at 13:25:10 UTC.<br>`hist-2026-0228` Past incident confirms prior occurrences of EAI_AGAIN errors across cluster services due to CoreDNS issues. | `metric:coredns:rps` CoreDNS overall RPS showed no major spike or anomaly, staying relatively stable around 3500 req/s. |
| 2 | External vendor nameserver timeouts | sms-vendor | third_party_outage | 0.20 | `log-00525` Shows CoreDNS timing out specifically when querying UDP for sms-vendor.example.net.<br>`log-00533` Shows notification-service failing to resolve sms-vendor.example.net with EAI_AGAIN. | `metric:coredns:cpu_pct` CoreDNS CPU utilization spiked to 105.92%, indicating internal resource contention rather than simple pass-through network packet loss.<br>`metric:coredns:error_rate_pct` CoreDNS errors started internally at 13:23 UTC before vendor-specific queries failed. |

## Facts (evidence-backed)

- CoreDNS latency_p99_ms experienced an anomaly starting at 2026-10-14T13:23:00+00:00, peaking at 2112.52 ms. (`metric:coredns:latency_p99_ms`)
- CoreDNS error_rate_pct experienced an anomaly starting at 2026-10-14T13:23:00+00:00, peaking at 22.72%. (`metric:coredns:error_rate_pct`)
- CoreDNS cpu_pct experienced an anomaly starting at 2026-10-14T13:23:00+00:00, peaking at 105.92%. (`metric:coredns:cpu_pct`)
- CoreDNS logged UDP timeout errors trying to resolve sms-vendor.example.net starting at 2026-10-14T13:24:03+00:00. (`log-00525`)
- Notification-service error_rate_pct shows an anomaly onset at 2026-10-14T13:25:00+00:00, with error rates jumping from a baseline of ~0.27% to a peak of 26.58%. (`metric:notification-service:error_rate_pct`)
- Notification-service logged getaddrinfo EAI_AGAIN errors for fcm.push-provider.example.com starting at 2026-10-14T13:25:05+00:00. (`log-00531`)
- Notification-service logged getaddrinfo EAI_AGAIN errors for sms-vendor.example.net starting at 2026-10-14T13:25:10+00:00. (`log-00533`)

## Assumptions (not proven)

- The CPU spike and query timeouts in CoreDNS were triggered by upstream recursive resolver latency or a burst of specific query patterns that exhausted CoreDNS worker threads.

## Evidence gaps

- search_past_incidents(query=coredns) returned partial data

## Timeline

- 13:23 CoreDNS metrics (error rate, latency p99, and CPU) begin abnormal upward trend. (`metric:coredns:error_rate_pct`)
- 13:24 CoreDNS logs UDP timeout errors resolving sms-vendor.example.net. (`log-00525`)
- 13:25 Notification-service error rate spikes. (`metric:notification-service:error_rate_pct`)
- 13:25 Notification-service logs getaddrinfo EAI_AGAIN for push-provider. (`log-00531`)
- 13:25 Notification-service logs getaddrinfo EAI_AGAIN for sms-vendor. (`log-00533`)

## Recommended actions

- **immediate**: Scale up or restart CoreDNS pods to mitigate CPU saturation and resolve active DNS timeout loops.. CoreDNS CPU utilization exceeded 105% and p99 latency spiked past 2100ms, causing cascading name resolution failures across the cluster. (`metric:coredns:cpu_pct`, `metric:coredns:latency_p99_ms`)
- **short_term**: Implement local caching or negative caching tuning for DNS resolution in notification-service to reduce cluster-wide DNS lookup load.. Past incidents and current logs indicate that DNS resolution dependency issues severely impact outbound service calls. (`hist-2026-0228`, `log-00533`)
- **long_term**: Review CoreDNS resource limits, horizontal autoscaling configurations, and ndots settings cluster-wide.. Prevent future CPU exhaustion and excessive amplification lookups as seen in past similar incidents. (`hist-2026-0228`, `metric:coredns:cpu_pct`)
