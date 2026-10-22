# INC-09: Transaction alerts delayed

**Verdict:** inconclusive

Transaction alerts were delayed due to an external vendor latency degradation at sms-vendor, which experienced a p99 latency anomaly starting at 14:05 on 2026-10-12. This caused synchronous outbound requests from notification-service to block, backing up asynchronous message consumption from the event-bus and resulting in consumer lag starting at 14:07.

system: multi_agent · stop: budget exhausted: LLM-call limit (30) · rounds: 3 · tool calls: 26 · LLM calls: 31 · tokens: 156702 · latency: 125.05s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | External Vendor Latency Degradation in SMS and Push Providers | sms-vendor | third_party_outage | 0.92 | `log-00763` Shows outbound requests to sms-vendor taking over 5.5 seconds starting at 14:02.<br>`metric:sms-vendor:latency_p99_ms` Confirms sms-vendor p99 latency anomaly starting at 14:05, peaking at 1569.0 ms.<br>`log-00781` Shows outbound requests to push-provider taking over 7.2 seconds starting at 14:06.<br>`metric:event-bus:consumer_lag` Shows consumer lag increasing sharply starting at 14:07, peaking at over 1000 messages.<br>`log-00860` Confirms warning logs for consumer group notif-alerts lag starting at 14:18.<br>`hist-2026-0325` Past incident shares exact symptom and root-cause category of sms-vendor delays. | `metric:sms-vendor:error_rate_pct` sms-vendor error rate showed no anomalous behavior during the window.<br>`metric:sms-vendor:rps` sms-vendor request rate remained stable with no traffic surge. |
| 2 | Notification-Service Internal Resource Bottleneck | notification-service | resource_exhaustion | 0.25 | - | `metric:sms-vendor:latency_p99_ms` sms-vendor experienced its own p99 latency anomaly starting at 14:05, indicating the bottleneck was vendor-side.<br>`log-00763` Outbound call logs show vendor-side latency rather than client-side connection exhaustion. |
| 3 | Notification-Service Credential Rotation Side-Effect | notification-service | config_change | 0.10 | `chg-9140` A config change (credentials rotation) was executed on notification-service earlier in the day at 07:38. | `chg-9140` The time gap between the change at 07:38 and the symptom onset at 14:02 is over 6 hours, with successful operation in between.<br>`log-00139` notification-service successfully processed payment intents and other requests normally hours after the change. |

## Facts (evidence-backed)

- Metrics queries for notification-service failed with a 503 Service Unavailable error. ()
- Event-bus consumer_lag metric showed an upward anomaly starting at 2026-10-12T14:07:00+00:00, peaking at 1006.69 messages at 14:33:00+00:00. (`metric:event-bus:consumer_lag`)
- Event-bus request rate, error rate, p99 latency, and CPU usage remained stable and showed no anomalies. (`metric:event-bus:rps`, `metric:event-bus:error_rate_pct`, `metric:event-bus:latency_p99_ms`, `metric:event-bus:cpu_pct`)
- Notification-service logged slow outbound requests to sms-vendor starting at 2026-10-12T14:02:53+00:00. (`log-00763`)
- Notification-service logged slow outbound requests to push-provider starting at 2026-10-12T14:06:19+00:00. (`log-00781`)
- Notification-service logged consumer group notif-alerts lag warnings starting at 2026-10-12T14:18:26+00:00. (`log-00860`)
- notification-service consumes messages asynchronously from event-bus and makes synchronous calls to sms-vendor and push-provider. (`dep:notification-service->event-bus`, `dep:notification-service->sms-vendor`, `dep:notification-service->push-provider`)
- payments-api produces messages asynchronously to event-bus. (`dep:payments-api->event-bus`)
- notification-service underwent a scheduled API credentials rotation (chg-9140) at 2026-10-12T07:38:00+00:00, prior to the reported symptom onset around 14:00. (`chg-9140`)
- sms-vendor latency_p99_ms experienced an anomaly starting at 2026-10-12T14:05:00+00:00, reaching a peak of 1569.0 ms at that time. (`metric:sms-vendor:latency_p99_ms`)
- sms-vendor request rate and error rate percentage showed no anomalous behavior in the observation window. (`metric:sms-vendor:rps`, `metric:sms-vendor:error_rate_pct`)
- push-provider metrics (rps, error_rate_pct, latency_p99_ms) showed no anomalies throughout the 12:00 to 14:40 window. (`metric:push-provider:rps`, `metric:push-provider:error_rate_pct`, `metric:push-provider:latency_p99_ms`)

## Assumptions (not proven)

- sms-vendor and push-provider suffered internal capacity or routing degradation outside of our platform control.

## Evidence gaps

- query_logs(service=notification-service) returned partial data
- query_metrics(service=notification-service) failed: query_metrics backend returned 503 Service Unavailable after 3 tries
- Unresolved automatic check: WARN: symptomatic service notification-service's own metrics could not be retrieved (tool failures): any conclusion rests on indirect evidence.

## Timeline

- 07:38 notification-service rotated API credentials (scheduled) (`chg-9140`)
- 14:02 Notification-service logged slow outbound requests to sms-vendor (`log-00763`)
- 14:05 sms-vendor latency_p99_ms anomaly started, reaching peak of 1569.0 ms (`metric:sms-vendor:latency_p99_ms`)
- 14:06 Notification-service logged slow send to push-provider (`log-00781`)
- 14:07 Event-bus consumer_lag anomaly started upward trend (`metric:event-bus:consumer_lag`)
- 14:18 Notification-service logged consumer group notif-alerts lag warnings (`log-00860`)
- 14:30 Incident reported by support lead Fatima
- 14:33 Event-bus consumer_lag peaked at 1006.69 messages (`metric:event-bus:consumer_lag`)

## Recommended actions

- **immediate**: Implement asynchronous timeout and circuit breaking on notification-service outbound calls to sms-vendor and push-provider to prevent worker thread blocking and consumer lag propagation.. Synchronous waits on slow external vendor APIs directly block workers and cascade into event-bus consumer lag. (`log-00763`, `log-00781`, `metric:event-bus:consumer_lag`)
- **short_term**: Establish vendor SLA monitoring and alerting for sms-vendor p99 latency spikes.. Early detection of external provider latency degradation will help pinpoint transaction notification delays faster. (`metric:sms-vendor:latency_p99_ms`)
- **long_term**: Investigate and resolve the 503 query failures on the notification-service metrics backend to ensure complete observability during future incidents.. Tool failures and missing direct telemetry forced reliance on indirect evidence during the investigation.
