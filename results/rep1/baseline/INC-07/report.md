# INC-07: Order placement errors

**Verdict:** root cause identified

Push campaign sent to 2.1M users at 13:30 triggered a massive traffic surge that overwhelmed orders-service, exhausting its executor queue and causing error rates to spike.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 12 · LLM calls: 5 · tokens: 47683 · latency: 14.5s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Traffic surge triggered by diwali_sip_offer push campaign overwhelming orders-service capacity | orders-service | traffic_spike | 0.90 | `chg-9674` Push campaign sent at 13:30 to 2.1M users with deep link orders/new-sip.<br>`metric:mobile-bff:rps` mobile-bff traffic jumped immediately after campaign.<br>`metric:orders-service:rps` orders-service traffic spiked from ~120 req/s to over 800 req/s.<br>`metric:orders-service:error_rate_pct` Error rate spiked to over 14% at 13:32.<br>`log-00593` RejectedExecutionException showing executor queue full.<br>`log-00972` Autoscaler reached max replicas (6/6). | - |
| 2 | Downstream broker-api slowness blocking order threads | broker-api | dependency_failure | 0.15 | `dep:orders-service->broker-api` orders-service depends on broker-api synchronously. | `log-00593` Queue full errors point to incoming request volume rather than waiting on downstream connections. |

## Facts (evidence-backed)

- Push campaign 'diwali_sip_offer' was sent to 2.1M users at 2026-10-10T13:30:00+00:00. (`chg-9674`)
- mobile-bff and orders-service request rates spiked starting at 2026-10-10T13:31:00+00:00. (`metric:mobile-bff:rps`, `metric:orders-service:rps`)
- orders-service and mobile-bff error rates began increasing at 2026-10-10T13:32:00+00:00. (`metric:mobile-bff:error_rate_pct`, `metric:orders-service:error_rate_pct`)
- orders-service logged RejectedExecutionException due to order-executor queue full capacity starting at 2026-10-10T13:32:04+00:00. (`log-00593`)
- orders-service reached maximum replicas (6/6) at 2026-10-10T13:50:19+00:00. (`log-00972`)

## Assumptions (not proven)

- The push campaign deep link directed users directly to create new SIPs, causing simultaneous submission spikes.
- The default thread pool and queue limits on orders-service are insufficient for multi-million user campaign bursts.

## Evidence gaps

- Metrics for orders-service initially timed out and required log/dependent metric correlation.
- External vendor metrics for broker-api are limited.

## Timeline

- 13:30 Push campaign 'diwali_sip_offer' sent to 2.1M users (`chg-9674`)
- 13:31 mobile-bff and orders-service traffic (RPS) begins spiking (`metric:mobile-bff:rps`)
- 13:32 Error rates and latencies start rising on orders-service and mobile-bff (`metric:orders-service:error_rate_pct`)
- 13:32 First RejectedExecutionException logged in orders-service (`log-00593`)
- 13:50 orders-service autoscaler reaches max replicas (6/6) (`log-00972`)

## Recommended actions

- **immediate**: Increase horizontal autoscaling limits (max replicas) for orders-service. Service reached max replicas and saturated CPU during the campaign surge. (`log-00972`, `metric:orders-service:cpu_pct`)
- **immediate**: Tune and increase order-executor queue and thread pool capacity. Queue capacity 500 was fully exhausted causing rejections. (`log-00593`)
- **short_term**: Implement rate limiting and staggered push notifications for marketing campaigns. Broadcasting to 2.1M users simultaneously causes unsustainable traffic spikes. (`chg-9674`)
