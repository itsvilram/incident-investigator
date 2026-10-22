# INC-02: Payments stuck in PENDING

**Verdict:** root cause identified

Payments became stuck in PENDING because ledger-db ran out of disk space, reaching 100% saturation at 13:59 UTC (with initial anomalies starting at 13:19 UTC). This caused PostgreSQL to throw 'No space left on device' errors on insert statements starting at 13:52 UTC, leading to ledger-service and payments-api write failures and subsequent retries.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 2 · tool calls: 16 · LLM calls: 20 · tokens: 123130 · latency: 77.72s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Ledger Database Storage Exhaustion | ledger-db | resource_exhaustion | 0.95 | `metric:ledger-db:disk_used_pct` Shows disk usage anomaly starting at 13:19 UTC, reaching 100% saturation at 13:59 UTC.<br>`log-00706` Shows ledger-db logging 'could not extend file... No space left on device' starting at 13:52:08 UTC.<br>`metric:ledger-service:error_rate_pct` Shows error rate spiking sharply starting at 13:52 UTC.<br>`metric:ledger-service:latency_p99_ms` Shows p99 latency spiking starting at 13:52 UTC.<br>`log-00704` Logs PostgreSQL storage exhaustion during ledger inserts starting at 13:52 UTC.<br>`metric:payments-api:error_rate_pct` Shows payments-api error rate rising starting at 13:53 UTC.<br>`log-00735` Shows payments-api failing ledger writes and marking payments as PENDING starting at 13:53 UTC.<br>`dep:ledger-service->ledger-db` Establishes dependency of ledger-service on ledger-db. | - |
| 2 | KYC Service Deployment Triggering Downstream Database Bloat | kyc-service | bad_deploy | 0.02 | `chg-9369` kyc-service deployed right around the reported time payments got stuck. | `metric:ledger-db:disk_used_pct` Disk usage anomaly on ledger-db started at 13:19, and disk saturation/write errors started at 13:52, which are prior to the kyc-service deployment at 14:00.<br>`log-00704` Storage exhaustion errors started at 13:52, which is 8 minutes before the kyc-service deployment at 14:00.<br>`metric:ledger-service:error_rate_pct` Ledger-service anomaly started at 13:52, preceding the kyc-service deployment. |

## Facts (evidence-backed)

- ledger-service error rate and p99 latency spiked starting at 2026-10-03T13:52:00+00:00. (`metric:ledger-service:error_rate_pct`, `metric:ledger-service:latency_p99_ms`)
- ledger-service began logging PostgreSQL storage exhaustion errors ('No space left on device') during ledger inserts at 2026-10-03T13:52:00+00:00. (`log-00704`)
- payments-api error rate rose starting at 2026-10-03T13:53:00+00:00. (`metric:payments-api:error_rate_pct`)
- payments-api began failing ledger writes and marking payments as PENDING for retry starting at 2026-10-03T13:53:03+00:00. (`log-00735`)
- payments-api configuration credentials were rotated at 2026-10-03T01:43:00+00:00 (chg-7351). (`chg-7351`)
- market-data-service v1.25.0 routine release occurred at 2026-10-03T12:07:00+00:00 (chg-7687). (`chg-7687`)
- portfolio-service v6.11.0 routine release occurred at 2026-10-03T12:29:00+00:00 (chg-7952). (`chg-7952`)
- kyc-service deployed v5.2.0 (retry Aadhaar e-sign on vendor timeouts) at 2026-10-03T14:00:00+00:00 (chg-9369), matching the reported onset time of payments getting stuck in PENDING. (`chg-9369`)
- metric:ledger-db:disk_used_pct showed an anomaly starting at 13:19 UTC, climbing to 100% saturation at 13:59 UTC. (`metric:ledger-db:disk_used_pct`)
- ledger-db logged 'No space left on device' errors starting at 13:52:08 UTC. (`log-00706`, `log-00704`)

## Assumptions (not proven)

- The underlying storage volume reached its provisioned disk quota due to accumulated transaction logs or data growth over time.

## Evidence gaps

- none

## Timeline

- 01:43 payments-api rotate API credentials (`chg-7351`)
- 12:07 market-data-service v1.25.0 routine release (`chg-7687`)
- 12:29 portfolio-service v6.11.0 routine release (`chg-7952`)
- 13:19 ledger-db disk usage anomaly begins climbing (`metric:ledger-db:disk_used_pct`)
- 13:52 ledger-service error rate and latency spike, logging PostgreSQL storage exhaustion errors (`metric:ledger-service:error_rate_pct`)
- 13:52 ledger-db logs 'No space left on device' errors (`log-00706`)
- 13:53 payments-api error rate rises and starts marking payments as PENDING for retry due to ledger write failures (`metric:payments-api:error_rate_pct`)
- 13:59 ledger-db disk usage reaches 100% saturation (`metric:ledger-db:disk_used_pct`)
- 14:00 kyc-service v5.2.0 deployed (`chg-9369`)

## Recommended actions

- **immediate**: Immediately provision additional storage or free up space on the ledger-db persistent volume to restore database write operations.. ledger-db storage is completely saturated (100.14%), causing write failures and blocking payments. (`metric:ledger-db:disk_used_pct`, `log-00706`)
- **short_term**: Implement automated alerts for ledger-db disk usage when passing 80% and 90% thresholds to catch storage exhaustion early.. Disk anomalies began at 13:19 UTC but went unnoticed until saturation occurred at 13:59 UTC. (`metric:ledger-db:disk_used_pct`)
- **long_term**: Review WAL archiving, transaction log retention policies, and data purging jobs on ledger-db to prevent recurring disk exhaustion.. Past incidents (hist-2026-0722) indicate similar disk filling issues can occur due to stalled WAL archiving or unmanaged data growth. (`hist-2026-0722`, `metric:ledger-db:disk_used_pct`)
