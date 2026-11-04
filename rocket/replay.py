"""Re-apply previously accepted optimizations to a freshly loaded model."""
from __future__ import annotations

from typing import Any, Callable, Mapping


def replay_accepted(
    toolbox: Mapping[str, Callable],
    model: Any,
    tokenizer: Any,
    history: list[dict[str, Any]],
):
    """Apply every accepted entry in `history`, in order, and return (model, tokenizer).

    Tools may return a new model object (e.g. `torch_compile` returns a
    compiled wrapper), so the return value of each tool must be carried
    forward rather than discarded.
    """
    for h in history:
        if h.get("accepted"):
            model, tokenizer, _ = toolbox[h["tool"]](
                model, tokenizer, **h.get("params", {})
            )
    return model, tokenizer
