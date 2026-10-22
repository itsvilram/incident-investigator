# INC-09: Transaction alerts delayed

**Verdict:** root cause identified

Transaction SMS and push alerts were delayed by 5-10 minutes due to latency spikes and degradation in the external sms-vendor service starting around 14:00 UTC, leading to consumer group message backlogs in notification-service.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 12 · LLM calls: 6 · tokens: 35530 · latency: 27.74s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | SMS Vendor Latency Spike / Degradation | sms-vendor | third_party_outage | 0.85 | `metric:sms-vendor:latency_p99_ms` Latency up anomaly detected starting at 14:05 with peak of 1569ms<br>`log-00763` Logs show sms-vendor send taking over 5.5 seconds<br>`log-00769` Logs show sms-vendor send taking over 8.5 seconds<br>`log-00860` Consumer group lag warnings appearing due to slow downstream vendor calls<br>`hist-2026-0325` Past incident shows similar symptom of delayed SMS alerts caused by sms-vendor | - |
| 2 | Scheduled Credential Rotation Side-Effect | notification-service | config_change | 0.25 | `chg-9140` Credential rotation performed earlier in the day on notification-service | `chg-9140` Credential rotation occurred at 07:38, several hours before symptoms began at 14:00 |

## Facts (evidence-backed)

- Users reported payment confirmation SMS/push arriving 5-10 minutes late since ~14:00. ()
- notification-service depends synchronously on sms-vendor and push-provider and asynchronously on event-bus. (`dep:notification-service->sms-vendor`, `dep:notification-service->push-provider`, `dep:notification-service->event-bus`)
- notification-service credentials were rotated at 2026-10-12T07:38:00+00:00. (`chg-9140`)
- sms-vendor p99 latency experienced an anomaly starting at 2026-10-12T14:05:00+00:00 reaching a peak of 1569ms. (`metric:sms-vendor:latency_p99_ms`)
- notification-service logged multiple slow requests to sms-vendor and consumer group lag on notif-alerts. (`log-00763`, `log-00769`, `log-00860`)

## Assumptions (not proven)

- The 5-minute discrepancy between user-reported onset and metric anomaly onset is within normal telemetry reporting bounds.
- Synchronous blocking on sms-vendor caused thread pool saturation and backpressure on the event-bus consumer group.

## Evidence gaps

- notification-service metric query failed with 503 Service Unavailable.
- 2 of 3 log shards timed out, resulting in partial log results.

## Timeline

- 07:38 notification-service rotate API credentials (`chg-9140`)
- 14:00 Users report delayed transaction SMS/push alerts
- 14:02 First slow sms-vendor call logged (`log-00763`)
- 14:05 sms-vendor p99 latency anomaly onset (`metric:sms-vendor:latency_p99_ms`)
- 14:18 Consumer group lag warning logged for notif-alerts (`log-00860`)
- 14:30 Incident reported by support lead Fatima

## Recommended actions

- **immediate**: Engage SMS vendor support to check for gateway congestion or throttling.. External vendor latency is the primary bottleneck causing notification delays. (`metric:sms-vendor:latency_p99_ms`, `log-00763`, `hist-2026-0325`)
- **short_term**: Implement circuit breakers and asynchronous timeout controls for sms-vendor calls.. Prevents slow external vendor calls from blocking notification-service worker pools and causing message queue lag. (`log-00860`, `dep:notification-service->sms-vendor`)
- **long_term**: Establish secondary vendor failover for SMS delivery.. Mitigates future third-party vendor outages and latency spikes. (`hist-2026-0325`)
