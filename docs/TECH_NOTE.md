# Technical note

## Key decisions

**Own harness, not a framework.** The orchestration is about 400 lines of asyncio: a shared state, a
dependency-aware scheduler, a budget, a tracer. LangGraph would have provided the graph, but owning the
loop made the reliability behaviour explicit and testable: retries, time limits, provider fallback,
reserves, veto. Every step can be traced.

**Typed messages and evidence IDs.** Agents exchange Pydantic objects through the shared state, never
transcripts. Every tool result item has an ID, and every claim must cite one. Grounding can then be
*checked by code*: did the cited evidence exist, and did the blamed change precede the onset? It can also
be *scored without an LLM judge*.

**A Critic that is half code.** In development, the LLM Critic accepted hypotheses that had just failed an
automatic check (a suspect never observed, missing symptomatic telemetry). Blocking checks now veto
acceptance and turn into evidence requests. If a check is still open at the end, the verdict becomes
"inconclusive". Prompts alone did not fix this; a rule in code did.

**Tools that summarise.** Logs come back as patterns with counts and first-seen times; metrics as baseline,
anomaly onset and saturation. This is how real observability tools help humans, and it keeps each
investigation around 100k tokens.

**Deterministic adversity.** Incidents are generated from seeded specs. Tool failures are scripted per
incident plus a random rate, where the random draw is a hash of the call, so parallel runs reproduce exactly.
Ground truth sits where no tool can read it.

**One model for both systems** (Gemini 3.5 Flash-Lite), so the comparison isolates architecture. Tier
routing exists but was not varied.

## Trade-offs

<!-- RESULTS-TRADEOFFS -->

The code veto trades recall for honesty: it can turn a correct but under-verified answer into
"inconclusive". We accept that, because a confident wrong answer during an incident costs more than "we
need metrics from X".

## Limitations

- 12 synthetic incidents, used for both development and evaluation: scores are optimistic. Prompt changes
  were generic and are logged, but they were made after seeing failures.
- One model and few repeats. A one-incident difference is within noise.
- Synthetic telemetry is cleaner than production: no clock skew, sampling or cardinality limits.
- In-process execution: a crash loses the investigation. There is no durable queue.
- Latency includes free-tier queueing and retries.

## Improvements

1. **Durable execution** (Temporal or a Redis-backed queue), so long investigations survive restarts and
   can wait for a human.
2. **A held-out incident set** written by someone else, more repeats, and confidence intervals.
3. **Measured model routing:** a cheap model for evidence agents and a strong one for the Critic, compared
   on cost per correct answer.
4. **Real backends** (Prometheus, Loki, deploy history from CI/Argo) and trace queries; the tool interfaces
   already fit them.
5. **Check the final report too:** run the citation and timing checks on the report, not only on the
   hypotheses.
6. **Calibration:** learn a mapping from check results and evidence counts to confidence instead of
   trusting the model's number.
