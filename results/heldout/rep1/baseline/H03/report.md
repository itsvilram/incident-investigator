# H03: KYC onboarding failing

**Verdict:** root cause identified

KYC onboarding failures since 13:50 UTC were caused by downstream 504 Gateway Timeouts from the external kyc-vendor during PAN verification calls. This exhausted the kyc-service worker pool (64/64 busy), causing request rejections, p99 latency spikes up to 30s, and elevated error rates in both kyc-service and mobile-bff.

system: baseline · stop: agent finished · rounds: 1 · tool calls: 10 · LLM calls: 5 · tokens: 53492 · latency: 19.09s

## Ranked hypotheses

| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |
|---|---|---|---|---|---|---|
| 1 | External KYC Vendor Degradation / Timeouts Causing Worker Pool Exhaustion | kyc-vendor | third_party_outage | 0.85 | `log-00675` Shows kyc-vendor returning 504 Gateway Timeouts after 30000ms starting at 13:50:15 UTC.<br>`metric:kyc-service:latency_p99_ms` Latency p99 anomaly onset at 13:51:00 UTC, peaking at ~30.7s.<br>`metric:kyc-service:error_rate_pct` Error rate anomaly onset at 13:52:00 UTC, peaking over 42%.<br>`log-00752` Verification worker pool exhausted (64/64 busy) error logs starting at 13:53:00 UTC. | - |
| 2 | Recent Code Deployment Introduced Blocking or Timeout Behavior | kyc-service | bad_deploy | 0.25 | `chg-8017` kyc-service v5.3.0 deployed a new PAN verification screen flow approximately 20 hours prior. | `metric:kyc-service:error_rate_pct` The deploy occurred ~20 hours prior to the error anomaly onset without prior symptoms, strongly implying external triggers. |

## Facts (evidence-backed)

- kyc-service error rate percentage anomaly started at 13:52:00 UTC and peaked at 42.72%. (`metric:kyc-service:error_rate_pct`)
- kyc-service p99 latency anomaly started at 13:51:00 UTC and peaked at 30,701ms. (`metric:kyc-service:latency_p99_ms`)
- kyc-vendor returned 504 Gateway Timeout after 30000ms starting at 13:50:15 UTC. (`log-00675`)
- kyc-service verification worker pool became exhausted (64/64 busy) at 13:53:00 UTC. (`log-00752`)
- mobile-bff error rate anomaly started at 13:52:00 UTC. (`metric:mobile-bff:error_rate_pct`)

## Assumptions (not proven)

- The external vendor kyc-vendor experienced internal capacity degradation or routing failures leading to 30-second timeouts.
- Rigid worker pool sizing and retry policies in kyc-service amplified the cascading failure by holding threads hostage.

## Evidence gaps

- Server-side logs and infrastructure metrics from kyc-vendor are unavailable due to it being an external vendor.

## Timeline

- 17:30 kyc-service v5.3.0 deployed (`chg-8017`)
- 13:50 First recorded kyc-vendor 504 Gateway Timeout on PAN verification (`log-00675`)
- 13:51 kyc-service p99 latency anomaly onset (`metric:kyc-service:latency_p99_ms`)
- 13:52 kyc-service and mobile-bff error rate anomaly onset (`metric:kyc-service:error_rate_pct`)
- 13:53 kyc-service verification worker pool exhausted (64/64 busy) (`log-00752`)
- 14:20 Incident reported by growth on-call

## Recommended actions

- **immediate**: Contact kyc-vendor support to report widespread 504 Gateway Timeouts on POST /v2/pan/verify.. Vendor-side timeouts are the primary driver of internal worker thread exhaustion. (`log-00675`)
- **immediate**: Implement circuit breakers and fast-fail fallbacks in kyc-service when vendor calls stall.. Prevents worker threads from getting blocked for 30 seconds and saturating the verification pool. (`log-00752`, `log-00675`)
- **short_term**: Increase kyc-service verification worker pool size and decouple verification tasks using an asynchronous model.. Mitigates thread starvation under similar future vendor slowdowns. (`log-00752`)
- **long_term**: Onboard a secondary backup KYC vendor for automatic traffic failover.. Protects user onboarding flow against single third-party vendor outages. (`log-00675`)
