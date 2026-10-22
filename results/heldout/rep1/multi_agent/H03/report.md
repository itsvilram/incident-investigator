# H03: KYC onboarding failing

**Verdict:** root cause identified

KYC onboarding failures began at 13:50:15 UTC due to external third-party kyc-vendor returning 504 Gateway Timeouts on POST /v2/pan/verify calls. This caused kyc-service verification threads to block, exhausting its worker pool (64/64 busy) by 13:53, elevating kyc-service latency and error rates, and subsequently increasing error rates in mobile-bff.

system: multi_agent · stop: critic accepted the top hypothesis · rounds: 2 · tool calls: 14 · LLM calls: 24 · tokens: 149417 · latency: 85.12s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | Third-party KYC Vendor Outage | kyc-vendor | third_party_outage | 0.85 | `log-00675` First warning of kyc-vendor returning 504 Gateway Timeout at 13:50:15, preceding all symptoms.<br>`log-00699` kyc-service retrying pan/verify calls due to vendor timeouts.<br>`log-00754` Verification worker pool exhaustion error in kyc-service resulting from blocked synchronous calls.<br>`metric:kyc-service:latency_p99_ms` kyc-service latency p99 spiked dramatically starting at 13:51.<br>`metric:kyc-service:error_rate_pct` kyc-service error rate surged at 13:52.<br>`metric:mobile-bff:error_rate_pct` mobile-bff error rate concurrently rose at 13:52 due to synchronous dependencies on kyc-service. | `metric:kyc-vendor:rps` kyc-vendor RPS showed no anomaly during the incident window.<br>`metric:kyc-vendor:error_rate_pct` kyc-vendor error_rate_pct showed no anomaly during the incident window.<br>`metric:kyc-vendor:latency_p99_ms` kyc-vendor latency_p99_ms showed no anomaly during the incident window. |
| 2 | KYC Service Deployment Regressed Timeout Handling | kyc-service | bad_deploy | 0.15 | `chg-8017` kyc-service v5.3.0 deployed a new PAN verification screen flow a day prior to the incident.<br>`log-00754` Worker pool exhaustion occurred in kyc-service.<br>`log-00699` kyc-service retrying pan/verify calls repeatedly. | `log-00675` Directly attributes the 30000ms timeouts to kyc-vendor POST /v2/pan/verify returning 504 Gateway Timeout rather than internal kyc-service logic.<br>`metric:kyc-vendor:rps` kyc-vendor metrics remain entirely normal, making pure client-side triggering less likely. |

## Facts (evidence-backed)

- kyc-service latency_p99_ms began rising sharply at 13:51, peaking at over 30 seconds. (`metric:kyc-service:latency_p99_ms`)
- kyc-service error_rate_pct anomaly started at 13:52, peaking at 42.72%. (`metric:kyc-service:error_rate_pct`)
- mobile-bff error_rate_pct anomaly started at 13:52, rising up to 2.85%. (`metric:mobile-bff:error_rate_pct`)
- First warning of kyc-vendor returning 504 Gateway Timeout occurred at 13:50:15. (`log-00675`)
- First kyc-service verification worker pool exhaustion error occurred at 13:53:03. (`log-00754`)
- kyc-service CPU, memory, and pod restarts showed no anomalies or restarts during the incident window. (`metric:kyc-service:cpu_pct`, `metric:kyc-service:mem_pct`, `metric:kyc-service:pod_restarts`)
- mobile-bff calls kyc-service synchronously. (`dep:mobile-bff->kyc-service`)
- kyc-service calls kyc-vendor and user-db synchronously. (`dep:kyc-service->kyc-vendor`, `dep:kyc-service->user-db`)
- kyc-service was deployed with version v5.3.0 on 2026-10-17T17:30:00+00:00. (`chg-8017`)
- kyc-vendor rps shows no anomaly during the incident window with a baseline of 24.61 req/s and stable values. (`metric:kyc-vendor:rps`)
- kyc-vendor error_rate_pct shows no anomaly during the incident window, staying at a baseline of 0.34% and maxing out at 0.48%. (`metric:kyc-vendor:error_rate_pct`)
- kyc-vendor latency_p99_ms shows no anomaly during the incident window, maintaining a baseline of 716.88 ms. (`metric:kyc-vendor:latency_p99_ms`)

## Assumptions (not proven)

- The external third-party kyc-vendor experienced localized gateway/proxy failures or upstream database lockups that manifested as 504 Gateway Timeouts at the API integration layer without registering as global metric anomalies.

## Evidence gaps

- query_logs(service=kyc-service) returned partial data

## Timeline

- 17:30 kyc-service v5.3.0 deployed (`chg-8017`)
- 13:50 First kyc-vendor POST /v2/pan/verify 504 Gateway Timeout logged by kyc-service (`log-00675`)
- 13:51 kyc-service latency p99 anomaly starts upward (`metric:kyc-service:latency_p99_ms`)
- 13:51 kyc-service begins retrying pan/verify calls (`log-00699`)
- 13:52 kyc-service error rate anomaly starts (`metric:kyc-service:error_rate_pct`)
- 13:52 mobile-bff error rate anomaly starts (`metric:mobile-bff:error_rate_pct`)
- 13:53 First kyc-service verification worker pool exhaustion error logged (`log-00754`)

## Recommended actions

- **immediate**: Contact third-party KYC vendor support to investigate potential localized proxy gateway timeouts or origin server connectivity issues on POST /v2/pan/verify.. Logs confirm continuous 504 Gateway Timeouts returned from kyc-vendor starting at 13:50:15. (`log-00675`, `log-00699`)
- **short_term**: Implement circuit breakers and aggressive request timeouts with fallback mechanisms in kyc-service for external vendor calls to prevent worker thread saturation.. Synchronous vendor calls hung for up to 30 seconds, exhausting the 64/64 worker pool and cascading errors to mobile-bff. (`log-00754`, `dep:kyc-service->kyc-vendor`)
- **long_term**: Establish specialized vendor-specific monitoring and alerting for intermediate proxy or gateway error codes that do not surface in aggregate RPS or latency metrics.. Vendor aggregate metrics showed no anomaly despite persistent 504 Gateway Timeouts impacting user traffic. (`metric:kyc-vendor:rps`, `metric:kyc-vendor:error_rate_pct`, `metric:kyc-vendor:latency_p99_ms`)
