# Test cases and results

All 18 test incidents, what each one tests, and how both systems did on every run. The numbers come from
[results/results.csv](../results/results.csv) and [results/heldout/results.csv](../results/heldout/results.csv);
how they were measured is in [EVALUATION.md](EVALUATION.md).

## Scoreboard

| Set | Incidents | Runs per system | Multi-agent correct | Single agent correct |
|---|---|---|---|---|
| Dev (INC-01..12), used while building | 12 | 24 (2 per incident) | 23 (96%) | 20 (83%) |
| **Held-out (H01..H06), written after the code freeze** | 6 | 6 (1 per incident) | **4 (67%)** | **4 (67%)** |
| All | 18 | 30 | 27 (90%) | 24 (80%) |

The held-out row is the fair comparison: those incidents were never used to tune anything. The dev row is
optimistic.

## What the incidents cover

The assignment asks for test incidents with misleading evidence, conflicting observations and tool failures.

| Kind of difficulty | Incidents |
|---|---|
| **Misleading evidence** (a suspicious change or a wrong guess in the report) | INC-02, INC-03, INC-05, INC-08, INC-10, H01, H02, H03, H04, H05 |
| **Conflicting observations** (data sources disagree) | INC-04, INC-06, INC-09, INC-12, H03, H04, H06 |
| **Tool failures** (scripted timeouts, 503s, partial results) | INC-03, INC-07, INC-09, plus a 5% random failure rate on every tool call in every incident |
| **Cause far from the symptoms** (another service, a vendor, the platform) | INC-03, INC-08, INC-11, H01, H05 |
| **Right answer is "inconclusive"** | INC-09, H06 |
| **Control** (no trap) | INC-01 |

## Every test case

Results show the answer each system gave (service / category) and its confidence. ✅ = correct.

### Dev set (2 runs per system)

| ID | What really happened | The trap | Expected | Multi-agent | Single agent |
|---|---|---|---|---|---|
| INC-01 | A payments-api release has a null-handling bug | None: control case | payments-api / bad_deploy | ✅ ✅ | ✅ ✅ |
| INC-02 | The ledger database disk filled up | The report blames a deploy that happened 8 min **after** the outage began | ledger-db / resource_exhaustion | ✅ ✅ | ✅ ✅ |
| INC-03 | The partner bank's API slowed down | Symptoms appear two services away; an unrelated config change; a harmless cache burst; partial logs | partner-bank-api / third_party_outage | ✅ ✅ | ✅ ✅ |
| INC-04 | A config sync cut the database connection pool from 50 to 5 | A config change, not a deploy ("no deploys today" is true); the database looks healthy | ledger-service / config_change | ✅ ✅ | ✅ ✅ |
| INC-05 | Our mTLS client certificate expired | The report and a past incident both point to gateway rate limiting | aa-connector / certificate_expiry | ✅ ❌ blamed the gateway's certificate (0.95) | ✅ ✅ |
| INC-06 | A memory leak from yesterday's release; pods are OOM-killed | "Logs are clean" because log shipping died; the release is outside the default time window | portfolio-service / resource_exhaustion (or bad_deploy) | ✅ ✅ | ✅ ✅ |
| INC-07 | A push campaign sent 6× traffic to orders-service | The metrics tool times out; logs come back partial; an earlier unrelated 429 blip | orders-service (or notification-service) / traffic_spike | ✅ ✅ | ✅ ✅ |
| INC-08 | A feature flag turned on an unindexed query | Very loud but harmless deprecation warnings; the cause is two services away | ledger-service / feature_flag | ✅ ✅ | ✅ ❌ named ledger-db (0.90) |
| INC-09 | Unknown: the key service's metrics never load and its logs are partial | Two weak leads that conflict | **inconclusive** | ✅ ✅ | ❌ ❌ blamed sms-vendor (0.85) both times |
| INC-10 | The OTP vendor returns 503s | The report blames a deploy that ran cleanly for 35 min before the outage | otp-provider / third_party_outage | ✅ ✅ | ✅ ✅ |
| INC-11 | DNS (coredns) was scaled down to one replica | Vendors look guilty; DNS is not in the dependency graph | coredns / network_dns (or config_change) | ✅ ✅ | ✅ ❌ coredns / resource_exhaustion (0.95) |
| INC-12 | A routing config change sends one bank's users to a wrong endpoint | Two changes one minute apart; payments-api only passes the error on | upi-gateway / config_change | ✅ ✅ | ✅ ✅ |

### Held-out set (1 run per system)

| ID | What really happened | The trap | Expected | Multi-agent | Single agent |
|---|---|---|---|---|---|
| H01 | A node-image change broke time sync; one node's clock runs ahead | Looks like an auth bug; an auth release 2 days earlier; only one node's pods fail | kubernetes / config_change (or bad_deploy) | ❌ kubernetes / network_dns (0.95) | ❌ kubernetes / network_dns (0.92) |
| H02 | A scheduled job locked the ledger table | A config change 3 min **before** the outage, so the timing fits; database CPU *drops* | ledger-db / resource_exhaustion (or dependency_failure) | ✅ | ✅ |
| H03 | The KYC vendor fails for one document type only | The vendor's health probe stays green; our thread pool looks guilty; a release the day before | kyc-vendor / third_party_outage | ✅ | ✅ |
| H04 | A rate-limit config change blocks users behind shared mobile IPs | An auth release 30 min earlier; an unrelated vendor blip; downstream traffic *drops* | mobile-bff / config_change | ✅ | ✅ |
| H05 | A payments-api release renamed an event field; the consumer crash-loops | Symptoms two hops away behind the event bus; restarts look like a memory problem | payments-api / bad_deploy | ✅ | ✅ |
| H06 | Two changes on two services in the same minute; nothing separates them | Both changes look like a convincing cause | **inconclusive** | ❌ ledger-service / config_change (0.95) | ❌ ledger-service / config_change (0.90) |

## The failures, in one line each

| Run | Why it failed |
|---|---|
| H06, both systems | Neither recognised genuine ambiguity. The multi-agent Reasoning agent never listed the second change as a hypothesis, and no code check looks for competing causes. |
| H01, both systems | Right service and right mechanism (clock drift), but filed under `network_dns`. The category list has no "infrastructure" class. Counted as wrong; the answer key was not changed after seeing results. |
| INC-09, single agent (both runs) | Concluded "sms-vendor" although the affected service's metrics never loaded. The multi-agent system said "inconclusive" because a code check blocks conclusions without that telemetry. |
| INC-05 run 2, multi-agent | Blamed the gateway's certificate instead of our own. The code veto forced a check of the gateway (healthy), but the LLM Critic accepted anyway. |
| INC-08 run 2, single agent | Named the database where the slow queries ran, instead of the service whose flag caused them. |
| INC-11 run 2, single agent | Right service, wrong category (resource_exhaustion instead of network_dns). |

## What the results say

- **Accuracy on unseen incidents: equal** (4/6 each, same two failures).
- **Confident wrong answers: fewer with multi-agent** on the dev set (1 vs 4), mainly from code checks rather
  than the LLM Critic.
- **Evidence:** both cite only evidence they really retrieved. Multi-agent cited all the key evidence on
  held-out incidents (single agent 80%).
- **Cost:** multi-agent uses about 2× the tokens and 2.5–3× the time.
- **Shared blind spots:** genuine ambiguity, uncalibrated confidence (wrong answers at 0.90–0.95), and a
  category list that is too narrow.
