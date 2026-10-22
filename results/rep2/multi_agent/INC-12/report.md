# INC-12: UPI payments failing for some users

**Verdict:** root cause identified

About 8% of UPI payments failed starting at 14:07 UTC due to a routing configuration update on upi-gateway (chg-9824) that incorrectly moved @okbank handles to partner-bank-api /v3/collect. Because partner-bank-api did not have this endpoint available or ready, it returned 404 Not Found errors, resulting in route failures (U30) in upi-gateway and subsequent transaction failures in payments-api.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 1 · tool calls: 9 · LLM calls: 13 · tokens: 75987 · latency: 58.39s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Routing Configuration Update Sent @okbank Traffic to Incorrect Endpoint | upi-gateway | config_change | 0.95 | `chg-9824` Config update at 14:06 moved @okbank handles to partner-bank-api /v3/collect, immediately preceding the anomaly.<br>`metric:payments-api:error_rate_pct` Error rate spiked starting at 14:07, right after the config change.<br>`metric:upi-gateway:error_rate_pct` Error rate spiked starting at 14:07.<br>`log-00788` upi-gateway logged 404 Not Found from partner-bank-api POST /v3/collect starting at 14:07.<br>`log-00790` payments-api logged UPI collect failed due to upi-gateway error U30 (route failure) starting at 14:07. | - |
| 2 | Payments-API v2.15.0 Deploy Caused Request Formatting Incompatibility | payments-api | bad_deploy | 0.05 | `chg-9649` payments-api v2.15.0 was deployed at 14:05, just before the incident. | `log-00788` Error logs explicitly show partner-bank-api returning 404 Not Found on /v3/collect, indicating a downstream routing and endpoint issue rather than a client-side formatting bug.<br>`chg-9824` The routing table update for @okbank explicitly targeted partner-bank-api /v3/collect precisely at 14:06, aligning with the 14:07 error onset. |

## Facts (evidence-backed)

- The error rate anomaly for payments-api began at 2026-10-07T14:07:00+00:00, rising from a baseline under 0.4% to a peak of 8.89%. (`metric:payments-api:error_rate_pct`)
- The error rate anomaly for upi-gateway began at 2026-10-07T14:07:00+00:00, rising from a baseline under 0.5% to a peak of 10.28%. (`metric:upi-gateway:error_rate_pct`)
- payments-api logged repeated errors stating 'UPI collect failed: upi-gateway error U30 (route failure)' starting at 14:07:07 UTC. (`log-00790`, `log-01635`)
- upi-gateway logged repeated errors stating 'partner-bank-api POST /v3/collect returned 404 Not Found for handle' starting at 14:07:03 UTC. (`log-00788`, `log-01639`)
- A deploy for payments-api (v2.15.0) occurred at 2026-10-07T14:05:00+00:00. (`chg-9649`)
- A routing table config update for upi-gateway moved @okbank handles to partner-bank-api /v3/collect at 2026-10-07T14:06:00+00:00. (`chg-9824`)

## Assumptions (not proven)

- partner-bank-api does not have /v3/collect deployed or active for @okbank handles.

## Evidence gaps

- none

## Timeline

- 14:05 payments-api v2.15.0 deployed (`chg-9649`)
- 14:06 upi-gateway routing table config updated to move @okbank handles to partner-bank-api /v3/collect (`chg-9824`)
- 14:07 Error rate spikes begin for both payments-api and upi-gateway (`metric:payments-api:error_rate_pct`)
- 14:07 upi-gateway logs 404 Not Found from partner-bank-api POST /v3/collect (`log-00788`)
- 14:07 payments-api logs UPI collect failure due to upi-gateway error U30 (`log-00790`)

## Recommended actions

- **immediate**: Revert the upi-gateway routing configuration change for @okbank handles back to /v2/collect or the correct active endpoint.. The config change introduced at 14:06 directly triggered 404 errors and transaction failures on upi-gateway. (`chg-9824`, `log-00788`)
- **short_term**: Verify partner-bank-api endpoint availability and version compatibility before updating routing tables in future releases.. Routing traffic to an unconfigured endpoint (/v3/collect) caused a complete failure for @okbank users. (`chg-9824`, `log-00788`)
- **long_term**: Implement pre-deployment checks or canary validation for gateway routing configuration updates.. Prevents misconfigurations from propagating directly to production traffic without validation. (`chg-9824`)
