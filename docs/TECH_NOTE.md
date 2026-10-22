# Technical note

## Key decisions

**Own harness, not a framework.** About 400 lines of asyncio: shared state, a dependency-aware scheduler,
a budget, a tracer. LangGraph would supply the graph, but owning the loop made retries, time limits,
provider fallback, the reporter's budget reserve and the Critic veto explicit and testable.

**Typed messages and evidence IDs.** Agents exchange Pydantic objects through the shared state, never
transcripts. Every tool result item has an ID and every claim cites one. Grounding can then be checked by
code (does the evidence exist? did the blamed change precede the onset?) and scored without an LLM judge.

**A Critic that is half code.** The LLM Critic accepted hypotheses that had just failed an automatic check.
Blocking checks now veto acceptance and become evidence requests; a check still open at the end makes the
verdict "inconclusive". Prompts alone did not fix this.

**Summarising tools.** Logs return patterns with counts and first-seen times; metrics return baseline, onset
and saturation. That keeps an investigation near 100k tokens.

**Deterministic adversity.** Seeded incident specs; scripted plus hash-seeded random tool failures,
reproducible under parallelism; ground truth that no tool can read.

**A fair comparison.** One model for both systems, the same tools, budget and verdict rule. Strict mode
discards rate-limited runs. A held-out set was written after a code freeze.

## Trade-offs

On six held-out incidents both systems scored 4/6 and failed the same two. The multi-agent system cited key
evidence more completely (100% vs 80%) and, on the dev set, made fewer confident wrong conclusions (1 vs 4).
It costs about 2× the tokens, 4× the LLM calls and 2.5–3× the latency, plus free-tier rate-limit waits from
bursty parallel calls. With this model, its value is caution and auditability, not accuracy.

The veto trades recall for honesty: it can turn a correct but under-verified answer into "inconclusive".

## Limitations

- Small samples (6 held-out incidents × 1 run, 12 dev × 2), one model, and one author for both the system and
  the incidents.
- Neither system recognises genuine ambiguity: given two changes in the same minute, both picked one.
- Confidence is uncalibrated: wrong answers scored as high as right ones.
- Synthetic telemetry. In-process execution, so a crash loses the investigation.

## Improvements

1. A competing-trigger check: when two candidate changes in the causal path precede the onset, require
   evidence that separates them before concluding.
2. Durable execution (Temporal or a Redis-backed queue) with checkpoints and human approval steps.
3. Calibrate confidence from check results and evidence counts instead of trusting the model's number.
4. A larger held-out set written by someone else, more repeats, more models.
5. Measured tier routing: cheap evidence agents and a strong Critic, scored on cost per correct answer.
6. Real backends (Prometheus, Loki, CI deploy history); the tool interfaces already fit them.
