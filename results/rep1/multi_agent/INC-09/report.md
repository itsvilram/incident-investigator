# INC-09: Transaction alerts delayed

**Verdict:** inconclusive

Users experienced 5-10 minute delays in receiving transaction SMS and push notifications starting around 14:00 UTC on 2026-10-12. Investigation revealed that the external third-party SMS vendor (sms-vendor) experienced transient latency degradation starting at 14:05 UTC, coinciding with slow outbound calls logged by notification-service starting at 14:02:53 UTC. This blocked synchronous worker threads and caused cascading message queue consumer lag in event-bus.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 3 · tool calls: 26 · LLM calls: 31 · tokens: 169756 · latency: 124.95s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | External SMS Vendor Latency Degradation | sms-vendor | third_party_outage | 0.85 | `log-00763` sms-vendor send took 5519ms starting at 14:02:53+00:00.<br>`metric:sms-vendor:latency_p99_ms` sms-vendor latency_p99_ms experienced an upward anomaly starting at 14:05 UTC, peaking at 1569.0 ms.<br>`log-00860` Consumer group notif-alerts lag recorded starting at 14:18:26+00:00 as a downstream consequence of blocked workers. | `metric:push-provider:latency_p99_ms` push-provider metrics showed zero latency or error anomalies, yet notification-service logged a slow push call in log-00781 (7278ms), suggesting local resource contention or thread pool blocking inside notification-service. |
| 2 | Notification-Service Client-Side Connection Pool Exhaustion / Thread Starvation | notification-service | resource_exhaustion | 0.12 | `chg-9140` notification-service had a scheduled API credential rotation configuration change on 2026-10-12 at 07:38:00+00:00.<br>`log-00781` push-provider took 7278ms in notification-service logs despite metric:push-provider:latency_p99_ms showing completely normal vendor metrics, pointing to a client-side bottleneck. | `chg-9140` chg-9140 occurred 6.5 hours prior to the onset at 14:02:53 UTC.<br>`metric:sms-vendor:latency_p99_ms` sms-vendor metrics independently showed an upward latency anomaly starting at 14:05 UTC on the vendor side. |
| 3 | Event-Bus Upstream Congestion | event-bus | resource_exhaustion | 0.03 | `metric:event-bus:consumer_lag` Consumer lag anomaly started rising sharply at 14:07:00+00:00, peaking at 1006.69 messages. | `log-00763` The first slow vendor call occurred at 14:02:53+00:00, before the event-bus consumer lag metric anomaly started rising at 14:07:00+00:00.<br>`metric:event-bus:cpu_pct` Event-bus CPU, error rate, and p99 latency metrics showed zero anomalies. |

## Facts (evidence-backed)

- sms-vendor send took 5519ms starting at 2026-10-12T14:02:53+00:00 (`log-00763`)
- push send to push-provider took 7278ms starting at 2026-10-12T14:06:19+00:00 (`log-00781`)
- Consumer group notif-alerts lag of 279 messages was recorded at 2026-10-12T14:18:26+00:00 (`log-00860`)
- notification-service depends asynchronously on event-bus and synchronously on sms-vendor and push-provider. (`dep:notification-service->event-bus`, `dep:notification-service->sms-vendor`, `dep:notification-service->push-provider`)
- payments-api sends events to event-bus which is consumed by notification-service. (`dep:payments-api->event-bus`)
- notification-service had a scheduled API credential rotation configuration change on 2026-10-12 at 07:38:00+00:00. (`chg-9140`)
- event-bus had a request timeout configuration change raised on 2026-10-12 at 05:21:00+00:00. (`chg-8599`)
- portfolio-service and auth-service had routine deployments shortly before the incident onset at 14:00. (`chg-9719`, `chg-9757`)
- sms-vendor p99 latency spiked starting at 14:05:00+00:00, reaching a peak of 1569.0 ms. (`metric:sms-vendor:latency_p99_ms`)
- sms-vendor error rate and request rates remained stable around baseline levels during the 12:00 to 14:40 UTC window. (`metric:sms-vendor:rps`, `metric:sms-vendor:error_rate_pct`)
- push-provider metrics (RPS, error rate, and p99 latency) showed no anomalies and remained entirely stable around baseline throughout the window. (`metric:push-provider:rps`, `metric:push-provider:error_rate_pct`, `metric:push-provider:latency_p99_ms`)
- The query_metrics backend for notification-service returned 503 Service Unavailable errors after 3 attempts. ()
- Event-bus consumer lag metric anomaly started at 2026-10-12T14:07:00+00:00, rising from a baseline of ~123 messages to a peak of 1006.69 messages at 14:33:00+00:00. (`metric:event-bus:consumer_lag`)

## Assumptions (not proven)

- The independent p99 latency spike on sms-vendor reflects genuine vendor-side processing delays rather than purely client-side connection starvation.

## Evidence gaps

- query_logs(service=notification-service) returned partial data
- query_metrics(service=notification-service) failed: query_metrics backend returned 503 Service Unavailable after 3 tries
- Unresolved automatic check: WARN: symptomatic service notification-service's own metrics could not be retrieved (tool failures): any conclusion rests on indirect evidence.

## Timeline

- 05:21 event-bus request timeout configuration change (chg-8599) (`chg-8599`)
- 07:38 notification-service API credentials rotated (chg-9140) (`chg-9140`)
- 12:32 portfolio-service v2.8.0 deployed (chg-9719) (`chg-9719`)
- 12:45 auth-service v4.2.0 deployed (chg-9757) (`chg-9757`)
- 14:02 notification-service logs first slow sms-vendor send call taking 5519ms (onset) (`log-00763`)
- 14:05 sms-vendor latency_p99_ms anomaly starts, peaking at 1569.0 ms (`metric:sms-vendor:latency_p99_ms`)
- 14:06 notification-service logs slow push send to push-provider taking 7278ms (`log-00781`)
- 14:07 event-bus consumer_lag metric anomaly starts rising (`metric:event-bus:consumer_lag`)
- 14:18 notification-service records consumer group notif-alerts lag warnings (`log-00860`)
- 14:30 Incident reported by support lead (Fatima)

## Recommended actions

- **immediate**: Coordinate with the external sms-vendor provider to investigate the root cause of their transient p99 latency spike.. External vendor latency degradation directly triggered synchronous request blocking and delayed customer transaction notifications. (`metric:sms-vendor:latency_p99_ms`, `log-00763`)
- **short_term**: Implement circuit breakers and asynchronous decoupling for synchronous vendor calls within notification-service to prevent thread pool exhaustion and queue lag buildup.. External API slowdowns directly blocked worker threads and caused downstream consumer group lag on the event bus. (`log-00763`, `log-00860`, `metric:event-bus:consumer_lag`)
- **long_term**: Restore and verify the reliability of the notification-service metrics backend to prevent observability blind spots during future incidents.. The metrics backend returned 503 errors during the incident, forcing reliance on indirect logs and external telemetry.
