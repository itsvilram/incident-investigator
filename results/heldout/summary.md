# Evaluation: multi-agent vs single-agent

Generated 2026-10-22 12:45. Models: {'fast': ['gemini:gemini-3.5-flash-lite'], 'strong': ['gemini:gemini-3.5-flash-lite']}. Cache: off. Repeats: 1. Random tool-fault rate: 5% (plus each incident's scripted faults). Wall time: 530s.

## Overall

| Metric | Multi-agent | Single-agent baseline |
|---|---|---|
| Root-cause accuracy (top-1) | 67% | 67% |
| Correct answer in top 3 | 67% | 67% |
| Right service (any category) | 83% | 83% |
| Concluded a root cause (runs) | 6 | 6 |
| Wrong conclusion (runs) | 2 | 2 |
|   of which confident, top confidence >= 0.8 (runs) | 2 | 2 |
| Right when it concluded | 67% | 67% |
| Held back when it could have answered (runs) | 0 | 0 |
| Citation validity (cited IDs really retrieved) | 100% | 100% |
| Invented citations (total) | 0 | 0 |
| Key-evidence recall | 100% | 80% |
| Tool calls per incident (incl. retries) | 13.00 | 10.33 |
| LLM calls per incident | 19.17 | 4.83 |
| Tokens per incident | 109,141 | 56,761 |
| Tokens, all incidents | 654,844 | 340,566 |
| Latency per incident (mean) | 70.1s | 18.1s |
| Latency per incident (median) | 77.8s | 18.1s |
|   of which waiting on rate limits (mean) | 20.0s | 1.7s |
| Latency without rate-limit waits (mean) | 50.1s | 16.5s |
| Mean top confidence when right | 0.92 | 0.90 |
| Mean top confidence when wrong | 0.95 | 0.91 |

Runs per system: multi_agent=6, baseline=6.

## Per incident

| Incident | Expected | Multi-agent | Single-agent baseline |
|---|---|---|---|
| H01 | kubernetes / config_change | ❌ kubernetes / network_dns (0.95), 10 tools, 103,007 tok, 53s | ❌ kubernetes / network_dns (0.92), 11 tools, 56,010 tok, 26s |
| H02 | ledger-db / resource_exhaustion | ✅ ledger-db / dependency_failure (0.95), 16 tools, 132,447 tok, 79s | ✅ ledger-db / resource_exhaustion (0.90), 12 tools, 68,714 tok, 19s |
| H03 | kyc-vendor / third_party_outage | ✅ kyc-vendor / third_party_outage (0.85), 14 tools, 149,417 tok, 85s | ✅ kyc-vendor / third_party_outage (0.85), 10 tools, 53,492 tok, 19s |
| H04 | mobile-bff / config_change | ✅ mobile-bff / config_change (0.95), 10 tools, 78,231 tok, 41s | ✅ mobile-bff / config_change (0.92), 8 tools, 39,395 tok, 14s |
| H05 | payments-api / bad_deploy | ✅ payments-api / bad_deploy (0.95), 15 tools, 97,006 tok, 86s | ✅ payments-api / bad_deploy (0.92), 8 tools, 31,396 tok, 14s |
| H06 | inconclusive | ❌ ledger-service / config_change (0.95), 13 tools, 94,736 tok, 76s | ❌ ledger-service / config_change (0.90), 13 tools, 91,559 tok, 17s |

## Traps per incident

- **H01**: looks like an auth-service bug; an auth-service deploy 2 days earlier; only pods on one node fail
- **H02**: the blamed config change comes 3 minutes BEFORE onset, so the timing fits; database CPU drops: lock waits, not load
- **H03**: the vendor's health probe stays green; kyc-service's own thread pool looks like the cause; a kyc-service deploy the day before
- **H04**: an auth-service deploy 30 minutes earlier; an earlier, unrelated OTP-vendor blip; downstream services look healthy: their traffic DROPS
- **H05**: symptoms are two hops away, behind the event bus; restarting pods look like a memory problem; a past incident blames the SMS vendor
- **H06**: two changes in the same minute on two services in the same path; the symptoms fit both, and no evidence separates them
