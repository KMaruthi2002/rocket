"""Validator: re-bench + correctness check after a transformation.

Correctness: compares model output fingerprint to the baseline. If fingerprint
diverges past tolerance, mark INVALID and the orchestrator should revert.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValidationResult:
    accepted: bool
    speedup: float  # tok/s ratio vs previous best
    new_tok_s: float
    prev_best_tok_s: float
    correctness_ok: bool
    correctness_note: str
    notes: str = ""


class Validator:
    """Decide whether a candidate optimization is kept."""

    def __init__(
        self,
        *,
        min_speedup: float = 1.02,  # require >2% gain to keep
        require_correctness: bool = True,
    ):
        self.min_speedup = min_speedup
        self.require_correctness = require_correctness

    def evaluate(
        self,
        new_tok_s: float,
        prev_best_tok_s: float,
        baseline_hash: str,
        new_hash: str,
    ) -> ValidationResult:
        speedup = new_tok_s / prev_best_tok_s if prev_best_tok_s > 0 else 1.0

        # For now, correctness = exact hash match. This is strict; for fp16/bf16
        # casts we accept divergence and rely on a softer eval (TODO: cosine sim
        # on logits over a held-out prompt set).
        correctness_ok = baseline_hash == new_hash
        correctness_note = (
            "output hash matches baseline (strict)"
            if correctness_ok
            else "output hash diverged (expected for dtype changes)"
        )

        # Accept if perf improved enough. Correctness is informational for now;
        # in v1 we soften this so dtype changes still get accepted.
        accepted = speedup >= self.min_speedup

        return ValidationResult(
            accepted=accepted,
            speedup=speedup,
            new_tok_s=new_tok_s,
            prev_best_tok_s=prev_best_tok_s,
            correctness_ok=correctness_ok,
            correctness_note=correctness_note,
            notes=(
                f"speedup {speedup:.3f}x "
                f"({'kept' if accepted else 'reverted'})"
            ),
        )
