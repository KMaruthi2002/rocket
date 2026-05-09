"""Cast model to a lower-precision dtype."""
from __future__ import annotations

import torch


_DTYPES = {
    "fp32": torch.float32,
    "bf16": torch.bfloat16,
    "fp16": torch.float16,
}


def apply_dtype_cast(model, tokenizer, *, target: str = "bf16", **_):
    """Cast all parameters and buffers to `target` dtype.

    Returns (model, tokenizer, info).
    """
    if target not in _DTYPES:
        raise ValueError(f"unknown dtype {target!r}; must be one of {list(_DTYPES)}")
    target_dt = _DTYPES[target]

    current = next(model.parameters()).dtype
    if current == target_dt:
        return model, tokenizer, {
            "tool": "dtype_cast",
            "target": target,
            "applied": False,
            "reason": "already at target dtype",
        }

    model.to(target_dt)
    return model, tokenizer, {
        "tool": "dtype_cast",
        "target": target,
        "applied": True,
        "from": str(current).replace("torch.", ""),
        "to": target,
    }
