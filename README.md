# Incident Investigator

A multi-agent AI system that investigates production incidents. It finds probable root causes and
recommends evidence-backed fixes. It is evaluated against a single-agent baseline on 18 synthetic
fintech incidents built with traps: red-herring deploys, cascading failures, misleading history,
silent logs, flaky tools, and incidents where the honest answer is "inconclusive". Six of them were
written after the code was frozen and are scored separately.

Built for the Orange Invest AI Engineer take-home.

| | |
|---|---|
| Architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (diagrams, agent coordination) |
| Technical note | [docs/TECH_NOTE.md](docs/TECH_NOTE.md) (≤ 500 words) |
| Evaluation | [docs/EVALUATION.md](docs/EVALUATION.md) · raw: [held-out](results/heldout/summary.md), [dev](results/summary.md) |
| Test cases and results | [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md) (all 18 incidents, every run) |
| Dataset | [dataset/scenarios.py](dataset/scenarios.py) (18 incidents and their traps) · generated data in `data/` |

## Results

Same model (Gemini 3.5 Flash-Lite), tools, budget and report format for both systems. Cache off; 5% random
tool failures plus scripted ones.

| | Held-out set: 6 incidents, written after the code freeze | Dev set: 12 incidents × 2 runs |
|---|---|---|
| Root-cause accuracy, multi-agent vs single agent | **4/6 vs 4/6** | 23/24 vs 20/24 |
| Wrong conclusions (all confident) | 2 vs 2 | **1 vs 4** |
| Key evidence cited | **100% vs 80%** | 80% vs 80% |
| Invented citations | 0 vs 0 | 0 vs 2 |
| Tokens per incident | 109k vs 57k | 98k vs 49k |
| Latency without free-tier rate-limit waits | 50s vs 17s | 38s vs 15s |

**In short:** on unseen incidents the multi-agent system was no more accurate. Both failed the same two
incidents, one of them a genuinely ambiguous case that neither recognised. It cited the key evidence more
completely and, on the dev set, made fewer confident wrong conclusions, partly because its code checks force
"inconclusive" when the affected service's telemetry is missing. It costs about 2× the tokens and 2.5–3× the
time. Details and caveats: [docs/EVALUATION.md](docs/EVALUATION.md).

## How it works (30 seconds)

```
incident ─► Orchestrator ─► [Observability ∥ Dependency] ─► Reasoning ─► Critic ─┬─► Reporting ─► report
                 ▲                (parallel tool use)       (hypotheses)  (code   │
                 └────────────── evidence requests ◄─────────────────────  checks │
                                  (feedback loop, max 3 rounds)            + LLM) ┘
```

- **Six agents** exchange typed (Pydantic) results through a **shared investigation state**: tasks,
  evidence store, findings, hypotheses, critiques, gaps, budget, trace.
- **Every claim cites evidence IDs** (`log-00412`, `metric:ledger-db:disk_used_pct`, `chg-1042`).
  Code checks that cited IDs were really retrieved, and that a blamed change happened *before* the
  symptoms.
- **The Critic is part code, part LLM.** The code half can veto an acceptance and send the team back for
  evidence. An investigation can end **inconclusive**.
- **Reliability:** parallel tasks with dependencies, bounded retries, per-task time limits, provider
  fallback on rate limits, a hard budget (tool calls, LLM calls, tokens, time) with a reserve for the
  report, and code fallbacks when an agent fails.
- **Tools fail on purpose:** timeouts, 503s and partial results, scripted per incident plus a seeded
  random rate.

## Quick start

Requirements: Python 3.13 and [uv](https://docs.astral.sh/uv/). For real runs, a free
[Gemini API key](https://aistudio.google.com) and/or a free [Groq key](https://console.groq.com).
Tests need no key.

```bash
uv sync
cp .env.example .env          # then paste GEMINI_API_KEY and/or GROQ_API_KEY
uv run pytest                 # 73 tests, no network (a scripted fake LLM drives the agents)

uv run investigate list                          # the 18 incidents
uv run investigate run INC-02                    # multi-agent investigation of one incident
uv run investigate run INC-02 --system baseline  # the single-agent baseline
uv run investigate eval                          # all incidents, both systems, scored
```

What produced `results/` (both model tiers set to `gemini:gemini-3.5-flash-lite` in `.env`; `--strict`
discards any run that hit a rate limit or fell back to another model, and the eval resumes where it stopped):

```bash
uv run investigate eval --incidents H01,H02,H03,H04,H05,H06 --repeats 1 --no-cache --strict --out results/heldout
uv run investigate eval --repeats 2 --no-cache --strict --out results \
  --incidents INC-01,INC-02,INC-03,INC-04,INC-05,INC-06,INC-07,INC-08,INC-09,INC-10,INC-11,INC-12
```

Each run writes `report.md` (human-readable), `result.json`, `trace.jsonl` (every agent step, LLM call
and tool call with timing and tokens) and, for multi-agent runs, `state.json` (the final shared state)
under `runs/<timestamp>/<system>/<incident>/`.

Useful options: `--seed` (random tool failures), `--fault-rate 0.2` (more failures),
`--incidents INC-01,INC-09`, `--repeats 2`.

Models are set in `.env` as tiers: `MODELS_FAST` and `MODELS_STRONG`, each a fallback list of
`provider:model`. The default for both is `gemini:gemini-3.5-flash-lite,groq:openai/gpt-oss-120b`.

To regenerate the dataset: `uv run python dataset/generate.py` (seeded, so the output is identical).

## Project layout

```
dataset/            scenario specs (incidents + traps) and the generator
data/world/         what the tools can read: logs, metrics, changes, topology, history, faults
data/ground_truth/  the answers, read only by the scorer (eval/scoring.py)
src/investigator/
  models.py         typed messages between agents
  tools/            5 tools + executor (failure injection, retries, evidence store)
  harness/          budget, tracer, evidence store, shared state, scheduler
  agents/           orchestrator, specialists (observability, dependency, reasoning, critic),
                    reporting, code checks, prompts
  llm/              OpenAI-compatible client, router (tiers, fallback), cache, schemas, fake
  multi_agent.py    the multi-agent investigation loop
  baseline.py       the single-agent baseline
  eval/             scoring, runner, summary
tests/              73 tests: dataset, tools, scheduler, checks, LLM layer, end to end, scoring
docs/               architecture, technical note, evaluation
results/            final evaluation output
```

## Assignment requirements → where

| Requirement | Where |
|---|---|
| ≥ 5 agents: orchestrator, observability, dependency, reasoning, critic, reporting | `agents/` (all six) |
| Structured exchange, real collaboration | `models.py`, `harness/state.py`; the Critic → Orchestrator feedback loop |
| Tools for logs, metrics, deployments, dependencies, history | `tools/catalog.py` |
| Structured I/O, error handling, simulated failures | `tools/executor.py`, `data/world/incidents/*/faults.json` |
| Parallel execution | `harness/scheduler.py` (tasks) and `agents/base.py` (tool calls in a turn) |
| Shared state, task dependencies | `harness/state.py`, `harness/scheduler.py` |
| Feedback loops | Critic requests → Orchestrator → new tasks; code veto in `agents/specialists.py` |
| Bounded retries, limits, termination | executor and task retries, `Budget`, stop rules in `multi_agent.py` |
| Recovery from agent/tool failures | provider fallback, task retry, code fallbacks for orchestrator and reporter |
| Ranked hypotheses, evidence for/against, confidence, actions | `FinalReport` in `models.py`; `report.md` per run |
| Facts vs assumptions, inconclusive outcome | `facts` / `assumptions` / `evidence_gaps`; verdict rules in `agents/reporting.py` |
| ≥ 10 test incidents with misleading evidence, conflicts, tool failures | `dataset/scenarios.py`: **18** (12 dev + 6 held-out) |
| Single-agent baseline with the same tools | `baseline.py` |
| Accuracy, grounding, tool calls, latency, tokens | `eval/scoring.py`, `results/summary.md` |
| No hardcoded answers | prompts are generic (`agents/prompts.py`); answers live only in `data/ground_truth/` |

## Limitations and external dependencies

- **External services:** an LLM API. Gemini (free tier) is the default, with Groq as fallback. There is no
  other network access. Everything else (data, tools) is local and synthetic.
- **Synthetic data.** The incidents are hand-designed and generated, not real telemetry. They test reasoning
  under traps, but they are cleaner than production (consistent clocks, no sampling, a single region).
- **Small evaluation.** 6 held-out incidents (one run each) and 12 dev incidents (two runs), one model.
  Differences of one or two runs are within noise. See [docs/EVALUATION.md](docs/EVALUATION.md) for what the
  numbers do and do not show.
- **One model for every agent** in the evaluation (Gemini 3.5 Flash-Lite), chosen for a fair comparison
  and free-tier quota. Tier routing is implemented but not evaluated as a variable.
- **Not built:** a UI; a persistent task queue (runs are in-process asyncio, not Temporal or BullMQ);
  real observability backends (the tools read JSON files); streaming progress; human-in-the-loop approval
  of remediation actions (actions are recommendations only).
- **Tuning risk:** prompts and Critic rules were adjusted with generic rules while working on the 12 dev
  incidents (listed in [docs/EVALUATION.md](docs/EVALUATION.md)), so dev scores are optimistic. The held-out
  set was written after the freeze tag `freeze-before-heldout`; `git diff freeze-before-heldout --
  src/investigator/agents` shows no change since. The same author wrote both sets.
