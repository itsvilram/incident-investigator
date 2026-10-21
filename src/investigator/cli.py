"""Command line.

    investigate list                          the test incidents
    investigate run INC-02                    multi-agent investigation of one incident
    investigate run INC-02 --system baseline  the single-agent baseline
    investigate run INC-02 --system both      both, one after the other
    investigate eval                          every incident, both systems, scored

Each run writes report.md, result.json, trace.jsonl (and state.json for multi-agent)
under runs/<timestamp>/<system>/<incident>/.
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console

from investigator import baseline, multi_agent
from investigator.config import PROJECT_ROOT, get_settings
from investigator.llm.router import build_router
from investigator.runs import save_run
from investigator.world import World, list_incidents

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(prog="investigate", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list the test incidents")

    run = sub.add_parser("run", help="investigate one incident")
    run.add_argument("incident")
    run.add_argument("--system", choices=["multi", "baseline", "both"], default="multi")
    _common(run)

    ev = sub.add_parser("eval", help="run and score every incident with both systems")
    ev.add_argument("--incidents", default="all", help="comma-separated IDs, or 'all'")
    ev.add_argument("--systems", default="multi,baseline")
    ev.add_argument("--repeats", type=int, default=1)
    ev.add_argument("--concurrency", type=int, default=2,
                    help="incidents investigated at the same time")
    _common(ev)

    args = parser.parse_args()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    if args.command == "list":
        for incident_id in list_incidents():
            inc = World.load(incident_id).incident
            console.print(f"[bold]{incident_id}[/]  {inc.title}")
    elif args.command == "run":
        asyncio.run(_run(args))
    else:
        from investigator.eval.runner import run_eval

        asyncio.run(run_eval(args))


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--no-cache", action="store_true", help="always call the LLM")
    p.add_argument("--seed", type=int, default=7, help="seed for random tool failures")
    p.add_argument("--fault-rate", type=float, default=0.05,
                   help="probability of a random tool failure per call")
    p.add_argument("--out", type=Path, default=None, help="output folder")


async def _run(args: argparse.Namespace) -> None:
    router = build_router(get_settings(), use_cache=not args.no_cache)
    out = args.out or PROJECT_ROOT / "runs" / datetime.now().strftime("%Y%m%d-%H%M%S")
    world = World.load(args.incident)
    systems = ["multi", "baseline"] if args.system == "both" else [args.system]
    for system in systems:
        console.rule(f"{args.incident} · {system}")
        if system == "multi":
            result, state = await multi_agent.investigate(
                world, router, seed=args.seed, fault_rate=args.fault_rate)
            folder = save_run(result, state.ctx, out, multi_agent.state_snapshot(state))
        else:
            result, ctx = await baseline.investigate(
                world, router, seed=args.seed, fault_rate=args.fault_rate)
            folder = save_run(result, ctx, out)
        r = result.report
        console.print(f"[bold]Verdict:[/] {r.verdict}   [dim]stop: {result.stop_reason}[/]")
        for h in r.ranked_hypotheses[:3]:
            console.print(f"  {h.rank}. [{h.confidence:.2f}] {h.root_cause_service} / "
                          f"{h.category}: {h.title}")
        console.print(f"[dim]rounds {result.rounds} · tool calls {result.tool_calls} · "
                      f"LLM calls {result.llm_calls} · tokens {result.total_tokens:,} · "
                      f"{result.latency_s}s[/]")
        console.print(f"Report: {folder / 'report.md'}")


if __name__ == "__main__":
    main()
