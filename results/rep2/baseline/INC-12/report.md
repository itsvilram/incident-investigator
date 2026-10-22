# INC-12: UPI payments failing for some users

**Verdict:** root cause identified

About 8% of UPI payments for okbank users began failing at 14:07 due to an incorrect routing configuration update (chg-9824) at 14:06 that directed okbank handles to an invalid /v3/collect endpoint on partner-bank-api instead of /v2/collect.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 9 · LLM calls: 4 · tokens: 41896 · latency: 12.97s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Routing Configuration Error | upi-gateway | config_change | 0.95 | `chg-9824` Routing table config update at 14:06 changed @okbank handles to partner-bank-api /v3/collect<br>`metric:upi-gateway:error_rate_pct` Error rate spiked starting at 14:07:00, coinciding with the config change<br>`log-00788` partner-bank-api returned 404 Not Found for /v3/collect starting at 14:07:03<br>`log-00790` payments-api logged upi-gateway error U30 (route failure) starting at 14:07:07 | - |
| 2 | Bad Code Deploy in payments-api | payments-api | bad_deploy | 0.05 | `chg-9649` payments-api v2.15.0 was deployed at 14:05, just before incident onset | `log-00788` Errors originate from upi-gateway failing to reach partner-bank-api at /v3/collect rather than internal code exceptions<br>`log-00790` Error messages explicitly cite upi-gateway error U30 (route failure) |

## Facts (evidence-backed)

- Error rates for payments-api and upi-gateway spiked starting at 2026-10-07T14:07:00Z. (`metric:payments-api:error_rate_pct`, `metric:upi-gateway:error_rate_pct`)
- payments-api v2.15.0 was deployed at 2026-10-07T14:05:00Z. (`chg-9649`)
- upi-gateway routing configuration was updated at 2026-10-07T14:06:00Z to route @okbank handles to /v3/collect. (`chg-9824`)
- partner-bank-api returned 404 Not Found for /v3/collect requests starting at 14:07:03Z. (`log-00788`)
- payments-api encountered upi-gateway error U30 route failure starting at 14:07:07Z. (`log-00790`)

## Assumptions (not proven)

- partner-bank-api does not support the /v3/collect endpoint for okbank handles.

## Evidence gaps

- Direct access logs from partner-bank-api to verify endpoint availability.

## Timeline

- 14:05 payments-api v2.15.0 deployed (`chg-9649`)
- 14:06 upi-gateway routing config updated for okbank handles (`chg-9824`)
- 14:07 Error rate anomaly begins on payments-api and upi-gateway (`metric:payments-api:error_rate_pct`)
- 14:07 partner-bank-api returns 404 for /v3/collect (`log-00788`)
- 14:07 payments-api logs upi-gateway error U30 (route failure) (`log-00790`)
- 14:30 Incident reported by on-call engineer

## Recommended actions

- **immediate**: Roll back the routing configuration change to restore @okbank handles to /v2/collect.. Will immediately resolve the 404 errors and U30 route failures causing payment drops. (`chg-9824`, `log-00788`, `log-00790`)
- **short_term**: Implement validation checks for partner API endpoints prior to applying gateway routing changes.. Prevents deploying configuration routes to non-existent or unsupported third-party endpoints. (`chg-9824`, `log-00788`)
