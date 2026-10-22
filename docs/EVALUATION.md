# Evaluation: multi-agent vs single-agent

## Setup

| | |
|---|---|
| Incidents | 18 synthetic fintech incidents ([dataset/scenarios.py](../dataset/scenarios.py)): a **dev set** INC-01..12 and a **held-out set** H01..H06 (see below). 16 have a known root cause; INC-09 and H06 should end **inconclusive** |
| Traps | red-herring deploys (one after onset, one 35 min before), cascading failure 2 hops away, config change rather than deploy, feature flag behind loud harmless warnings, misleading past incident, silent logs (shipper died), trigger deployed the day before, platform DNS outside the dependency graph, two changes one minute apart, tool failures. Held-out: a node's clock drift, a herring change 3 min *before* onset, a vendor failing behind a green health probe, a rate limit that makes downstream traffic drop, a bad event two hops away, two changes in the same minute that no evidence separates |
| Tool failures | scripted per incident (timeouts, 503s, partial results) **plus** a 5% seeded random rate on every call |
| Systems | multi-agent ([architecture](ARCHITECTURE.md)) vs single-agent baseline |
| Held equal | model (Gemini 3.5 Flash-Lite for every call), the five tools, the budget (40 tool calls, 30 LLM calls, 250k tokens, 600 s), the report schema, the domain principles in the prompts, the final verdict rule |
| Runs | Dev: 12 incidents × 2 systems × 2 repeats (fault seeds 7 and 8) = 48 runs. Held-out: 6 × 2 × 1 = 12 runs. Response cache **off**, runs one at a time, so latency is real |
| Fairness guard | `--strict`: any run that hit a rate limit or fell back to another model is discarded and re-run, so every scored run used the same model |

Commands (both model tiers set to `gemini:gemini-3.5-flash-lite`) are in the [README](../README.md#quick-start).

## Metrics

All scoring is automatic ([eval/scoring.py](../src/investigator/eval/scoring.py)); there is no LLM judge.

- **Accuracy (top-1):** the report says `root_cause_identified` and the top hypothesis's (service, category)
  is in the ground truth's accepted set. For INC-09 the report must say `inconclusive`.
- **Top-3 / right service:** a lenient view: the answer ranked anywhere in the top 3, or the right service
  with any category.
- **Wrongly inconclusive:** "inconclusive" on an incident that has a known answer.
- **Citation validity:** cited evidence IDs that were really retrieved in that run ÷ all cited IDs.
- **Key-evidence recall:** the ground truth lists the evidence that proves the answer (e.g. the "No space
  left on device" log lines, the disk metric). Recall = share of those groups the report cites.
- **Cost:** tool calls (every retry counts), LLM calls, tokens (prompt + completion, including hidden
  reasoning tokens), wall-clock latency.
- **Calibration:** mean top confidence when right vs. when wrong.

## Two incident sets

- **Dev set (INC-01..12):** used while building. Prompts and the Critic's rules were adjusted after seeing
  failures here (all changes are listed below), so these scores are optimistic.
- **Held-out set (H01..H06):** written *after* the system was frozen (git tag `freeze-before-heldout`), run
  once, never used for tuning. **This is the honest number.** You can verify that no system code changed after
  the freeze:
  ```
  git diff freeze-before-heldout -- src/investigator/agents src/investigator/harness \
      src/investigator/tools src/investigator/llm src/investigator/multi_agent.py src/investigator/baseline.py
  ```
  (empty). Only the dataset, the scoring summary and the docs changed after it.

Held-out runs: 6 incidents × 2 systems × 1 run. Dev runs: 12 × 2 × 2 runs (fault seeds 7 and 8). The dev runs
were split over two sessions because of the free quota (500 requests per day); the system code was identical in
both (checked with `git diff`).

## Results: held-out set

| | Multi-agent | Single-agent baseline |
|---|---|---|
| **Root-cause accuracy** | **4 / 6** | **4 / 6** |
| Right service (any category) | 5 / 6 | 5 / 6 |
| Wrong conclusions (all with confidence ≥ 0.8) | 2 | 2 |
| Citation validity / invented citations | 100% / 0 | 100% / 0 |
| Key-evidence recall | **100%** | 80% |
| Tool calls per incident | 13.0 | 10.3 |
| LLM calls per incident | 19.2 | 4.8 |
| Tokens per incident | 109k | 57k |
| Latency, mean (without free-tier rate-limit waits) | 70s (50s) | 18s (17s) |

| Incident | Expected | Multi-agent | Baseline |
|---|---|---|---|
| H01 node clock drift | kubernetes / config_change | ❌ kubernetes / network_dns | ❌ kubernetes / network_dns |
| H02 table lock, herring just before onset | ledger-db / resource_exhaustion | ✅ (ledger-db / dependency_failure, accepted) | ✅ |
| H03 vendor fails behind a green probe | kyc-vendor / third_party_outage | ✅ | ✅ |
| H04 edge rate limit, traffic drops | mobile-bff / config_change | ✅ | ✅ |
| H05 bad event, two hops away | payments-api / bad_deploy | ✅ | ✅ |
| H06 two changes, same minute | inconclusive | ❌ ledger-service / config_change | ❌ ledger-service / config_change |

## Results: dev set

| | Multi-agent | Single-agent baseline |
|---|---|---|
| **Root-cause accuracy** | **23 / 24 (96%)** | **20 / 24 (83%)** |
| Right service (any category) | 96% | 88% |
| Wrong conclusions (all with confidence ≥ 0.8) | **1** | **4** |
| Right when it concluded | 95% | 83% |
| Held back when it could have answered | 0 | 0 |
| Citation validity / invented citations | 100% / 0 | 99% / 2 |
| Key-evidence recall | 80% | 80% |
| Tool calls per incident | 12.8 | 10.2 |
| LLM calls per incident | 16.8 | 4.5 |
| Tokens per incident | 98k | 49k |
| Latency, mean (without free-tier rate-limit waits) | 64s (38s) | 19s (15s) |

Wrong runs: multi-agent INC-05 run 2 (blamed the gateway's certificate instead of our own client certificate).
Baseline: INC-09 both runs (concluded where the answer is inconclusive), INC-08 run 2 (ledger-db instead of
ledger-service), INC-11 run 2 (coredns / resource_exhaustion instead of network_dns).

Full tables per incident and run: [results/summary.md](../results/summary.md),
[results/heldout/summary.md](../results/heldout/summary.md). Every run's report, trace and shared state is in
`results/`.

## What it means

1. **On unseen incidents, the multi-agent system was not more accurate.** Both systems scored 4/6 and failed
   the same two incidents. With six incidents, that says the advantage, if any, is small. It does not show
   that the architecture wins.
2. **On the dev set it made fewer confident wrong conclusions (1 vs 4).** But half of the baseline's misses are
   INC-09, and the rule that makes the multi-agent system answer "inconclusive" there (missing telemetry on the
   affected service blocks a conclusion) was added after INC-09 failed in development. On that incident the
   LLM Critic accepted the wrong answer in both runs; **the code check is what said "inconclusive"**. Without
   INC-09 the dev scores are 22/22 vs 20/22.
3. **Grounding is good in both, and slightly better in the multi-agent system.** Neither invented evidence on
   the held-out set. The multi-agent reports cited all of the key evidence on held-out incidents (baseline
   80%), the result of the extra round that fetches the suspect's own telemetry.
4. **The feedback loop is used, and the code half matters.** 17 of 30 multi-agent runs went to a second or
   third round; 7 of those were forced by the code veto after the LLM Critic tried to accept early.
5. **It costs about 2× the tokens, 4× the LLM calls and 2.5–3× the latency.** On the free tier, multi-agent
   runs also wait 20–25 s per incident on per-minute rate limits, because parallel agents send requests in
   bursts.
6. **Confidence means little in either system.** Wrong answers came with the same ~0.9–0.95 confidence as
   right ones. Nothing in either system calibrates it.
7. **Robustness held:** about 80 injected tool failures (timeouts, 503s, partial results) across the runs, and
   no investigation crashed or lost its report.

## Why the failures happened

- **H06 (two changes, same minute):** the right answer is "inconclusive: revert one at a time". Both
  systems blamed the ledger-service change. The multi-agent Reasoning agent never even listed the competing
  ledger-db change as a hypothesis (its alternative was an unrelated vendor), and no code check looks for
  *competing triggers*. This is the clearest gap: a check that fires when two changes in the causal path
  precede the onset by similar margins would catch it.
- **H01 (clock drift):** both systems found the right service, the right change and the right mechanism
  ("node image changed time sync, clocks drifted, tokens look issued in the future"), but filed it under
  `network_dns`. Our category list has no class for infrastructure or time sync, so this is partly a
  taxonomy problem. We did not change the answer key after seeing the results.
- **INC-05 run 2:** blamed the external gateway's certificate. The code veto forced a check of the
  gateway, which looked healthy, but the LLM Critic accepted anyway. Code checks catch specific failure modes;
  they do not make the LLM judge evidence better.

## Changes made during development

All generic: none names an incident, a service from an answer, or a trap.

1. The Critic's code checks can veto "accept" and add the missing check as a request.
2. Confidence is limited to 0.02–0.95 (both systems).
3. Missing telemetry on a symptomatic service blocks a conclusion; a report cannot claim a root cause while a
   blocking check is open (added after INC-09 failed in development).
4. Strict evaluation mode (no runs on a fallback model or after a rate limit) and rate-limit wait time reported
   separately. These are evaluation-only changes.

## How far to trust this

- **Small samples:** 6 held-out incidents with one run each; 12 dev incidents with two runs. A difference of
  one or two runs can be chance.
- **One model** (Gemini 3.5 Flash-Lite). A stronger model might change both systems' results and the gap.
- **One author:** the same person (with the same AI assistant) wrote the system and both incident sets.
- **Synthetic data:** cleaner than production telemetry.
- **Strict categories:** a right service and mechanism under a different category counts as wrong (H01).
