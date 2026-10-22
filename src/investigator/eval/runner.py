"""Run every incident with both systems, score the runs, write the summary.

Resumable: a run whose result.json already exists in the output folder is loaded,
not re-run, so an eval interrupted by a quota limit continues where it stopped.
"""

import argparse
import asyncio
import json
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from investigator import baseline, multi_agent
from investigator.config import PROJECT_ROOT, get_settings
from investigator.eval.scoring import load_truth, score
from investigator.eval.summary import write_summary
from investigator.llm.router import build_router
from investigator.runs import save_run
from investigator.world import World, list_incidents

console = Console()
SYSTEMS = {"multi": "multi_agent", "baseline": "baseline"}


async def run_eval(args: argparse.Namespace) -> Path:
    settings = get_settings()
    router = build_router(settings, use_cache=not args.no_cache)
    incidents = list_incidents() if args.incidents == "all" else args.incidents.split(",")
    systems = [SYSTEMS[s.strip()] for s in args.systems.split(",")]
    out: Path = args.out or PROJECT_ROOT / "runs" / f"eval-{datetime.now():%Y%m%d-%H%M%S}"
    jobs = [(rep, inc, sys) for rep in range(1, args.repeats + 1) for inc in incidents
            for sys in systems]
    slots = asyncio.Semaphore(args.concurrency)
    console.print(f"[bold]{len(jobs)} runs[/] → {out}  models: {router.describe()}  "
                  f"cache: {'off' if args.no_cache else 'on'}")
    started = time.monotonic()

    async def job(rep: int, incident: str, system: str) -> dict[str, Any] | None:
        folder = out / f"rep{rep}"
        existing = folder / system / incident / "result.json"
        if existing.exists():
            return json.loads(existing.read_text())
        async with slots:
            try:
                world = World.load(incident)
                seed = args.seed + rep - 1
                if system == "multi_agent":
                    result, state = await multi_agent.investigate(
                        world, router, seed=seed, fault_rate=args.fault_rate)
                    save_run(result, state.ctx, folder, multi_agent.state_snapshot(state))
                else:
                    result, ctx = await baseline.investigate(
                        world, router, seed=seed, fault_rate=args.fault_rate)
                    save_run(result, ctx, folder)
            except Exception as error:  # one broken run must not sink the whole eval
                console.print(f"[red]{incident} {system} rep{rep} crashed: {error}[/]")
                (folder / system / incident).mkdir(parents=True, exist_ok=True)
                (folder / system / incident / "error.txt").write_text(traceback.format_exc())
                return None
        data = result.to_json()
        row = score(data, load_truth(incident))
        console.print(
            f"{'✅' if row['correct'] else '❌'} {incident} {system:<11} rep{rep} "
            f"{row['verdict']:<21} {row['top_answer']:<40} {row['tool_calls']:>3} tools "
            f"{row['tokens']:>8,} tok {row['latency_s']:>6.1f}s")
        return data

    results = await asyncio.gather(*(job(*j) for j in jobs))
    rows = [score(r, load_truth(r["incident_id"])) for r in results if r is not None]
    failed = len(jobs) - len(rows)
    models = next((r["models"] for r in results if r), {})
    notes = [
        f"Generated {datetime.now():%Y-%m-%d %H:%M}. Models: {models}. "
        f"Cache: {'off' if args.no_cache else 'on'}. Repeats: {args.repeats}. "
        f"Random tool-fault rate: {args.fault_rate:.0%} (plus each incident's scripted "
        f"faults). Wall time: {time.monotonic() - started:.0f}s.",
    ]
    if failed:
        notes.append(f"**{failed} run(s) crashed** and are not in the table; see error.txt.")
    path = write_summary(rows, out, title="Evaluation: multi-agent vs single-agent", notes=notes)
    console.print(f"[bold]Summary:[/] {path}")
    return path
