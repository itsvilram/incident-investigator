# INC-05: Account linking via AA failing

**Verdict:** root cause identified

Account linking via AA failed due to an expired mTLS client certificate on aa-connector communicating with aa-fiu-gateway.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 6 · LLM calls: 3 · tokens: 22223 · latency: 9.05s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Expired mTLS client certificate on aa-connector | aa-connector | certificate_expiry | 0.95 | `log-00002` Warned that mTLS client certificate expires at 2026-10-08T13:30:00Z<br>`log-00551` Shows SSL handshake with aa-fiu-gateway failed because the certificate expired at 13:30<br>`metric:aa-connector:error_rate_pct` Error rate spiked precisely at 13:30 | - |
| 2 | External vendor gateway certificate or outage | aa-fiu-gateway | third_party_outage | 0.05 | `hist-2026-0907` Past incident involved aa-fiu-gateway issues | `log-00002` Local mTLS client certificate expiration caused the failure rather than a remote vendor cert issue |

## Facts (evidence-backed)

- aa-connector error rate spiked to over 90% starting at 2026-10-08T13:30:00+00:00. (`metric:aa-connector:error_rate_pct`)
- mTLS client certificate CN=aa-connector.orange.internal expired at 2026-10-08T13:30:00Z. (`log-00002`)
- SSL handshakes with aa-fiu-gateway began failing with certificate expired errors immediately following 13:30. (`log-00551`)

## Assumptions (not proven)

- The certificate automation system or secret manager failed to automatically renew the mTLS certificate prior to expiration.

## Evidence gaps

- The exact automated rotation pipeline configuration or logs for the certificate manager were not visible.

## Timeline

- 12:00 mTLS client certificate expiration warning logged. (`log-00002`)
- 13:30 Certificate expires and error rate anomaly begins on aa-connector. (`metric:aa-connector:error_rate_pct`)
- 13:30 SSL handshake with aa-fiu-gateway fails due to expired certificate. (`log-00551`)

## Recommended actions

- **immediate**: Issue and deploy a valid mTLS client certificate for aa-connector.. Required to re-establish secure communication with aa-fiu-gateway and restore account linking. (`log-00551`)
- **short_term**: Audit certificate rotation mechanisms for internal services.. Prevent future unexpected certificate expirations. (`log-00002`)
