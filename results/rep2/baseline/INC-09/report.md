# INC-09: Transaction alerts delayed

**Verdict:** root cause identified

External SMS and push notification vendors experienced severe response latencies, causing message processing lag inside notification-service and delaying delivery of user transaction alerts.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 14 · LLM calls: 5 · tokens: 32600 · latency: 14.99s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Third-party vendor latency and throttling | sms-vendor | third_party_outage | 0.85 | `log-00763` Shows slow SMS vendor response of 5519ms starting right after incident onset.<br>`log-00781` Shows slow push provider response of 7278ms.<br>`log-00860` Shows consumer group lag building up in notification-service.<br>`hist-2026-0325` Past incident documents identical symptoms caused by sms-vendor throttling. | - |
| 2 | Internal worker pool processing bottleneck | notification-service | resource_exhaustion | 0.20 | `log-00860` Consumer group notif-alerts lag warnings. | `log-00763` Delays correlate directly with slow external vendor calls rather than internal errors. |

## Facts (evidence-backed)

- Support lead reported transaction alerts arriving 5-10 minutes late since ~14:00. ()
- notification-service logged slow responses from sms-vendor and push-provider up to ~8.8 seconds. (`log-00763`, `log-00769`, `log-00781`, `log-00945`)
- notification-service consumer group notif-alerts experienced message lag up to 382 messages. (`log-00860`, `log-00866`, `log-00890`, `log-00969`)
- Scheduled configuration change chg-9140 occurred on notification-service at 07:38. (`chg-9140`)

## Assumptions (not proven)

- External vendors sms-vendor and push-provider were independently rate-limiting or degraded.
- The 503 error on query_metrics did not conceal any critical internal resource starvation.

## Evidence gaps

- Direct metric telemetry for notification-service was unavailable due to query_metrics backend failure.
- Direct log access for external vendors sms-vendor and push-provider.

## Timeline

- 07:38 notification-service API credentials rotated (`chg-9140`)
- 14:00 Approximate onset of user-reported alert delays
- 14:02 First observed slow sms-vendor response time (`log-00763`)
- 14:06 First observed slow push-provider response time (`log-00781`)
- 14:18 First logged consumer group lag warning (`log-00860`)
- 14:30 Incident INC-09 reported by support lead

## Recommended actions

- **immediate**: Check external vendor status pages and contact SMS/push vendor support regarding rate limits.. Logs indicate slow vendor calls are the primary bottleneck causing consumer lag. (`log-00763`, `log-00781`, `log-00860`)
- **short_term**: Scale up worker concurrency or consumer pool size for notification-service.. Helps drain the message backlog on event-bus faster during vendor slowdowns. (`log-00860`, `log-00866`)
- **long_term**: Implement circuit breakers and fallback routing for third-party notification vendors.. Prevents downstream queue build-up when individual vendors experience latency spikes. (`log-00763`, `log-00781`)
