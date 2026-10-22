# INC-05: Account linking via AA failing

**Verdict:** root cause identified

Account linking via Account Aggregator failed starting at 2026-10-08T13:30:00+00:00 due to an expired SSL certificate on the external dependency aa-fiu-gateway, causing 100% failure rates in aa-connector and elevated error rates in mobile-bff.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 2 · tool calls: 12 · LLM calls: 19 · tokens: 119434 · latency: 101.83s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Expired SSL certificate on external aa-fiu-gateway | aa-fiu-gateway | certificate_expiry | 0.95 | `log-00551` Explicitly states SSL handshake failed because the certificate expired at notAfter=2026-10-08T13:30:00Z.<br>`log-00559` Shows FI fetch failed for consents with upstream errors starting at 13:30.<br>`metric:aa-connector:error_rate_pct` Error rate anomaly started precisely at 13:30.<br>`metric:mobile-bff:error_rate_pct` Error rate anomaly started precisely at 13:30 due to synchronous calls to aa-connector. | - |
| 2 | Regression introduced by aa-connector deployment chg-8692 | aa-connector | bad_deploy | 0.05 | `chg-8692` Deploy on aa-connector occurred prior to the incident window. | `log-00551` Log explicitly identifies an expired certificate (notAfter=2026-10-08T13:30:00Z) on the external gateway rather than a software regression. |

## Facts (evidence-backed)

- aa-connector error rate anomaly started at 2026-10-08T13:30:00+00:00 and peaked at 104.34% (`metric:aa-connector:error_rate_pct`)
- aa-connector p99 latency dropped sharply at 2026-10-08T13:30:00+00:00 as requests failed immediately (`metric:aa-connector:latency_p99_ms`)
- mobile-bff error rate anomaly started at 2026-10-08T13:30:00+00:00 (`metric:mobile-bff:error_rate_pct`)
- SSL handshake with aa-fiu-gateway failed because the certificate expired at 2026-10-08T13:30:00Z (`log-00551`)
- FI fetch failed for multiple consents with upstream error starting at 2026-10-08T13:30:23+00:00 (`log-00559`)
- mobile-bff makes a synchronous call to aa-connector (`dep:mobile-bff->aa-connector`)
- aa-connector makes synchronous calls to aa-fiu-gateway and user-db (`dep:aa-connector->aa-fiu-gateway`, `dep:aa-connector->user-db`)
- aa-connector had a deploy (v8.18.8 minor bug fixes) on 2026-10-07T01:22:00+00:00 (`chg-8692`)

## Assumptions (not proven)

- The external partner failed to renew or automate rotation of the aa-fiu-gateway certificate, explaining why internal metrics for aa-fiu-gateway showed normal request counts while connection attempts failed at the TLS handshake layer.

## Evidence gaps

- none

## Timeline

- 01:22 aa-connector deploy v8.18.8 occurred (`chg-8692`)
- 13:30 aa-connector and mobile-bff error rate anomalies begin (`metric:aa-connector:error_rate_pct`)
- 13:30 SSL certificate on aa-fiu-gateway expired, causing SSL handshake failures (`log-00551`)
- 13:30 FI fetch failed for consent ee143657 due to upstream error (`log-00559`)

## Recommended actions

- **immediate**: Coordinate immediately with the external aa-fiu-gateway provider to renew and deploy a valid SSL certificate.. Directly resolves the expired certificate causing 100% account linking failures. (`log-00551`)
- **long_term**: Implement automated certificate expiration monitoring and alerting for all external dependencies.. Prevents future silent expirations from going unnoticed until runtime connection failures occur. (`log-00551`)
