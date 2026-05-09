"""Force HF model to use F.scaled_dot_product_attention."""
from __future__ import annotations


def apply_sdpa_attention(model, tokenizer, **_):
    """Switch HF model's attention implementation to SDPA.

    PyTorch's scaled_dot_product_attention dispatches to memory-efficient kernels.
    On ROCm 7+, this hits hipBLASLt / memory-efficient backends — a big win on
    attention-bound workloads.
    """
    cfg = model.config

    # transformers 4.36+ supports config.attn_implementation
    prev = getattr(cfg, "_attn_implementation", None) or getattr(
        cfg, "attn_implementation", None
    )
    if prev == "sdpa":
        return model, tokenizer, {
            "tool": "sdpa_attention",
            "applied": False,
            "reason": "already using SDPA",
        }

    try:
        cfg._attn_implementation = "sdpa"
        if hasattr(cfg, "attn_implementation"):
            cfg.attn_implementation = "sdpa"
    except Exception as e:
        return model, tokenizer, {
            "tool": "sdpa_attention",
            "applied": False,
            "error": str(e),
        }

    return model, tokenizer, {
        "tool": "sdpa_attention",
        "applied": True,
        "from": prev or "default",
        "to": "sdpa",
        "note": "may require re-loading the model for some architectures",
    }
