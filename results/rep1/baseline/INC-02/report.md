# INC-02: Payments stuck in PENDING

**Verdict:** root cause identified

Ledger database storage filled up completely, causing write failures across ledger-service and leaving customer payments stuck in PENDING status in payments-api.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 12 · LLM calls: 4 · tokens: 51639 · latency: 14.16s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | ledger-db ran out of disk space | ledger-db | resource_exhaustion | 0.95 | `log-00641` ledger-db logged that disk usage reached 90%<br>`log-00706` ledger-db began logging could not extend file: No space left on device<br>`log-00704` ledger-service failed to insert ledger entries due to disk exhaustion<br>`log-00735` payments-api failed to write to the ledger and marked payments PENDING for retry<br>`metric:ledger-service:error_rate_pct` Ledger service error rate spiked upward right when disk filled up | - |
| 2 | kyc-service deploy broke payments | kyc-service | bad_deploy | 0.05 | `chg-9369` kyc-service had a deployment at 14:00:00 | `log-00706` Payment and ledger failures started at 13:52, seven minutes before the kyc-service deploy |

## Facts (evidence-backed)

- ledger-db disk usage reached 90% at 13:42:17 (`log-00641`)
- ledger-db experienced disk space exhaustion errors starting at 13:52:08 (`log-00706`)
- ledger-service began failing db insertions with No space left on device errors at 13:52:00 (`log-00704`)
- payments-api failed ledger writes and marked payments PENDING for retry starting at 13:53:03 (`log-00735`)
- kyc-service deployed version 5.2.0 at 14:00:00 (`chg-9369`)

## Assumptions (not proven)

- Past incidents with similar disk exhaustion symptoms point to a systemic lack of WAL retention and disk cleanup automation.

## Evidence gaps

- Exact byte-level database volume growth metrics beyond log alerts were not queried.

## Timeline

- 13:42 ledger-db logs disk usage alert at 90% (`log-00641`)
- 13:52 ledger-service experiences database write failures (`log-00704`)
- 13:52 ledger-db logs disk full errors (`log-00706`)
- 13:53 payments-api marks payments as PENDING due to ledger write failures (`log-00735`)
- 14:00 kyc-service v5.2.0 is deployed (`chg-9369`)
- 14:15 INC-02 reported by payments on-call

## Recommended actions

- **immediate**: Free disk space on ledger-db immediately. Database is out of space causing all ledger writes to fail and payments to remain stuck in PENDING. (`log-00706`, `log-00735`)
- **short_term**: Replay or retry pending payments once ledger storage is restored. Payments marked PENDING need to be successfully processed once db writes resume. (`log-00735`)
- **long_term**: Lower disk alert threshold and implement WAL archiving/pruning. Prevent future storage exhaustion outages similar to past incident hist-2026-0722. (`log-00641`)
