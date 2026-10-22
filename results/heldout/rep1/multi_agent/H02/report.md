# H02: Payments timing out

**Verdict:** root cause identified

An incident affecting payments and ledger services started at 13:06 on 2026-10-17 when database statement timeouts began occurring due to table lock contention. Specifically, the daily reconciliation cron job on ledger-db acquired a share row exclusive lock on the ledger_entries table at 13:04, blocking incoming transactional inserts and causing widespread active connection pile-ups, latency spikes, and 10-second statement timeouts starting at 13:05/13:06.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 2 · tool calls: 16 · LLM calls: 19 · tokens: 132447 · latency: 79.41s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Daily reconciliation cron job table lock contention on ledger-db | ledger-db | dependency_failure | 0.95 | `log-00400` ledger-db cron job executed LOCK TABLE ledger_entries at 13:04:02, directly preceding the anomaly.<br>`log-00414` Continuous warnings starting at 13:05 for processes waiting for RowExclusiveLock on ledger_entries.<br>`metric:ledger-db:latency_p99_ms` Ledger-db latency spiked upward starting at 13:05.<br>`metric:ledger-db:connections_active` Ledger-db active connections surged starting at 13:05.<br>`log-00445` Ledger-service statements timed out on INSERT INTO ledger_entries starting at 13:06. | - |
| 2 | Payments-api logging configuration change causing thread pool or serialization overhead | payments-api | config_change | 0.02 | `chg-9660` Config change on payments-api at 13:02 setting ledger client logging to DEBUG. | `log-00445` Actual failures are database statement timeouts inside ledger-db and ledger-service, not client-side formatting delays.<br>`log-00400` ledger-db explicitly started its blocking table lock at 13:04, establishing an independent database-side cause. |

## Facts (evidence-backed)

- payments-api error_rate_pct and latency_p99_ms started an upward anomaly at 2026-10-17T13:06:00+00:00. (`metric:payments-api:error_rate_pct`, `metric:payments-api:latency_p99_ms`)
- ledger-service error_rate_pct and latency_p99_ms started an upward anomaly at 2026-10-17T13:06:00+00:00 (and 13:05 for p99 latency). (`metric:ledger-service:error_rate_pct`, `metric:ledger-service:latency_p99_ms`)
- payments-api logs show persistent errors: ledger-service POST /entries timed out after 10s starting at 13:06:02. (`log-00443`, `log-02092`)
- ledger-service logs show persistent statement timeouts: INSERT INTO ledger_entries canceled after 10000 ms starting at 13:06:04. (`log-00445`, `log-02075`)
- At 2026-10-17T13:04:02, ledger-db started a cron job reconcile_daily which executed LOCK TABLE ledger_entries IN SHARE ROW EXCLUSIVE MODE. (`log-00400`)
- Ledger-db latency_p99_ms showed an upward anomaly starting at 13:05, jumping from ~15 ms to a peak of 10527.28 ms. (`metric:ledger-db:latency_p99_ms`)
- Ledger-db active connections showed an upward anomaly starting at 13:05, surging from ~45 to ~180 active connections. (`metric:ledger-db:connections_active`)
- Starting at 13:05, ledger-db logged continuous warnings of processes waiting for RowExclusiveLock on the ledger_entries relation. (`log-00414`, `log-02090`)

## Assumptions (not proven)

- The reconcile_daily cron job holds the table lock for the duration of the reconciliation process, blocking concurrent writes.

## Evidence gaps

- none

## Timeline

- 13:02 payments-api config change chg-9660 applied (logging.ledger_client set to DEBUG) (`chg-9660`)
- 13:04 ledger-db cron job reconcile_daily started with LOCK TABLE ledger_entries IN SHARE ROW EXCLUSIVE MODE (`log-00400`)
- 13:05 ledger-db processes begin waiting for RowExclusiveLock and active connections/latency spike (`log-00414`)
- 13:06 Upstream error and latency anomalies start on payments-api and ledger-service due to database statement timeouts (`log-00445`)

## Recommended actions

- **long_term**: Optimize or reschedule the reconcile_daily cron job on ledger-db to avoid blocking concurrent transactional writes on ledger_entries during peak traffic hours.. The daily cron job acquires a broad table lock that causes cascading statement timeouts and connection pool exhaustion. (`log-00400`, `log-00414`, `metric:ledger-db:connections_active`)
- **short_term**: Implement more granular locking strategies or MVCC-compliant queries for reconciliation tasks.. Prevent exclusive table locks from halting regular INSERT and UPDATE statements on ledger tables. (`log-00400`, `log-00445`)
