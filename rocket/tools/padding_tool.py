"""Pad input sequence length to a GPU-friendly multiple."""
from __future__ import annotations


class PaddingConfig:
    """Sentinel config object the bench harness can read.

    Apply by attaching to model: `model._rocket_pad_to = 128`.
    The bench harness checks for this attribute and pads prompt accordingly.
    """

    pass


def apply_input_padding(model, tokenizer, *, multiple: int = 128, **_):
    """Mark the model so prompt length is padded to `multiple`.

    The bench harness reads `model._rocket_pad_to` to apply padding.
    Typical good values on MI300X: 128 or 256 (matches tile sizes).
    """
    if multiple not in (32, 64, 128, 256, 512):
        return model, tokenizer, {
            "tool": "input_padding",
            "applied": False,
            "error": f"multiple must be in {{32,64,128,256,512}}, got {multiple}",
        }

    setattr(model, "_rocket_pad_to", multiple)

    return model, tokenizer, {
        "tool": "input_padding",
        "applied": True,
        "multiple": multiple,
        "note": "bench harness will pad prompt up to next multiple",
    }
