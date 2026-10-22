# H05: Payment confirmations not sent

**Verdict:** root cause identified

Payment confirmations failed due to a breaking schema change in PaymentCompleted events (v3) deployed by payments-api, which caused DeserializationError exceptions and container restarts in notification-service.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 8 · LLM calls: 4 · tokens: 31396 · latency: 13.59s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Schema Mismatch due to payments-api Deployment | payments-api | bad_deploy | 0.92 | `chg-9973` Deployment of payments-api v2.16.0 renamed 'amount' to 'amount_minor' in PaymentCompleted event v3.<br>`log-00790` notification-service began logging DeserializationError for missing required field 'amount' starting immediately after the deploy. | - |
| 2 | March SMS Vendor Outage recurrence | sms-vendor | third_party_outage | 0.10 | - | `log-00790` Telemetry points to internal message deserialization failures rather than external SMS vendor HTTP/connection issues. |

## Facts (evidence-backed)

- payments-api deployed version v2.16.0 at 2026-10-20T14:05:00+00:00, renaming 'amount' to 'amount_minor' in PaymentCompleted event v3. (`chg-9973`)
- notification-service error rate and pod restarts increased starting at 2026-10-20T14:08:00+00:00. (`metric:notification-service:error_rate_pct`, `metric:notification-service:pod_restarts`)
- notification-service logged DeserializationError: PaymentCompleted v3 missing required field 'amount' starting at 2026-10-20T14:08:02+00:00. (`log-00790`)

## Assumptions (not proven)

- The notification-service unhandled deserialization exceptions cause container crashes and subsequent pod restarts.

## Evidence gaps

- None

## Timeline

- 14:05 payments-api deploys version v2.16.0 introducing PaymentCompleted v3 schema changes. (`chg-9973`)
- 14:08 notification-service error rate anomaly and pod restarts begin. (`metric:notification-service:error_rate_pct`)
- 14:08 notification-service records first DeserializationError due to missing 'amount' field. (`log-00790`)
- 14:40 Support lead Fatima reports missing payment confirmations.

## Recommended actions

- **immediate**: Roll back payments-api to version v2.15.0 or patch notification-service to support PaymentCompleted v3 schema.. Stops the deserialization errors and pod restarts immediately. (`chg-9973`, `log-00790`)
- **short_term**: Implement contract testing and strict schema compatibility checks between event producers and consumers.. Prevents breaking schema changes from being deployed independently. (`chg-9973`)
