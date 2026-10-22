# INC-02: Payments stuck in PENDING

**Verdict:** root cause identified

Payments became stuck in PENDING because the ledger database volume ran completely out of disk space, resulting in PostgreSQL write failures ('No space left on device') starting at 13:52 UTC. This caused ledger-service and payments-api to fail database INSERT operations and mark payments for retry.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 2 · tool calls: 10 · LLM calls: 18 · tokens: 113788 · latency: 63.83s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Ledger Database Disk Exhaustion | ledger-db | resource_exhaustion | 0.95 | `metric:ledger-db:disk_used_pct` Shows disk usage upward anomaly starting at 13:19 UTC and saturating at 100.7% at 13:59 UTC.<br>`log-00514` Shows ledger-db warning for disk usage at 96% at 13:22 UTC.<br>`log-00706` Shows explicit PostgreSQL disk full errors starting at 13:52 UTC.<br>`metric:ledger-db:error_rate_pct` Shows ledger-db error rate rising sharply at 13:52 UTC.<br>`log-00704` Shows ledger-service logging PSQLException 'No space left on device' during INSERT operations starting at 13:52 UTC.<br>`metric:ledger-service:error_rate_pct` Shows ledger-service error rate spiking at 13:52 UTC.<br>`log-00735` Shows payments-api marking payments as PENDING for retry starting at 13:53 UTC due to ledger write failures. | - |
| 2 | KYC Service Deployment Interference | kyc-service | bad_deploy | 0.02 | `chg-9369` Shows kyc-service was deployed at 14:00 UTC, aligning with the reported timing in the incident summary. | `log-00706` Ledger-db disk exhaustion and write errors started at 13:52 UTC, which is 8 minutes before the kyc-service deployment.<br>`log-00704` Ledger-service disk errors started at 13:52 UTC.<br>`metric:ledger-service:error_rate_pct` Ledger-service error rates started rising at 13:52 UTC.<br>`metric:payments-api:error_rate_pct` Payments-api error rates started rising at 13:53 UTC. |

## Facts (evidence-backed)

- Ledger-db disk_used_pct showed an upward anomaly starting at 2026-10-03T13:19:00+00:00 and reached a saturated peak of 100.7% at 13:59:00+00:00. (`metric:ledger-db:disk_used_pct`)
- Ledger-db logged warning for disk usage at 96% starting at 2026-10-03T13:22:49+00:00. (`log-00514`)
- Ledger-service error rate and latency anomalies started at 2026-10-03T13:52:00+00:00. (`metric:ledger-service:error_rate_pct`, `metric:ledger-service:latency_p99_ms`)
- Ledger-service logged disk full errors during INSERT operations starting at 2026-10-03T13:52:00+00:00. (`log-00704`)
- Ledger-db error_rate_pct increased sharply from its baseline of 0.05% starting at 2026-10-03T13:52:00+00:00. (`metric:ledger-db:error_rate_pct`)
- Ledger-db logged database extension errors (No space left on device) starting at 2026-10-03T13:52:08+00:00. (`log-00706`)
- Payments-api error rates started rising at 2026-10-03T13:53:00+00:00. (`metric:payments-api:error_rate_pct`)
- Payments-api began logging ledger write failures and marking payments as PENDING for retry at 2026-10-03T13:53:03+00:00. (`log-00735`)
- Kyc-service was deployed to version v5.2.0 via chg-9369 at 2026-10-03T14:00:00+00:00. (`chg-9369`)

## Assumptions (not proven)

- The underlying storage volume reached maximum capacity due to natural data accumulation or database growth without an explicit prior administrative failure log.
- The timestamps of ledger-db and ledger-service errors occurring 8 minutes prior to the deploy are coincidental.

## Evidence gaps

- none

## Timeline

- 13:19 Ledger-db disk usage upward anomaly begins (`metric:ledger-db:disk_used_pct`)
- 13:22 Ledger-db logs warning for disk usage at 96% (`log-00514`)
- 13:52 Ledger-service and ledger-db begin experiencing disk full write errors and error rate spikes (`log-00704`)
- 13:53 Payments-api error rate rises and payments are marked PENDING for retry (`metric:payments-api:error_rate_pct`)
- 13:59 Ledger-db disk usage reaches saturated peak of 100.7% (`metric:ledger-db:disk_used_pct`)
- 14:00 kyc-service deployed to version v5.2.0 (`chg-9369`)

## Recommended actions

- **immediate**: Immediately expand the storage volume backing ledger-db to restore write operations.. Ledger-db is completely out of disk space (100.7%), causing database write failures and leaving payments stuck in PENDING. (`metric:ledger-db:disk_used_pct`, `log-00706`)
- **short_term**: Implement automated recovery mechanisms and retry processing for payments stuck in PENDING once ledger-db storage is expanded.. Hundreds of payments were marked as PENDING for retry due to ledger write failures and will need reconciliation. (`log-00735`)
- **long_term**: Set up proactive storage utilization alerts and automated volume scaling for ledger-db before disk usage reaches critical thresholds like 90%.. Disk usage warnings at 96% were logged well before complete saturation, indicating a need for better capacity monitoring and early alerting. (`log-00514`, `metric:ledger-db:disk_used_pct`)
