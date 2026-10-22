# INC-07: Order placement errors

**Verdict:** root cause identified

The diwali_sip_offer push campaign sent at 13:30 triggered a massive traffic surge that overwhelmed orders-service and mobile-bff, causing executor queue exhaustion, high error rates, and hitting max replica limits.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 11 · LLM calls: 4 · tokens: 39161 · latency: 25.94s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Push Campaign Traffic Overload | orders-service | traffic_spike | 0.90 | `chg-9674` Push campaign sent to 2.1M users at 13:30 with deep link orders/new-sip.<br>`metric:orders-service:rps` RPS anomaly started at 13:31, increasing request rate significantly.<br>`metric:mobile-bff:rps` RPS anomaly started at 13:31, mirroring the traffic surge.<br>`metric:orders-service:error_rate_pct` Error rate spiked starting at 13:32 up to 15.85%.<br>`log-00593` RejectedExecutionException: order-executor queue full starting at 13:32.<br>`log-00972` Autoscaler reached max replicas (6/6).<br>`hist-2026-0901` Past incident with identical symptoms caused by traffic overload and low replica max. | - |
| 2 | Routine Deployment Regression | market-data-service | bad_deploy | 0.10 | `chg-9148` market-data-service v2.12.0 deployed shortly before the incident. | `metric:market-data-service:error_rate_pct` Market data service error rate remained completely flat and normal. |

## Facts (evidence-backed)

- Push campaign 'diwali_sip_offer' was sent to 2.1M users at 2026-10-10T13:30:00+00:00. (`chg-9674`)
- orders-service and mobile-bff request rates surged starting at 2026-10-10T13:31:00+00:00. (`metric:orders-service:rps`, `metric:mobile-bff:rps`)
- orders-service and mobile-bff error rates spiked starting at 2026-10-10T13:32:00+00:00. (`metric:orders-service:error_rate_pct`, `metric:mobile-bff:error_rate_pct`)
- orders-service logged RejectedExecutionException due to full order-executor queue starting at 13:32:04. (`log-00593`)
- orders-service autoscaler reached max replicas (6/6). (`log-00972`)

## Assumptions (not proven)

- The push campaign deep link directed users to initiate SIP orders, heavily concentrating traffic onto orders-service.

## Evidence gaps

- metrics query for orders-service initially timed out before succeeding on retry
- orders-service log query shards experienced partial timeouts, leading to incomplete log counts

## Timeline

- 12:39 market-data-service v2.12.0 deployed (`chg-9148`)
- 12:40 user-db v3.23.0 deployed (`chg-9417`)
- 13:30 Push campaign diwali_sip_offer sent to 2.1M users (`chg-9674`)
- 13:31 orders-service and mobile-bff request rates surge anomaly starts (`metric:orders-service:rps`)
- 13:32 orders-service and mobile-bff error rate anomaly starts (`metric:orders-service:error_rate_pct`)
- 13:32 First RejectedExecutionException logged in orders-service (`log-00593`)
- 13:50 orders-service autoscaler reaches max replicas (`log-00972`)
- 13:55 Incident reported by on-call

## Recommended actions

- **immediate**: Coordinate with growth team to stagger or temporarily pause massive push campaigns. Directly halts the incoming traffic surge causing resource exhaustion. (`chg-9674`)
- **immediate**: Increase maximum replica limits for orders-service and mobile-bff beyond 6 pods. Allows services to scale up and absorb higher traffic volumes. (`log-00972`, `hist-2026-0901`)
- **short_term**: Expand order-executor thread pool capacity and queue size in orders-service. Prevents RejectedExecutionException under high concurrent load. (`log-00593`)
- **long_term**: Establish communication workflows between marketing and SRE prior to launching large campaigns. Ensures proactive capacity provisioning for major product campaigns. (`chg-9674`, `hist-2026-0901`)
