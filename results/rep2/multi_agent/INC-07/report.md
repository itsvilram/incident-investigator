# INC-07: Order placement errors

**Verdict:** root cause identified

An order placement incident occurred starting at 13:31 UTC on 2026-10-10, impacting orders-service and mobile-bff with 'Please try again' errors and failed order placements. The root cause is identified as a high-volume push notification campaign ('diwali_sip_offer') sent by notification-service to 2.1 million users at 13:30 with a deep link to 'orders/new-sip'. This campaign triggered a massive, synchronized traffic influx starting at 13:31, overwhelming orders-service's internal executor queue (capacity 500) and causing RejectedExecutionException errors, high CPU utilization, and spiked latencies.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 2 · tool calls: 16 · LLM calls: 22 · tokens: 137289 · latency: 78.2s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Diwali SIP Campaign Push Notification Traffic Surge | notification-service | traffic_spike | 0.95 | `chg-9674` Push campaign sent to 2.1M users at 13:30, precisely preceding the 13:31 traffic surge onset.<br>`log-00577` Notification service logs confirm dispatch of the push campaign at 13:30.<br>`metric:mobile-bff:rps` Shows sudden RPS increase starting at 13:31.<br>`metric:orders-service:rps` Shows sudden RPS increase starting at 13:31, surging from baseline 115 req/s to 748+ req/s.<br>`metric:orders-service:error_rate_pct` Error rate spiked starting at 13:32.<br>`log-00593` orders-service logged RejectedExecutionException due to order-executor queue full starting at 13:32.<br>`metric:notification-service:cpu_pct` Notification-service health metrics retrieved and verified stable during campaign window.<br>`metric:notification-service:mem_pct` Notification-service memory usage verified stable during campaign window.<br>`metric:notification-service:error_rate_pct` Notification-service error rate verified stable during campaign window.<br>`metric:notification-service:latency_p99_ms` Notification-service latency verified stable during campaign window. | - |
| 2 | Broker-API Rate Limiting / Downstream Bottleneck | broker-api | third_party_outage | 0.08 | `log-00200` orders-service previously received 429 Too Many Requests from broker-api. | `log-00200` Broker-API 429 warnings occurred earlier at 12:31, whereas the incident onset and massive RPS surge strictly correlate with the 13:30 push campaign. |

## Facts (evidence-backed)

- notification-service launched the 'diwali_sip_offer' push campaign to 2.1M users with deep link 'orders/new-sip' at 2026-10-10T13:30:00+00:00. (`chg-9674`)
- orders-service experienced an RPS anomaly onset starting at 2026-10-10T13:31:00+00:00, surging from a baseline of ~115 req/s to a peak of 872.67 req/s. (`metric:orders-service:rps`)
- mobile-bff experienced an RPS anomaly starting at 2026-10-10T13:31:00+00:00. (`metric:mobile-bff:rps`)
- orders-service error rate and latency anomalies began at 2026-10-10T13:32:00+00:00, with error rates peaking at 15.85% and p99 latency peaking at 8,999.2 ms. (`metric:orders-service:error_rate_pct`, `metric:orders-service:latency_p99_ms`)
- orders-service started logging RejectedExecutionException due to order-executor queue full (capacity 500) starting at 2026-10-10T13:32:04+00:00. (`log-00593`)
- mobile-bff experienced an error rate anomaly starting at 13:32:00+00:00, peaking at 4.42% error rate. (`metric:mobile-bff:error_rate_pct`)
- orders-service CPU usage spiked up to 106.54% and reached maximum autoscaler replicas (6/6) at 13:50:19. (`metric:orders-service:cpu_pct`, `log-00972`)
- notification-service health metrics (CPU, memory, error rate, p99 latency) showed no anomalies during the push campaign window. (`metric:notification-service:cpu_pct`, `metric:notification-service:mem_pct`, `metric:notification-service:error_rate_pct`, `metric:notification-service:latency_p99_ms`)

## Assumptions (not proven)

- The push notification deep link successfully drove immediate concurrent user sessions that exceeded provisioned orders-service baseline capacity before autoscaling took full effect.

## Evidence gaps

- query_logs(service=orders-service) returned partial data
- query_metrics(service=orders-service) failed: timed out after 0.3s after 3 tries

## Timeline

- 12:31 orders-service received 429 Too Many Requests from broker-api (`log-00200`)
- 13:30 notification-service sent Push campaign 'diwali_sip_offer' to 2.1M users with deep link 'orders/new-sip' (`chg-9674`)
- 13:30 notification-service dispatched initial batch of push campaign (`log-00577`)
- 13:31 orders-service and mobile-bff experienced a sudden surge in RPS (`metric:orders-service:rps`)
- 13:32 orders-service and mobile-bff error rates spiked (`metric:orders-service:error_rate_pct`)
- 13:32 orders-service logged RejectedExecutionException due to order-executor queue full (`log-00593`)
- 13:50 orders-service reached maximum autoscaler replicas (6/6) (`log-00972`)

## Recommended actions

- **immediate**: Implement rate limiting or throttling on inbound traffic originating from bulk push notification deep links to prevent downstream thread pool saturation.. Unrestricted deep link traffic from large-scale campaigns directly caused the thread pool exhaustion and subsequent order placement failures. (`chg-9674`, `log-00593`, `metric:orders-service:rps`)
- **short_term**: Increase the default executor queue capacity and adjust the autoscaling thresholds/policies for orders-service to absorb sudden marketing campaign traffic spikes more smoothly.. orders-service hit its maximum replica limit (6/6) and filled its executor queue (capacity 500), resulting in high error rates. (`log-00593`, `metric:orders-service:cpu_pct`, `log-00972`)
- **long_term**: Establish a coordination and staggering protocol between marketing teams dispatching large push campaigns and platform on-calls to pre-scale target services.. Unannounced high-volume traffic campaigns can bypass normal provisioning windows and cause sudden system degradation. (`chg-9674`)
