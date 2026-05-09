"""KV cache configuration."""
from __future__ import annotations


def apply_kv_cache_config(model, tokenizer, *, enabled: bool = True, **_):
    """Ensure use_cache is enabled in generation config.

    For autoregressive generation, KV cache turns O(n^2) into O(n) compute.
    HF's `use_cache=False` (e.g., during training) is sometimes left on by accident.
    """
    cfg = model.config
    prev = getattr(cfg, "use_cache", None)

    cfg.use_cache = enabled
    if hasattr(model, "generation_config"):
        model.generation_config.use_cache = enabled

    return model, tokenizer, {
        "tool": "kv_cache_config",
        "applied": True,
        "from": prev,
        "to": enabled,
        "note": "expect 2-4x speedup on long-context generation when previously disabled",
    }
