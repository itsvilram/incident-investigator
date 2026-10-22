# INC-07: Order placement errors

**Verdict:** root cause identified

An incident occurred on 2026-10-10 starting at 13:31 UTC where order placements failed with errors like 'Please try again'. The root cause was determined to be a push notification campaign ('diwali_sip_offer') sent to 2.1M users at 13:30 UTC with a direct deep link to create new SIP orders. This generated an instantaneous surge in user traffic across mobile-bff and orders-service, overwhelming the orders-service executor queue (capacity 500) and leading to RejectedExecutionException errors, high CPU utilization, and transaction failures.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 2 · tool calls: 18 · LLM calls: 20 · tokens: 131312 · latency: 131.12s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Push Notification Campaign Overwhelms Orders Service Queue | orders-service | traffic_spike | 0.95 | `chg-9674` Push campaign 'diwali_sip_offer' sent to 2.1M users at 13:30 UTC with deep link to orders/new-sip directly precedes the traffic surge.<br>`metric:mobile-bff:rps` mobile-bff traffic spiked abruptly starting at 13:31 UTC, rising from baseline 1097 req/s to 2516+ req/s.<br>`metric:orders-service:rps` orders-service traffic surged simultaneously at 13:31 UTC, jumping from baseline 115 req/s to 748+ req/s.<br>`metric:orders-service:cpu_pct` orders-service CPU usage spiked from 27.42% to 89.09% starting at 13:31 UTC.<br>`log-00593` orders-service logged RejectedExecutionException: order-executor queue full starting at 13:32 UTC.<br>`metric:orders-service:error_rate_pct` orders-service error rate spiked to 14.12% starting at 13:32 UTC, correlating with the executor queue saturation.<br>`metric:notification-service:rps` notification-service RPS remained stable without anomalies during the campaign.<br>`metric:notification-service:error_rate_pct` notification-service error rate remained at 0.31% with no errors. | - |
| 2 | Routine Deployment of Market Data Service or User DB Triggered Upstream Instability | market-data-service | bad_deploy | 0.05 | `chg-9148` market-data-service v2.12.0 deployed at 12:39 UTC.<br>`chg-9417` user-db v3.23.0 deployed at 12:40 UTC. | `chg-9674` A 50-minute delay between deployments and the abrupt 13:31 UTC traffic surge without prior anomalies makes a deployment regression far less likely than the direct push campaign trigger.<br>`metric:orders-service:rps` Traffic metrics show an explicit volume spike starting precisely at 13:31 UTC, matching the push notification timing rather than a gradual deployment degradation. |

## Facts (evidence-backed)

- orders-service traffic (RPS) and CPU usage showed an anomaly starting at 2026-10-10T13:31:00+00:00. (`metric:orders-service:rps`, `metric:orders-service:cpu_pct`)
- orders-service error rate and p99 latency anomalies began at 2026-10-10T13:32:00+00:00, with error rates peaking at 15.85%. (`metric:orders-service:error_rate_pct`, `metric:orders-service:latency_p99_ms`)
- orders-service logs show RejectedExecutionException: order-executor queue full (capacity 500) starting at 2026-10-10T13:32:04+00:00. (`log-00593`)
- mobile-bff RPS anomaly started at 2026-10-10T13:31:00+00:00 and error rate anomaly started at 2026-10-10T13:32:00+00:00. (`metric:mobile-bff:rps`, `metric:mobile-bff:error_rate_pct`)
- A push campaign 'diwali_sip_offer' was sent to 2.1M users via notification-service at 13:30 UTC on 2026-10-10. (`chg-9674`)
- notification-service experienced no distress, errors, resource saturation, or latency spikes between 13:30 and 13:35 UTC. (`metric:notification-service:rps`, `metric:notification-service:error_rate_pct`, `metric:notification-service:latency_p99_ms`, `metric:notification-service:cpu_pct`, `metric:notification-service:mem_pct`, `metric:notification-service:pod_restarts`)

## Assumptions (not proven)

- The push notification deep link successfully drove a large synchronized influx of users to open order forms simultaneously.

## Evidence gaps

- query_logs(service=orders-service) returned partial data
- query_metrics(service=orders-service) failed: timed out after 0.3s after 3 tries
- query_logs(service=orders-service, contains=Please try again) returned partial data

## Timeline

- 12:39 market-data-service v2.12.0 deployed (`chg-9148`)
- 12:40 user-db v3.23.0 deployed (`chg-9417`)
- 13:30 Push campaign 'diwali_sip_offer' sent to 2.1M users (`chg-9674`)
- 13:31 mobile-bff and orders-service traffic RPS and CPU anomalies begin (`metric:orders-service:rps`)
- 13:32 orders-service error rate and p99 latency spike, and RejectedExecutionException occurs (`log-00593`)
- 13:50 orders-service autoscaler reaches max replicas (6/6) (`log-00972`)

## Recommended actions

- **immediate**: Implement rate limiting or queue shedding mechanisms on orders-service to handle sudden traffic surges gracefully without throwing execution rejections.. Orders-service executor queue became full (capacity 500) during the notification campaign surge, causing transaction failures. (`log-00593`, `metric:orders-service:cpu_pct`)
- **short_term**: Establish cross-functional coordination and throttling between marketing/notification campaigns and backend service capacity teams.. Uncoordinated broad push notification campaigns with direct deep links caused instantaneous traffic spikes that overwhelmed downstream services. (`chg-9674`, `metric:orders-service:rps`)
- **long_term**: Review and increase baseline resource provisioning or adjust autoscaling parameters for orders-service during high-impact marketing events.. Autoscaler reached max replicas only later in the incident after queue saturation had already impacted users. (`log-00972`, `metric:orders-service:rps`)
