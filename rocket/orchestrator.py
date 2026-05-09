"""ROCKET orchestrator — runs the full Profile → Plan → Apply → Validate loop."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .agents import Profiler, Validator
from .agents.planner import OfflinePlanner, Planner, PlannerDecision
from .bench import BenchResult, benchmark, detect_device, free, load_model
from .tools import TOOLBOX


console = Console()


@dataclass
class Iteration:
    step: int
    decision: dict
    pre_tok_s: float
    post_tok_s: float
    speedup_vs_prev: float
    cumulative_speedup: float
    accepted: bool
    profile_summary: str
    note: str = ""


@dataclass
class RunReport:
    model_id: str
    device_label: str
    baseline_tok_s: float
    final_tok_s: float
    cumulative_speedup: float
    iterations: list[Iteration] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


class Orchestrator:
    def __init__(
        self,
        model_id: str,
        *,
        dtype: str = "fp32",
        max_iterations: int = 5,
        new_tokens: int = 64,
        prompt_tokens: int = 64,
        runs: int = 3,
        warmup: int = 1,
        log_path: str | Path = "logs/run.jsonl",
        use_offline_planner: bool = False,
    ):
        self.model_id = model_id
        self.dtype = dtype
        self.max_iterations = max_iterations
        self.bench_kwargs = dict(
            new_tokens=new_tokens,
            prompt_tokens=prompt_tokens,
            runs=runs,
            warmup=warmup,
        )
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.planner: Planner = OfflinePlanner() if use_offline_planner else Planner()

    def _log(self, payload: dict) -> None:
        with self.log_path.open("a") as f:
            f.write(json.dumps(payload) + "\n")

    def run(self) -> RunReport:
        device, label = detect_device()
        console.rule(f"[bold red]ROCKET[/bold red]  ::  {label}")
        console.print(f"target model: [bold]{self.model_id}[/bold]")

        # ---- Baseline ----
        console.print("\n[cyan]→ loading model + measuring baseline[/cyan]")
        model, tokenizer = load_model(self.model_id, dtype=self.dtype, device=device)
        baseline = benchmark(model, tokenizer, device, notes="baseline", **self.bench_kwargs)
        console.print(
            Panel.fit(
                f"baseline tok/s = [bold red]{baseline.tokens_per_second:.2f}[/bold red]\n"
                f"dtype = {baseline.dtype}    "
                f"peak mem = {baseline.peak_memory_mb} MB",
                title="baseline",
            )
        )
        self._log({"event": "baseline", "result": baseline.to_dict()})

        baseline_tok_s = baseline.tokens_per_second
        baseline_hash = baseline.output_hash
        prev_best = baseline_tok_s

        report = RunReport(
            model_id=self.model_id,
            device_label=label,
            baseline_tok_s=baseline_tok_s,
            final_tok_s=baseline_tok_s,
            cumulative_speedup=1.0,
        )

        history: list[dict[str, Any]] = []
        profiler = Profiler(device=device)
        validator = Validator(min_speedup=1.02)

        # ---- Loop ----
        for step in range(1, self.max_iterations + 1):
            console.rule(f"iteration {step}")

            # Profile current model
            profile = profiler.profile(model, tokenizer)
            profile_summary = profile.to_planner_prompt()
            console.print(
                Panel(profile_summary, title=f"profile @ step {step}", style="dim")
            )

            # Plan
            try:
                decision: PlannerDecision = self.planner.decide(
                    profile_summary=profile_summary,
                    history=history,
                    baseline_tok_s=baseline_tok_s,
                    current_tok_s=prev_best,
                )
            except Exception as e:
                console.print(f"[yellow]planner failed ({e}); falling back to offline[/yellow]")
                decision = OfflinePlanner().decide(
                    profile_summary, history, baseline_tok_s, prev_best
                )

            console.print(
                Panel.fit(
                    f"[bold]{decision.tool}[/bold]({decision.params})\n"
                    f"[dim]{decision.reasoning}[/dim]",
                    title=f"planner decision",
                )
            )

            tool_fn = TOOLBOX.get(decision.tool)
            if tool_fn is None:
                console.print(f"[red]unknown tool {decision.tool!r}; skipping[/red]")
                history.append({"tool": decision.tool, "applied": False, "error": "unknown"})
                continue

            try:
                model, tokenizer, info = tool_fn(model, tokenizer, **decision.params)
            except Exception as e:
                console.print(f"[red]tool {decision.tool} failed: {e}[/red]")
                history.append({"tool": decision.tool, "applied": False, "error": str(e)})
                continue

            # Re-bench
            new = benchmark(
                model, tokenizer, device,
                notes=f"after {decision.tool}", **self.bench_kwargs,
            )
            console.print(
                f"new tok/s = [bold]{new.tokens_per_second:.2f}[/bold] "
                f"(prev best {prev_best:.2f})"
            )

            verdict = validator.evaluate(
                new_tok_s=new.tokens_per_second,
                prev_best_tok_s=prev_best,
                baseline_hash=baseline_hash,
                new_hash=new.output_hash,
            )

            it = Iteration(
                step=step,
                decision={"tool": decision.tool, "params": decision.params,
                          "reasoning": decision.reasoning, "tool_info": info},
                pre_tok_s=prev_best,
                post_tok_s=new.tokens_per_second,
                speedup_vs_prev=verdict.speedup,
                cumulative_speedup=new.tokens_per_second / baseline_tok_s,
                accepted=verdict.accepted,
                profile_summary=profile_summary,
                note=verdict.notes,
            )
            report.iterations.append(it)
            self._log({"event": "iteration", "iteration": asdict(it)})

            history.append({
                "tool": decision.tool,
                "params": decision.params,
                "speedup_vs_prev": round(verdict.speedup, 3),
                "accepted": verdict.accepted,
            })

            color = "green" if verdict.accepted else "yellow"
            console.print(
                f"[{color}]{verdict.notes} | cumulative {it.cumulative_speedup:.2f}x[/]"
            )

            if verdict.accepted:
                prev_best = new.tokens_per_second
            else:
                # Revert by reloading. Cheap for small models; for big ones,
                # in v2 we'd checkpoint state and restore.
                console.print("[yellow]reverting (reload)[/yellow]")
                free(model)
                model, tokenizer = load_model(self.model_id, dtype=self.dtype, device=device)
                # Re-apply all kept history
                for h in history:
                    if h.get("accepted"):
                        TOOLBOX[h["tool"]](model, tokenizer, **h.get("params", {}))

        report.final_tok_s = prev_best
        report.cumulative_speedup = prev_best / baseline_tok_s

        # ---- Summary table ----
        table = Table(title="ROCKET run summary")
        table.add_column("step")
        table.add_column("tool")
        table.add_column("Δ vs prev", justify="right")
        table.add_column("cumulative", justify="right")
        table.add_column("kept?")
        for it in report.iterations:
            table.add_row(
                str(it.step),
                it.decision["tool"],
                f"{it.speedup_vs_prev:.2f}x",
                f"{it.cumulative_speedup:.2f}x",
                "✓" if it.accepted else "✗",
            )
        console.print(table)
        console.print(
            Panel.fit(
                f"baseline: {baseline_tok_s:.2f} tok/s\n"
                f"final:    {report.final_tok_s:.2f} tok/s\n"
                f"speedup:  [bold red]{report.cumulative_speedup:.2f}x[/bold red]",
                title="ROCKET result",
            )
        )

        self._log({"event": "summary", "report": report.to_dict()})
        return report


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--dtype", default="fp32", choices=["fp32", "bf16", "fp16"])
    ap.add_argument("--iterations", type=int, default=5)
    ap.add_argument("--offline", action="store_true",
                    help="use the offline rule-based planner instead of LLM")
    args = ap.parse_args()

    orch = Orchestrator(
        model_id=args.model,
        dtype=args.dtype,
        max_iterations=args.iterations,
        use_offline_planner=args.offline,
    )
    orch.run()
