"""torch.compile transformation."""
from __future__ import annotations

import torch


VALID_MODES = ("default", "reduce-overhead", "max-autotune")


def apply_torch_compile(model, tokenizer, *, mode: str = "reduce-overhead", **_):
    """Compile model.forward via torch.compile.

    On ROCm 7+, dispatches through Inductor and produces fused kernels.
    Cold-start cost: first run is slow as kernels get cached.
    """
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}")

    try:
        compiled = torch.compile(model, mode=mode, dynamic=False)
    except Exception as e:
        return model, tokenizer, {
            "tool": "torch_compile",
            "mode": mode,
            "applied": False,
            "error": str(e),
        }

    return compiled, tokenizer, {
        "tool": "torch_compile",
        "mode": mode,
        "applied": True,
        "warning": "first-run will be slow due to compilation; tok/s measured after warmup",
    }
