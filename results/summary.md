# Evaluation: multi-agent vs single-agent

Generated 2026-10-22 13:03. Models: {'fast': ['gemini:gemini-3.5-flash-lite'], 'strong': ['gemini:gemini-3.5-flash-lite']}. Cache: off. Repeats: 2. Random tool-fault rate: 5% (plus each incident's scripted faults). Wall time: 1127s.

## Overall

| Metric | Multi-agent | Single-agent baseline |
|---|---|---|
| Root-cause accuracy (top-1) | 96% | 83% |
| Correct answer in top 3 | 96% | 83% |
| Right service (any category) | 96% | 88% |
| Concluded a root cause (runs) | 22 | 24 |
| Wrong conclusion (runs) | 1 | 4 |
|   of which confident, top confidence >= 0.8 (runs) | 1 | 4 |
| Right when it concluded | 95% | 83% |
| Held back when it could have answered (runs) | 0 | 0 |
| Citation validity (cited IDs really retrieved) | 100% | 99% |
| Invented citations (total) | 0 | 2 |
| Key-evidence recall | 80% | 80% |
| Tool calls per incident (incl. retries) | 12.83 | 10.21 |
| LLM calls per incident | 16.83 | 4.54 |
| Tokens per incident | 98,180 | 48,932 |
| Tokens, all incidents | 2,356,324 | 1,174,370 |
| Latency per incident (mean) | 63.6s | 18.8s |
| Latency per incident (median) | 58.2s | 14.8s |
|   of which waiting on rate limits (mean) | 25.4s | 3.8s |
| Latency without rate-limit waits (mean) | 38.2s | 15.0s |
| Mean top confidence when right | 0.94 | 0.92 |
| Mean top confidence when wrong | 0.95 | 0.89 |

Runs per system: multi_agent=24, baseline=24.

## Per incident

| Incident | Expected | Multi-agent | Single-agent baseline |
|---|---|---|---|
| INC-01 | payments-api / bad_deploy | ✅ payments-api / bad_deploy (0.95), 9 tools, 69,118 tok, 25s<br>✅ payments-api / bad_deploy (0.95), 8 tools, 62,283 tok, 36s | ✅ payments-api / bad_deploy (0.95), 9 tools, 46,088 tok, 30s<br>✅ payments-api / bad_deploy (0.95), 8 tools, 48,476 tok, 15s |
| INC-02 | ledger-db / resource_exhaustion | ✅ ledger-db / resource_exhaustion (0.95), 10 tools, 113,788 tok, 64s<br>✅ ledger-db / resource_exhaustion (0.95), 16 tools, 123,130 tok, 78s | ✅ ledger-db / resource_exhaustion (0.95), 12 tools, 51,639 tok, 14s<br>✅ ledger-db / resource_exhaustion (0.95), 13 tools, 91,082 tok, 22s |
| INC-03 | partner-bank-api / third_party_outage | ✅ partner-bank-api / third_party_outage (0.95), 13 tools, 101,059 tok, 54s<br>✅ partner-bank-api / third_party_outage (0.95), 12 tools, 95,695 tok, 40s | ✅ partner-bank-api / third_party_outage (0.85), 12 tools, 68,769 tok, 16s<br>✅ partner-bank-api / third_party_outage (0.90), 9 tools, 56,303 tok, 16s |
| INC-04 | ledger-service / config_change | ✅ ledger-service / config_change (0.95), 7 tools, 56,904 tok, 53s<br>✅ ledger-service / config_change (0.95), 15 tools, 77,302 tok, 38s | ✅ ledger-service / config_change (0.95), 7 tools, 27,047 tok, 10s<br>✅ ledger-service / config_change (0.95), 10 tools, 40,108 tok, 14s |
| INC-05 | aa-connector / certificate_expiry | ✅ aa-connector / certificate_expiry (0.95), 8 tools, 61,192 tok, 34s<br>❌ aa-fiu-gateway / certificate_expiry (0.95), 12 tools, 119,434 tok, 102s | ✅ aa-connector / certificate_expiry (0.95), 8 tools, 41,369 tok, 11s<br>✅ aa-connector / certificate_expiry (0.95), 6 tools, 22,223 tok, 9s |
| INC-06 | portfolio-service / resource_exhaustion | ✅ portfolio-service / resource_exhaustion (0.95), 10 tools, 64,016 tok, 58s<br>✅ portfolio-service / resource_exhaustion (0.95), 8 tools, 70,329 tok, 37s | ✅ portfolio-service / resource_exhaustion (0.90), 7 tools, 46,541 tok, 13s<br>✅ portfolio-service / bad_deploy (0.90), 9 tools, 44,123 tok, 17s |
| INC-07 | orders-service / traffic_spike | ✅ orders-service / traffic_spike (0.95), 18 tools, 131,312 tok, 131s<br>✅ notification-service / traffic_spike (0.95), 16 tools, 137,289 tok, 78s | ✅ orders-service / traffic_spike (0.90), 12 tools, 47,683 tok, 14s<br>✅ orders-service / traffic_spike (0.90), 11 tools, 39,161 tok, 26s |
| INC-08 | ledger-service / feature_flag | ✅ ledger-service / feature_flag (0.95), 13 tools, 129,979 tok, 73s<br>✅ ledger-service / feature_flag (0.95), 13 tools, 61,357 tok, 24s | ✅ ledger-service / feature_flag (0.90), 15 tools, 81,256 tok, 16s<br>❌ ledger-db / feature_flag (0.90), 19 tools, 115,188 tok, 48s |
| INC-09 | inconclusive | ✅ inconclusive (0.85), 26 tools, 169,756 tok, 125s<br>✅ inconclusive (0.92), 26 tools, 156,702 tok, 125s | ❌ sms-vendor / third_party_outage (0.85), 12 tools, 35,530 tok, 28s<br>❌ sms-vendor / third_party_outage (0.85), 14 tools, 32,600 tok, 15s |
| INC-10 | otp-provider / third_party_outage | ✅ otp-provider / third_party_outage (0.95), 11 tools, 103,898 tok, 72s<br>✅ otp-provider / third_party_outage (0.95), 13 tools, 112,842 tok, 44s | ✅ otp-provider / third_party_outage (0.85), 10 tools, 44,475 tok, 11s<br>✅ otp-provider / third_party_outage (0.90), 10 tools, 44,254 tok, 12s |
| INC-11 | coredns / network_dns | ✅ coredns / network_dns (0.95), 15 tools, 101,853 tok, 61s<br>✅ coredns / network_dns (0.95), 12 tools, 102,552 tok, 91s | ✅ coredns / network_dns (0.95), 8 tools, 33,639 tok, 44s<br>❌ coredns / resource_exhaustion (0.95), 8 tools, 32,906 tok, 12s |
| INC-12 | upi-gateway / config_change | ✅ upi-gateway / config_change (0.95), 8 tools, 58,547 tok, 25s<br>✅ upi-gateway / config_change (0.95), 9 tools, 75,987 tok, 58s | ✅ upi-gateway / config_change (0.95), 7 tools, 42,014 tok, 25s<br>✅ upi-gateway / config_change (0.95), 9 tools, 41,896 tok, 13s |

## Traps per incident

- **INC-01**: none: control case
- **INC-02**: reporter blames a deploy; the blamed deploy happened 8 minutes AFTER onset
- **INC-03**: symptoms are two hops away from the cause; an unrelated config change at 13:30; a harmless cache eviction burst
- **INC-04**: a config change, not a deploy: 'no deploys today' is true; the database looks healthy (low CPU, few connections)
- **INC-05**: the reporter and a past incident point to gateway rate limiting; the gateway itself is healthy
- **INC-06**: 'logs are clean' because log shipping died, not because the service is healthy; the trigger was deployed the day before, outside the default time window
- **INC-07**: the metrics tool times out for orders-service; logs come back partial; an earlier, unrelated broker-api 429 blip
- **INC-08**: very loud but harmless deprecation warnings (present all day); the cause is a flag, not a deploy, and two services away
- **INC-09**: the key service's metrics are unavailable and its logs incomplete; two weak, conflicting leads (sms-vendor slowness vs consumer lag); push is delayed too, which sms-vendor cannot explain
- **INC-10**: the reporter blames a deploy; the deploy went out 35 minutes before onset with clean metrics in between; the new resend limit shows up in logs and looks related
- **INC-11**: vendors look like the obvious suspects; the dependency graph has no edge to coredns: it is a platform service; other services show the same DNS errors
- **INC-12**: two changes one minute apart; payments-api errors are pass-through from upi-gateway; the new payments-api endpoint works fine
