# H05: Payment confirmations not sent

**Verdict:** root cause identified

Payment confirmations failed due to notification-service encountering deserialization errors starting at 2026-10-20T14:08:00+00:00. This was triggered by the deployment of payments-api v2.16.0 at 14:05, which introduced PaymentCompleted event v3 and renamed the 'amount' field to 'amount_minor'. As notification-service still expected the 'amount' field, it failed to parse the events, causing unhandled exceptions, error rate spikes, and pod restarts.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 2 · tool calls: 15 · LLM calls: 22 · tokens: 97006 · latency: 86.27s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | payments-api v2.16.0 schema change breaks notification-service event deserialization | payments-api | bad_deploy | 0.95 | `chg-9973` payments-api v2.16.0 deployed at 14:05 introduced PaymentCompleted event v3 renaming amount to amount_minor, exactly preceding the 14:08 onset.<br>`metric:notification-service:error_rate_pct` notification-service error rate spikes right after the deploy at 14:08.<br>`metric:notification-service:pod_restarts` notification-service pod restarts begin at 14:08, matching the onset of the deserialization errors.<br>`log-00790` Explicitly shows DeserializationError stating PaymentCompleted v3 missing required field 'amount' starting at 14:08:02.<br>`metric:payments-api:error_rate_pct` payments-api error rate shows no anomaly, confirming the service itself is healthy post-deployment.<br>`metric:payments-api:cpu_pct` payments-api CPU usage remained stable after deployment.<br>`metric:payments-api:mem_pct` payments-api memory usage remained stable after deployment. | - |
| 2 | Third-party SMS vendor outage or push provider failure | sms-vendor | third_party_outage | 0.02 | - | `log-00790` Logs show errors are exclusively DeserializationError for PaymentCompleted v3, with no error logs related to sms-vendor or push-provider. |

## Facts (evidence-backed)

- notification-service error rate metric began increasing at 2026-10-20T14:08:00+00:00, reaching a peak of 69.07%. (`metric:notification-service:error_rate_pct`)
- notification-service pod restarts metric began increasing at 2026-10-20T14:08:00+00:00. (`metric:notification-service:pod_restarts`)
- The first DeserializationError log in notification-service occurred at 2026-10-20T14:08:02+00:00 stating PaymentCompleted v3 missing required field 'amount'. (`log-00790`)
- There are no error logs related to sms-vendor or push-provider in notification-service. (`log-00790`, `log-01486`)
- notification-service depends asynchronously on event-bus, and synchronously on sms-vendor and push-provider. (`dep:notification-service->event-bus`, `dep:notification-service->sms-vendor`, `dep:notification-service->push-provider`)
- payments-api publishes asynchronously to event-bus. (`dep:payments-api->event-bus`)
- There were zero code deployments or config changes for notification-service, sms-vendor, push-provider, event-bus, coredns, or kubernetes over the past 7 days. (`chg-9973`)
- payments-api deployed version v2.16.0 at 2026-10-20T14:05:00+00:00, introducing PaymentCompleted event v3 which renames amount to amount_minor. (`chg-9973`)
- payments-api successfully started v2.16.0 at 14:05:11. (`log-00774`)
- payments-api error rate shows no anomaly, remaining stable around baseline. (`metric:payments-api:error_rate_pct`)
- payments-api CPU, memory, request rate, p99 latency, and pod restarts show no anomalies following the deployment. (`metric:payments-api:rps`, `metric:payments-api:latency_p99_ms`, `metric:payments-api:cpu_pct`, `metric:payments-api:mem_pct`, `metric:payments-api:pod_restarts`)

## Assumptions (not proven)

- notification-service has not yet been updated to support PaymentCompleted v3 event schema.

## Evidence gaps

- none

## Timeline

- 14:05 payments-api v2.16.0 deployed introducing PaymentCompleted event v3 (amount renamed to amount_minor) (`chg-9973`)
- 14:05 payments-api successfully started v2.16.0 (`log-00774`)
- 14:08 notification-service error rate and pod restarts metrics began increasing (`metric:notification-service:error_rate_pct`)
- 14:08 notification-service logs first DeserializationError for PaymentCompleted v3 due to missing 'amount' field (`log-00790`)
- 14:22 notification-service error rate reaches peak of 69.07% (`metric:notification-service:error_rate_pct`)
- 14:44 notification-service pod restarts reaches peak of 2.18 restarts/min (`metric:notification-service:pod_restarts`)

## Recommended actions

- **immediate**: Roll back payments-api to version v2.15.0 or patch notification-service to support PaymentCompleted event v3 schema (handling 'amount_minor').. The schema mismatch between payments-api v2.16.0 and notification-service causes continuous deserialization errors and pod restarts. (`chg-9973`, `log-00790`)
- **long_term**: Implement contract testing or schema validation pipelines between event producers and consumers to prevent breaking changes.. Renaming fields in asynchronous domain events without updating downstream consumer schema expectations caused total failure of notification delivery. (`chg-9973`, `log-00790`)
