# INC-11: Intermittent notification failures

**Verdict:** root cause identified

At 13:22 UTC, coredns was scaled down from 4 to 1 replica under a cost optimisation change (chg-8542). This reduction in capacity caused severe CPU saturation, high query latency, and error rate spikes starting at 13:23 UTC, followed by UDP read i/o timeout errors at 13:24 UTC. Consequently, notification-service experienced DNS resolution failures (getaddrinfo EAI_AGAIN) starting at 13:25 UTC when attempting to reach external push and SMS vendors, leading to a 25% failure rate in notification deliveries.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 2 · tool calls: 12 · LLM calls: 20 · tokens: 102552 · latency: 90.98s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | CoreDNS replica scale-down causes DNS resolution timeouts for external vendors | coredns | network_dns | 0.95 | `chg-8542` Precedes symptom onset by 3 minutes and directly reduces coredns capacity.<br>`metric:coredns:cpu_pct` Shows coredns CPU saturation starting immediately after scale-down.<br>`metric:coredns:latency_p99_ms` Shows high DNS latency starting at 13:23.<br>`metric:coredns:error_rate_pct` Shows coredns error rate spike starting at 13:23.<br>`log-00525` Coredns logged UDP read i/o timeout errors starting at 13:24.<br>`metric:notification-service:error_rate_pct` Shows the exact onset of the error surge at 13:25 UTC.<br>`log-00531` Indicates DNS getaddrinfo EAI_AGAIN failures for push-provider starting at 13:25 UTC.<br>`log-00533` Indicates DNS getaddrinfo EAI_AGAIN failures for sms-vendor starting at 13:25 UTC.<br>`hist-2026-0228` Past incident confirms coredns configuration/capacity issues cause similar EAI_AGAIN errors across services. | `metric:notification-service:rps` Request rate remained stable, meaning the trigger was structural capacity reduction rather than a traffic spike. |
| 2 | External DNS or upstream resolver timeout coinciding with coredns replica change | sms-vendor | third_party_outage | 0.05 | `log-00531` Shows resolution errors specifically for push-provider.<br>`log-00533` Shows resolution errors specifically for sms-vendor. | `metric:coredns:cpu_pct` Proves internal coredns was severely resource-constrained at the exact same time.<br>`metric:coredns:latency_p99_ms` Proves coredns latency spiked right before the notification errors.<br>`metric:coredns:error_rate_pct` Proves coredns itself was failing queries.<br>`log-00525` Shows coredns experiencing UDP read i/o timeouts.<br>`chg-8542` The tight window after coredns change strongly points to the internal scaling change.<br>`metric:notification-service:error_rate_pct` Simultaneous failure across two completely independent vendors points to a shared local resolver issue. |

## Facts (evidence-backed)

- notification-service depends synchronously on sms-vendor and push-provider, asynchronously on event-bus, and uses coredns for name resolution. (`dep:notification-service->sms-vendor`, `dep:notification-service->push-provider`, `dep:notification-service->event-bus`)
- An infrastructure change chg-8542 scaled coredns replicas from 4 to 1 at 2026-10-14T13:22:00+00:00. (`chg-8542`)
- CoreDNS CPU percentage showed an anomaly starting at 13:23, peaking at 105.92% at 13:46. (`metric:coredns:cpu_pct`)
- CoreDNS latency p99 spiked upwards starting at 13:23, reaching a peak of 2112.52 ms. (`metric:coredns:latency_p99_ms`)
- CoreDNS error rate percentage showed an anomaly starting at 13:23, peaking at 22.72%. (`metric:coredns:error_rate_pct`)
- CoreDNS logged UDP read i/o timeout errors starting at 13:24:03. (`log-00525`)
- notification-service error rate metric spiked to 22.63% at 13:25:00 UTC and peaked at 26.58% (`metric:notification-service:error_rate_pct`)
- notification-service began logging DNS resolution errors for fcm.push-provider.example.com at 13:25:05 UTC (`log-00531`)
- notification-service began logging DNS resolution errors for sms-vendor.example.net at 13:25:10 UTC (`log-00533`)

## Assumptions (not proven)

- Reducing coredns replicas from 4 to 1 left insufficient capacity to handle cluster DNS query load under normal operation.
- Both external vendor DNS records experienced concurrent transient upstream resolution issues completely independent of the internal coredns resource saturation.

## Evidence gaps

- none

## Timeline

- 13:22 CoreDNS replicas scaled from 4 to 1 (cost optimisation) (`chg-8542`)
- 13:23 CoreDNS CPU percentage, latency p99, and error rate anomalies begin (`metric:coredns:cpu_pct`)
- 13:24 CoreDNS logs UDP read i/o timeout errors (`log-00525`)
- 13:25 notification-service error rate spikes to 22.63% (`metric:notification-service:error_rate_pct`)
- 13:25 notification-service logs getaddrinfo EAI_AGAIN for push-provider (`log-00531`)
- 13:25 notification-service logs getaddrinfo EAI_AGAIN for sms-vendor (`log-00533`)

## Recommended actions

- **immediate**: Scale coredns replicas back up from 1 to 4 to restore DNS query handling capacity.. Directly mitigates the resource saturation and DNS lookup failures caused by chg-8542. (`chg-8542`, `metric:coredns:cpu_pct`, `metric:coredns:latency_p99_ms`)
- **long_term**: Review cluster-wide core infrastructure cost-reduction changes and establish minimum replica thresholds.. Prevents similar DNS or shared infrastructure bottlenecks from recurring during resource optimization efforts. (`chg-8542`, `hist-2026-0228`)
