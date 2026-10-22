# INC-02: Payments stuck in PENDING

**Verdict:** root cause identified

Ledger Database ran out of disk space, causing file extension errors during INSERT queries in ledger-service, which in turn caused payments-api to fail ledger writes and leave payments stuck in PENDING status.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 13 · LLM calls: 6 · tokens: 91082 · latency: 21.84s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Ledger Database disk space exhaustion | ledger-db | resource_exhaustion | 0.95 | `metric:ledger-db:disk_used_pct` Shows disk usage reached 100% saturation starting at 13:19<br>`log-00706` Ledger-db reported 'could not extend file' errors starting at 13:52<br>`log-00704` Ledger-service logged PostgreSQL 'No space left on device' errors on insert statements<br>`log-00735` Payments-api failed ledger writes and marked payments as PENDING for retry | - |
| 2 | KYC service deployment regression | kyc-service | bad_deploy | 0.05 | `chg-9369` kyc-service deploy occurred at 14:00 | `metric:payments-api:error_rate_pct` Payment-api errors started at 13:53, before the kyc deploy at 14:00<br>`metric:ledger-service:error_rate_pct` Ledger-service errors started at 13:52, before the kyc deploy at 14:00 |

## Facts (evidence-backed)

- Ledger-db disk usage reached 100% and showed an anomaly starting at 2026-10-03T13:19:00+00:00 (`metric:ledger-db:disk_used_pct`)
- Ledger-service error rate and latency started increasing at 2026-10-03T13:52:00+00:00 (`metric:ledger-service:error_rate_pct`, `metric:ledger-service:latency_p99_ms`)
- Ledger-db logged 'could not extend file' errors starting at 2026-10-03T13:52:08+00:00 (`log-00706`)
- Ledger-service logged PostgreSQL 'No space left on device' errors starting at 2026-10-03T13:52:00+00:00 (`log-00704`)
- Payments-api error rate started increasing at 2026-10-03T13:53:00+00:00 (`metric:payments-api:error_rate_pct`)
- Payments-api logged ledger write failures and marked payments as PENDING for retry starting at 2026-10-03T13:53:03+00:00 (`log-00735`)
- A kyc-service deploy occurred at 2026-10-03T14:00:00+00:00 (`chg-9369`)

## Assumptions (not proven)

- Normal transaction volume and database growth over time naturally filled the storage volume allocated to ledger-db without timely log rotation or scaling.

## Evidence gaps

- Past incident search index was partially degraded, returning only top matches.

## Timeline

- 13:19 Ledger-db disk usage anomaly began rising toward 100% (`metric:ledger-db:disk_used_pct`)
- 13:52 Ledger-service began experiencing error rate and latency anomalies and logging 'No space left on device' errors (`log-00704`)
- 13:52 Ledger-db reported file extension failures due to lack of disk space (`log-00706`)
- 13:53 Payments-api error rate increased and marked payments as PENDING for retry (`log-00735`)
- 14:00 Routine kyc-service deployment occurred (`chg-9369`)
- 14:15 Incident INC-02 officially reported by payments on-call

## Recommended actions

- **immediate**: Provision additional disk space or expand storage volume for ledger-db. Resolves the 'No space left on device' condition allowing database writes to succeed again (`metric:ledger-db:disk_used_pct`, `log-00706`)
- **immediate**: Implement background worker to retry and complete payments stuck in PENDING status. Ensures customer transactions that debited users are properly processed and recorded (`log-00735`)
- **short_term**: Set up critical disk usage alerting on ledger-db. Prevents unexpected disk saturation by warning engineering teams early (`metric:ledger-db:disk_used_pct`)
- **long_term**: Review database retention, cleanup, and storage scaling policies for ledger-db. Ensures sustainable long-term capacity planning (`metric:ledger-db:disk_used_pct`)
