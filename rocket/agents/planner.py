"""Planner agent: decides which optimization to try next.

Uses an LLM (Qwen by default to align with the hackathon's Qwen sponsor track)
to read the profile + history and pick the next tool from the bounded toolbox.

Two backends are supported:
  1) OpenAI-compatible endpoint (works with vLLM serving Qwen on the MI300X)
  2) HuggingFace Inference (fallback)
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from ..tools import TOOL_DESCRIPTIONS


SYSTEM_PROMPT = """You are ROCKET's optimization planner.

Your job: given a model's runtime profile and a history of optimizations already
tried, pick the SINGLE BEST next optimization to apply from the bounded toolbox
below. You MUST pick a tool that hasn't already been applied (or pick a different
parameter if you re-apply one).

You are running on AMD MI300X. Optimize for tokens-per-second on autoregressive
generation. The host model is a Qwen causal LM.

# Toolbox (the only valid actions)
{toolbox}

# Output format
Respond with a single JSON object, no prose, matching this schema:
{{
  "tool": "<one of: {tool_names}>",
  "params": {{...}},   // tool-specific kwargs; can be empty
  "reasoning": "<one sentence explaining why this tool now>"
}}

Examples of valid params:
  - dtype_cast: {{"target": "bf16"}} or {{"target": "fp16"}}
  - torch_compile: {{"mode": "reduce-overhead"}} or {{"mode": "max-autotune"}}
  - sdpa_attention: {{}}
  - input_padding: {{"multiple": 128}}
  - kv_cache_config: {{"enabled": true}}

Pick the tool with the highest expected speedup given the profile. If the profile
shows attention dominates, prefer sdpa_attention. If the dtype is fp32, prefer
dtype_cast first. If kv_cache is off, that's the highest-priority fix.
"""


@dataclass
class PlannerDecision:
    tool: str
    params: dict[str, Any]
    reasoning: str
    raw: str = ""


def _format_toolbox() -> str:
    return "\n".join(f"- {name}: {desc}" for name, desc in TOOL_DESCRIPTIONS.items())


class Planner:
    """LLM-driven planner. Backend: OpenAI-compatible endpoint (e.g., vLLM/Qwen)."""

    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        # Defaults aim at a local vLLM serving Qwen on the same MI300X.
        # Overridable via env or constructor.
        self.model = model or os.getenv("ROCKET_PLANNER_MODEL", "Qwen/Qwen2.5-7B-Instruct")
        self.base_url = base_url or os.getenv(
            "ROCKET_PLANNER_BASE_URL", "http://localhost:8000/v1"
        )
        self.api_key = api_key or os.getenv("ROCKET_PLANNER_API_KEY", "EMPTY")

    def _client(self):
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError(
                "openai package required: pip install openai"
            ) from e
        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    def decide(
        self,
        profile_summary: str,
        history: list[dict[str, Any]],
        baseline_tok_s: float,
        current_tok_s: float,
    ) -> PlannerDecision:
        client = self._client()

        history_str = json.dumps(history, indent=2) if history else "(none yet)"
        sys = SYSTEM_PROMPT.format(
            toolbox=_format_toolbox(),
            tool_names=", ".join(TOOL_DESCRIPTIONS.keys()),
        )
        user = (
            f"# Current state\n"
            f"Baseline tok/s: {baseline_tok_s:.2f}\n"
            f"Current tok/s:  {current_tok_s:.2f} "
            f"({100*(current_tok_s/baseline_tok_s - 1):+.1f}% vs baseline)\n\n"
            f"{profile_summary}\n\n"
            f"# History (already tried)\n{history_str}\n\n"
            f"Pick the next tool to try."
        )

        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=400,
        )
        text = resp.choices[0].message.content or ""
        return self._parse(text)

    @staticmethod
    def _parse(text: str) -> PlannerDecision:
        # Extract first JSON object (LLMs sometimes add prose)
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise ValueError(f"planner returned no JSON object:\n{text}")
        obj = json.loads(match.group(0))
        return PlannerDecision(
            tool=obj["tool"],
            params=obj.get("params", {}) or {},
            reasoning=obj.get("reasoning", ""),
            raw=text,
        )


class OfflinePlanner(Planner):
    """Fallback planner that picks tools by a simple priority list.

    Useful for development without an LLM available, or if vLLM isn't up yet.
    """

    PRIORITY = [
        ("kv_cache_config", {"enabled": True}),
        ("dtype_cast", {"target": "bf16"}),
        ("sdpa_attention", {}),
        ("input_padding", {"multiple": 128}),
        ("torch_compile", {"mode": "reduce-overhead"}),
    ]

    def decide(self, profile_summary, history, baseline_tok_s, current_tok_s):
        tried = {h.get("tool") for h in history}
        for name, params in self.PRIORITY:
            if name not in tried:
                return PlannerDecision(
                    tool=name,
                    params=params,
                    reasoning=f"offline-priority: try {name} (not yet attempted)",
                )
        return PlannerDecision(
            tool="torch_compile",
            params={"mode": "max-autotune"},
            reasoning="offline: all priorities exhausted; escalate to max-autotune",
        )
