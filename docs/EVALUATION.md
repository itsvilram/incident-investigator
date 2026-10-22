# Evaluation: multi-agent vs single-agent

## Setup

| | |
|---|---|
| Incidents | 12 synthetic fintech incidents ([dataset/scenarios.py](../dataset/scenarios.py)). 11 have a known root cause; 1 (INC-09) should end **inconclusive** |
| Traps | red-herring deploys (one after onset, one 35 min before), cascading failure 2 hops away, config change rather than deploy, feature flag behind loud harmless warnings, misleading past incident, silent logs (shipper died), trigger deployed the day before, platform DNS outside the dependency graph, two changes one minute apart, tool failures |
| Tool failures | scripted per incident (timeouts, 503s, partial results) **plus** a 5% seeded random rate on every call |
| Systems | multi-agent ([architecture](ARCHITECTURE.md)) vs single-agent baseline |
| Held equal | model (Gemini 3.5 Flash-Lite for every call), the five tools, the budget (40 tool calls, 30 LLM calls, 250k tokens, 600 s), the report schema, the domain principles in the prompts, the final verdict rule |
| Runs | 2 repeats per incident and system (fault seeds 7 and 8): 48 runs. Response cache **off**, runs one at a time, so latency is real |
| Fairness guard | `--strict`: any run that hit a rate limit or fell back to another model is discarded and re-run, so every scored run used the same model |

Command: `investigate eval --no-cache --strict --repeats 2 --out results` (with both model tiers set to
`gemini:gemini-3.5-flash-lite`).

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

<!-- RESULTS -->
