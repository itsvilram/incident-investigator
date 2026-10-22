# INC-05: Account linking via AA failing

**Verdict:** root cause identified

An incident occurred where account linking via the Account Aggregator failed starting at 2026-10-08T13:30:00+00:00. The investigation established that the mTLS client certificate used by aa-connector to authenticate with aa-fiu-gateway expired at that exact timestamp, causing SSL handshakes to fail and error rates to spike on aa-connector and mobile-bff.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 1 · tool calls: 8 · LLM calls: 11 · tokens: 61192 · latency: 34.46s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Expired mTLS Certificate on aa-connector | aa-connector | certificate_expiry | 0.95 | `log-00002` Shows the exact mTLS client certificate expiration time matching the onset.<br>`log-00551` Records SSL handshake failures due to expired certificate starting at 13:30:03.<br>`log-00559` Shows financial information fetch failing for consents due to upstream errors.<br>`metric:aa-connector:error_rate_pct` Error rate spiked sharply at 13:30.<br>`metric:mobile-bff:error_rate_pct` Error rate spiked upward at 13:30 due to synchronous dependency on aa-connector. | - |
| 2 | External aa-fiu-gateway Certificate Trust Store Rejection | aa-fiu-gateway | third_party_outage | 0.05 | `log-00551` SSL handshake failure with external gateway. | `log-00002` Explicitly proves that the local client certificate expired at the exact onset time. |

## Facts (evidence-backed)

- The error rate for aa-connector began rising sharply at 2026-10-08T13:30:00+00:00. (`metric:aa-connector:error_rate_pct`)
- The error rate for mobile-bff spiked upward starting at 2026-10-08T13:30:00+00:00. (`metric:mobile-bff:error_rate_pct`)
- mTLS client certificate CN=aa-connector.orange.internal expired at 2026-10-08T13:30:00Z. (`log-00002`)
- SSL handshake with aa-fiu-gateway failed due to the expired certificate starting at 2026-10-08T13:30:03+00:00. (`log-00551`)
- Financial information fetch failed for consents due to upstream errors. (`log-00559`)
- aa-connector depends synchronously on aa-fiu-gateway and user-db. (`dep:aa-connector->aa-fiu-gateway`, `dep:aa-connector->user-db`)
- mobile-bff depends synchronously on aa-connector, auth-service, payments-api, portfolio-service, orders-service, and kyc-service. (`dep:mobile-bff->aa-connector`, `dep:mobile-bff->auth-service`, `dep:mobile-bff->payments-api`, `dep:mobile-bff->portfolio-service`, `dep:mobile-bff->orders-service`, `dep:mobile-bff->kyc-service`)

## Assumptions (not proven)

- The automated certificate renewal process for aa-connector was either misconfigured or failed to execute prior to expiration.

## Evidence gaps

- none

## Timeline

- 12:00 aa-connector logged that the mTLS client certificate was set to expire in 0 days. (`log-00002`)
- 13:30 Symptom onset: error rate for aa-connector and mobile-bff spiked. (`metric:aa-connector:error_rate_pct`)
- 13:30 aa-connector began logging SSL handshake failures with aa-fiu-gateway due to the expired certificate. (`log-00551`)
- 13:30 Financial information fetch began failing for consents due to upstream errors. (`log-00559`)

## Recommended actions

- **immediate**: Immediately provision and deploy a valid mTLS client certificate for aa-connector to restore secure communication with aa-fiu-gateway.. Directly resolves the expired certificate causing SSL handshake failures and account linking errors. (`log-00002`, `log-00551`)
- **long_term**: Implement monitoring and alerting for mTLS and TLS certificate expirations well in advance of the 0-day warning threshold.. Prevents future outages caused by silently expiring client certificates. (`log-00002`)
