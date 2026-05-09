"""ROCKET optimization toolbox.

Each tool is a pure function that takes (model, tokenizer, config) and returns
(model, tokenizer, info_dict). Tools are composable. Each is safely revertible
by reloading the model from its source.

The agent picks tools to apply based on the profile. The toolbox is bounded so
the agent has to make smart choices, not write arbitrary code.
"""
from .compile_tool import apply_torch_compile
from .dtype_tool import apply_dtype_cast
from .sdpa_tool import apply_sdpa_attention
from .padding_tool import apply_input_padding
from .kvcache_tool import apply_kv_cache_config

TOOLBOX = {
    "dtype_cast": apply_dtype_cast,
    "torch_compile": apply_torch_compile,
    "sdpa_attention": apply_sdpa_attention,
    "input_padding": apply_input_padding,
    "kv_cache_config": apply_kv_cache_config,
}

TOOL_DESCRIPTIONS = {
    "dtype_cast": (
        "Cast model parameters to a lower-precision dtype (fp32 -> bf16/fp16). "
        "Halves memory and roughly doubles arithmetic throughput on MI300X. "
        "Risk: small numerical drift; bf16 is safer than fp16."
    ),
    "torch_compile": (
        "Wrap the forward with torch.compile(mode=...). Fuses ops via Inductor; "
        "best for repeated shapes. Cold start cost. Modes: default, reduce-overhead, max-autotune."
    ),
    "sdpa_attention": (
        "Force HF model to use F.scaled_dot_product_attention (PyTorch's fused "
        "attention). On ROCm 7+, SDPA dispatches to memory-efficient kernels. "
        "Big win on attention-bound models with long contexts."
    ),
    "input_padding": (
        "Pad prompt sequence length to a GPU-friendly multiple (e.g., 128 or 256). "
        "Helps tensor-core / matrix-engine utilization. Free win when shapes are odd."
    ),
    "kv_cache_config": (
        "Configure KV cache: enable, set use_cache=True, optionally pre-allocate. "
        "Critical for autoregressive generation — turning this on can be 2-4x."
    ),
}

__all__ = ["TOOLBOX", "TOOL_DESCRIPTIONS"]
