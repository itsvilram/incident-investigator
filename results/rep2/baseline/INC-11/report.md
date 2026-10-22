# INC-11: Intermittent notification failures

**Verdict:** root cause identified

CoreDNS replicas were scaled down from 4 to 1 at 13:22, overloading the remaining replica and causing CPU saturation, request timeouts, and widespread DNS resolution failures (EAI_AGAIN) across the cluster, including notification-service calls to SMS and push vendors.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 8 · LLM calls: 4 · tokens: 32906 · latency: 12.11s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | CoreDNS replica scale-down causes DNS resolution failures | coredns | resource_exhaustion | 0.95 | `chg-8542` CoreDNS scaled down from 4 to 1 replicas at 13:22, just before the incident onset.<br>`metric:coredns:cpu_pct` CoreDNS CPU utilization spiked to 105.9% right after the scale-down.<br>`log-00525` CoreDNS logs show plugin/errors timeout querying external vendor endpoints.<br>`log-00533` notification-service logs EAI_AGAIN errors resolving sms-vendor.example.net starting at 13:25.<br>`log-00531` notification-service logs EAI_AGAIN errors resolving fcm.push-provider.example.com starting at 13:25. | - |
| 2 | External vendor outage | sms-vendor | third_party_outage | 0.05 | - | `log-00533` Errors are local DNS resolution failures (EAI_AGAIN) rather than HTTP/transport layer failures from the vendor. |

## Facts (evidence-backed)

- notification-service error rate anomaly started at 2026-10-14T13:25:00+00:00 and peaked at 26.58%. (`metric:notification-service:error_rate_pct`)
- CoreDNS replicas were scaled from 4 to 1 at 2026-10-14T13:22:00+00:00. (`chg-8542`)
- CoreDNS error rate and latency spiked starting at 2026-10-14T13:23:00+00:00. (`metric:coredns:error_rate_pct`, `metric:coredns:latency_p99_ms`)
- notification-service logged EAI_AGAIN errors for sms-vendor and push-provider starting at 13:25. (`log-00531`, `log-00533`)

## Assumptions (not proven)

- The reduction of CoreDNS replicas from 4 to 1 directly caused CPU saturation and packet/timeout drops under normal cluster DNS load.

## Evidence gaps

- none

## Timeline

- 13:22 CoreDNS scaled down from 4 to 1 replicas for cost optimisation (`chg-8542`)
- 13:23 CoreDNS CPU and latency metrics spike (`metric:coredns:cpu_pct`)
- 13:24 CoreDNS logs first UDP timeout error (`log-00525`)
- 13:25 notification-service error rate anomaly begins (`metric:notification-service:error_rate_pct`)
- 13:25 notification-service logs first EAI_AGAIN DNS resolution failure (`log-00531`)

## Recommended actions

- **immediate**: Scale CoreDNS replicas back to at least 4. Restores cluster DNS processing capacity and resolves CPU exhaustion and timeouts. (`chg-8542`, `metric:coredns:cpu_pct`)
- **short_term**: Implement safety thresholds on infrastructure replica count changes. Prevents accidental or unauthorized critical infrastructure scale-down below high availability requirements. (`chg-8542`)
