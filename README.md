# Incident Investigator

A multi-agent AI system that investigates production incidents. It finds probable root causes and
recommends evidence-backed fixes. It is evaluated against a single-agent baseline on 12 synthetic
fintech incidents built with traps: red-herring deploys, cascading failures, misleading history,
silent logs, flaky tools, and one incident where the honest answer is "inconclusive".

Built for the Orange Invest AI Engineer take-home.

| | |
|---|---|
| Architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (diagrams, agent coordination) |
| Technical note | [docs/TECH_NOTE.md](docs/TECH_NOTE.md) (≤ 500 words) |
| Evaluation | [docs/EVALUATION.md](docs/EVALUATION.md) · raw: [results/summary.md](results/summary.md) |
| Dataset | [dataset/scenarios.py](dataset/scenarios.py) (12 incidents and their traps) · generated data in `data/` |
| AI assistant transcript | [transcript/](transcript/) |

<!-- RESULTS -->

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
uv run pytest                 # 60 tests, no network (a scripted fake LLM drives the agents)

uv run investigate list                          # the 12 incidents
uv run investigate run INC-02                    # multi-agent investigation of one incident
uv run investigate run INC-02 --system baseline  # the single-agent baseline
uv run investigate eval                          # all incidents, both systems, scored
uv run investigate eval --no-cache --out results # what produced results/ (latency is real)
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
tests/              60 tests: dataset, tools, scheduler, checks, LLM layer, end to end, scoring
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
| ≥ 10 test incidents with misleading evidence, conflicts, tool failures | `dataset/scenarios.py` (12) |
| Single-agent baseline with the same tools | `baseline.py` |
| Accuracy, grounding, tool calls, latency, tokens | `eval/scoring.py`, `results/summary.md` |
| No hardcoded answers | prompts are generic (`agents/prompts.py`); answers live only in `data/ground_truth/` |

## Limitations and external dependencies

- **External services:** an LLM API. Gemini (free tier) is the default, with Groq as fallback. There is no
  other network access. Everything else (data, tools) is local and synthetic.
- **Synthetic data.** The incidents are hand-designed and generated, not real telemetry. They test reasoning
  under traps, but they are cleaner than production (consistent clocks, no sampling, a single region).
- **Small evaluation.** 12 incidents, one model, few repeats. Differences of one or two incidents are within
  noise. See [docs/EVALUATION.md](docs/EVALUATION.md) for what the numbers do and do not show.
- **One model for every agent** in the evaluation (Gemini 3.5 Flash-Lite), chosen for a fair comparison
  and free-tier quota. Tier routing is implemented but not evaluated as a variable.
- **Not built:** a UI; a persistent task queue (runs are in-process asyncio, not Temporal or BullMQ);
  real observability backends (the tools read JSON files); streaming progress; human-in-the-loop approval
  of remediation actions (actions are recommendations only).
- **Prompt tuning risk:** prompts were adjusted only with generic rules during development. Every change is
  listed in [docs/EVALUATION.md](docs/EVALUATION.md). Still, the same 12 incidents were used for
  development and for evaluation, so the scores are optimistic for unseen incidents.

## AI coding assistant

Built with Claude Code (as the assignment allows). The full session transcript is in
[transcript/](transcript/). Personal content unrelated to the assignment is marked as redacted.
