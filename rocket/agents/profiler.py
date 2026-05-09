"""Profiler agent: runs torch.profiler, summarizes hotspots."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import torch
from torch.profiler import ProfilerActivity, profile, record_function


@dataclass
class HotSpot:
    name: str
    self_cpu_time_us: float
    self_device_time_us: float
    cpu_pct: float
    device_pct: float

    def summary(self) -> str:
        return (
            f"{self.name}  "
            f"device={self.self_device_time_us/1000:.2f}ms ({self.device_pct:.1f}%)  "
            f"cpu={self.self_cpu_time_us/1000:.2f}ms ({self.cpu_pct:.1f}%)"
        )


@dataclass
class ProfileReport:
    device: str
    hotspots: list[HotSpot] = field(default_factory=list)
    total_device_time_ms: float = 0.0
    notes: str = ""

    def to_planner_prompt(self) -> str:
        """Compact, LLM-friendly summary for the Planner."""
        lines = [f"# Profile ({self.device})"]
        lines.append(f"Total device time: {self.total_device_time_ms:.2f} ms\n")
        lines.append("Top hotspots (sorted by device time):")
        for h in self.hotspots[:10]:
            lines.append(f"- {h.summary()}")
        if self.notes:
            lines.append(f"\nNotes: {self.notes}")
        return "\n".join(lines)


class Profiler:
    """Run a single forward+generate pass under torch.profiler and summarize."""

    def __init__(self, device: str):
        self.device = device

    def profile(
        self,
        model,
        tokenizer,
        *,
        prompt: str = "Hello world",
        new_tokens: int = 32,
        top_k: int = 15,
    ) -> ProfileReport:
        activities = [ProfilerActivity.CPU]
        if self.device == "cuda":
            activities.append(ProfilerActivity.CUDA)

        enc = tokenizer(prompt, return_tensors="pt").to(self.device)

        with profile(
            activities=activities,
            record_shapes=False,
            profile_memory=False,
        ) as prof:
            with record_function("rocket_generate"):
                with torch.no_grad():
                    model.generate(
                        **enc,
                        max_new_tokens=new_tokens,
                        do_sample=False,
                        num_beams=1,
                        pad_token_id=tokenizer.eos_token_id,
                    )
            if self.device == "cuda":
                torch.cuda.synchronize()

        # Extract per-op stats
        events = prof.key_averages()
        total_dev = sum(getattr(e, "self_cuda_time_total", 0) for e in events) or 1
        total_cpu = sum(e.self_cpu_time_total for e in events) or 1

        hotspots: list[HotSpot] = []
        for e in events:
            dev_t = getattr(e, "self_cuda_time_total", 0)
            cpu_t = e.self_cpu_time_total
            hotspots.append(
                HotSpot(
                    name=e.key,
                    self_cpu_time_us=cpu_t,
                    self_device_time_us=dev_t,
                    cpu_pct=100 * cpu_t / total_cpu,
                    device_pct=100 * dev_t / total_dev,
                )
            )

        # rank by device time if we have it, else cpu time
        key = (
            (lambda h: h.self_device_time_us)
            if self.device == "cuda"
            else (lambda h: h.self_cpu_time_us)
        )
        hotspots.sort(key=key, reverse=True)

        return ProfileReport(
            device=self.device,
            hotspots=hotspots[:top_k],
            total_device_time_ms=total_dev / 1000,
        )
