# INC-11: Intermittent notification failures

**Verdict:** root cause identified

Notification service experienced intermittent push and SMS sending failures starting at 13:25 UTC due to DNS resolution failures (getaddrinfo EAI_AGAIN), caused by a CoreDNS replica scale-down from 4 to 1 for cost optimisation at 13:22 UTC.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 8 · LLM calls: 4 · tokens: 33639 · latency: 44.32s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | CoreDNS Replicas Scaled Down Causing DNS Resolution Timeouts | coredns | network_dns | 0.95 | `chg-8542` CoreDNS replicas scaled from 4 to 1 at 13:22 UTC, immediately preceding the latency and error spikes.<br>`metric:coredns:latency_p99_ms` CoreDNS p99 latency spiked starting at 13:23 UTC, reaching over 2,112 ms.<br>`metric:coredns:error_rate_pct` CoreDNS error rate jumped starting at 13:23 UTC to ~22%.<br>`metric:coredns:cpu_pct` CoreDNS CPU usage spiked to over 105% immediately after the scale-down.<br>`metric:notification-service:error_rate_pct` Notification service error rate spiked to ~26.58% starting at 13:25 UTC.<br>`log-00531` Logs show continuous getaddrinfo EAI_AGAIN errors resolving fcm.push-provider.example.com starting at 13:25 UTC.<br>`log-00533` Logs show continuous getaddrinfo EAI_AGAIN errors resolving sms-vendor.example.net starting at 13:25 UTC. | - |
| 2 | External Vendor Outages | sms-vendor | third_party_outage | 0.05 | - | `log-00531` Errors are local DNS resolution failures (getaddrinfo EAI_AGAIN), not HTTP or connection failures from successfully resolved vendor endpoints.<br>`chg-8542` The exact timing of failures directly correlates with DNS infrastructure downscaling rather than external vendor incidents. |

## Facts (evidence-backed)

- CoreDNS replicas were scaled down from 4 to 1 at 2026-10-14T13:22:00+00:00. (`chg-8542`)
- CoreDNS latency, CPU usage, and error rate spiked starting at 2026-10-14T13:23:00+00:00. (`metric:coredns:latency_p99_ms`, `metric:coredns:error_rate_pct`, `metric:coredns:cpu_pct`)
- notification-service error rate spiked starting at 2026-10-14T13:25:00+00:00, reaching a peak of 26.58%. (`metric:notification-service:error_rate_pct`)
- notification-service logged getaddrinfo EAI_AGAIN errors for sms-vendor.example.net and fcm.push-provider.example.com starting at 2026-10-14T13:25:00+00:00. (`log-00531`, `log-00533`)

## Assumptions (not proven)

- Reducing CoreDNS replicas from 4 to 1 resulted in severe resource exhaustion and query throttling, causing DNS resolution requests to time out.

## Evidence gaps

- Metrics for other services depending on CoreDNS were not reviewed in detail, although notification-service clearly captures the impact.

## Timeline

- 13:22 CoreDNS replicas scaled from 4 to 1 (`chg-8542`)
- 13:23 CoreDNS latency, error rate, and CPU metrics begin spiking (`metric:coredns:latency_p99_ms`)
- 13:25 notification-service error rate increases and getaddrinfo EAI_AGAIN errors begin (`metric:notification-service:error_rate_pct`)
- 13:50 Incident INC-11 reported by on-call SRE

## Recommended actions

- **immediate**: Scale CoreDNS back up to 4 replicas. Restores cluster DNS capacity, resolves query throttling, and stops notification failures. (`chg-8542`)
- **short_term**: Implement minimum replica limits for platform infrastructure services. Prevents accidental single-replica downscaling of critical shared components like CoreDNS. (`chg-8542`)
