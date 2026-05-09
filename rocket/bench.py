"""
ROCKET benchmark harness.

Device-agnostic tok/s + memory + latency measurement for HF causal LMs.
Works on CUDA, ROCm (treated as CUDA by torch), MPS, and CPU.
"""
from __future__ import annotations

import gc
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def detect_device() -> tuple[str, str]:
    """Return (device, label). Label is human-readable for logs/demo."""
    if torch.cuda.is_available():
        # On ROCm builds, torch.cuda.* still works and reports HIP devices.
        name = torch.cuda.get_device_name(0)
        is_rocm = bool(getattr(torch.version, "hip", None))
        return "cuda", f"{'ROCm' if is_rocm else 'CUDA'}: {name}"
    if torch.backends.mps.is_available():
        return "mps", "Apple MPS"
    return "cpu", "CPU"


@dataclass
class BenchResult:
    model_id: str
    device: str
    device_label: str
    dtype: str
    batch: int
    prompt_tokens: int
    new_tokens: int
    runs: int
    warmup: int
    total_seconds: float
    tokens_per_second: float
    peak_memory_mb: float | None
    output_hash: str  # for correctness check across optimizations
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _hash_logits_proxy(model, tokenizer, device: str, dtype: torch.dtype) -> str:
    """Cheap correctness fingerprint: greedy-decode 32 tokens from a fixed prompt
    and hash the IDs. If an optimization changes outputs catastrophically,
    this fingerprint diverges and we can flag it."""
    prompt = "The capital of France is"
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=32,
            do_sample=False,
            num_beams=1,
            pad_token_id=tokenizer.eos_token_id,
        )
    ids = out[0].tolist()
    # rolling hash
    h = 1469598103934665603
    for i in ids:
        h ^= int(i) & 0xFFFFFFFFFFFFFFFF
        h = (h * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


def benchmark(
    model,
    tokenizer,
    device: str,
    *,
    batch: int = 1,
    prompt_tokens: int = 128,
    new_tokens: int = 128,
    runs: int = 3,
    warmup: int = 1,
    notes: str = "",
) -> BenchResult:
    """Measure tokens/sec for greedy generation. Returns BenchResult."""
    dtype = next(model.parameters()).dtype
    model.eval()

    # Build a synthetic prompt of the requested length
    pad = tokenizer.eos_token or "<|endoftext|>"
    prompt = (pad + " ") * prompt_tokens
    enc = tokenizer(
        [prompt] * batch,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=prompt_tokens,
    ).to(device)

    # reset memory stats if CUDA/ROCm
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()

    # warmup
    for _ in range(warmup):
        with torch.no_grad():
            model.generate(
                **enc,
                max_new_tokens=new_tokens,
                do_sample=False,
                num_beams=1,
                pad_token_id=tokenizer.eos_token_id,
            )
        if device == "cuda":
            torch.cuda.synchronize()

    # timed runs
    t0 = time.perf_counter()
    total_new = 0
    for _ in range(runs):
        with torch.no_grad():
            out = model.generate(
                **enc,
                max_new_tokens=new_tokens,
                do_sample=False,
                num_beams=1,
                pad_token_id=tokenizer.eos_token_id,
            )
        # tokens generated this run = (output_len - input_len) * batch
        gen = (out.shape[1] - enc["input_ids"].shape[1]) * batch
        total_new += gen
    if device == "cuda":
        torch.cuda.synchronize()
    elapsed = time.perf_counter() - t0
    tok_per_s = total_new / elapsed if elapsed > 0 else 0.0

    peak_mb = None
    if device == "cuda":
        peak_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)

    output_hash = _hash_logits_proxy(model, tokenizer, device, dtype)

    return BenchResult(
        model_id=model.config._name_or_path,
        device=device,
        device_label=detect_device()[1],
        dtype=str(dtype).replace("torch.", ""),
        batch=batch,
        prompt_tokens=prompt_tokens,
        new_tokens=new_tokens,
        runs=runs,
        warmup=warmup,
        total_seconds=round(elapsed, 4),
        tokens_per_second=round(tok_per_s, 2),
        peak_memory_mb=round(peak_mb, 1) if peak_mb is not None else None,
        output_hash=output_hash,
        notes=notes,
    )


def load_model(model_id: str, dtype: str = "bf16", device: str = "cuda"):
    """Load HF causal LM with a chosen dtype and place on device."""
    dtype_map = {
        "fp32": torch.float32,
        "fp16": torch.float16,
        "bf16": torch.bfloat16,
    }
    torch_dtype = dtype_map[dtype]

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch_dtype,
        low_cpu_mem_usage=True,
    ).to(device)
    return model, tokenizer


def free(*objs):
    for o in objs:
        del o
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def save_result(result: BenchResult, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(result.to_dict()) + "\n")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt2-medium")
    ap.add_argument("--dtype", default="fp32", choices=["fp32", "fp16", "bf16"])
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--prompt-tokens", type=int, default=128)
    ap.add_argument("--new-tokens", type=int, default=128)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--out", default="logs/bench.jsonl")
    args = ap.parse_args()

    device, label = detect_device()
    print(f"[bench] device: {label}")

    model, tok = load_model(args.model, dtype=args.dtype, device=device)
    res = benchmark(
        model,
        tok,
        device,
        batch=args.batch,
        prompt_tokens=args.prompt_tokens,
        new_tokens=args.new_tokens,
        runs=args.runs,
        warmup=args.warmup,
        notes="baseline",
    )
    print(json.dumps(res.to_dict(), indent=2))
    save_result(res, args.out)
