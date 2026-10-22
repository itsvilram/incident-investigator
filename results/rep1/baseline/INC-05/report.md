# INC-05: Account linking via AA failing

**Verdict:** root cause identified

Account linking via Account Aggregator failed due to an expired mTLS client certificate on aa-connector preventing secure connections to aa-fiu-gateway.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 8 · LLM calls: 4 · tokens: 41369 · latency: 11.05s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Expired mTLS Client Certificate on aa-connector | aa-connector | certificate_expiry | 0.95 | `log-00002` Logged warning that mTLS client certificate expires at 2026-10-08T13:30:00Z.<br>`log-00551` Logged SSL handshake failure with aa-fiu-gateway due to expired certificate exactly at onset time.<br>`metric:aa-connector:error_rate_pct` Shows error rate spiking sharply at 13:30. | - |
| 2 | Third-Party AA FIU Gateway Outage | aa-fiu-gateway | third_party_outage | 0.05 | - | `log-00551` Logs explicitly attribute the failure to our own client certificate expiring, not an external gateway failure. |

## Facts (evidence-backed)

- aa-connector logged an mTLS client certificate expiration warning for 2026-10-08T13:30:00Z at 12:00:14Z. (`log-00002`)
- aa-connector error rate spiked to nearly 100% starting at 2026-10-08T13:30:00Z. (`metric:aa-connector:error_rate_pct`)
- aa-connector reported SSL handshake failures with aa-fiu-gateway due to certificate expiration starting at 13:30:03Z. (`log-00551`)
- mobile-bff experienced an error rate increase starting at 13:30. (`metric:mobile-bff:error_rate_pct`)

## Assumptions (not proven)

- The certificate was not automatically renewed due to an unconfigured or failing secret rotation operator.

## Evidence gaps

- None

## Timeline

- 12:00 aa-connector logs that its mTLS client certificate expires in 0 days. (`log-00002`)
- 13:30 mTLS client certificate expires; aa-connector error rate spikes. (`metric:aa-connector:error_rate_pct`)
- 13:30 First SSL handshake failure logged by aa-connector. (`log-00551`)

## Recommended actions

- **immediate**: Renew and deploy the expired mTLS client certificate for aa-connector.. Directly resolves the SSL handshake failures and restores account linking functionality. (`log-00551`)
- **short_term**: Configure proactive alerts for certificate expiration 14 and 7 days prior.. Prevents future unexpected outages from expired certificates. (`log-00002`)
