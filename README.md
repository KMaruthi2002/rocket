---
title: ROCKET ⚡ AI Scientist for AMD Performance
sdk: static
pinned: true
license: apache-2.0
short_description: An AI scientist whose only research domain is making models faster on AMD MI300X.
---

# ⚡ ROCKET

> An AI scientist whose only research domain is making models faster on AMD MI300X.

ROCKET is a multi-agent system that takes a PyTorch model, profiles it on AMD MI300X, hypothesizes which optimizations will help, applies them, validates correctness, and measures the speedup completely on its own. Output: a measured speedup, a research log, and a PR-ready diff.

**Real result on real hardware.** Qwen2.5-7B-Instruct on AMD Instinct MI300X (ROCm 7), batch=8, prompt 256 + new 512: baseline 62.59 tok/s → final 183.47 tok/s. **2.93× honest speedup.** The agent tried 5 tools and kept 1 (bf16 cast); rejected the 4 that didn't beat the validation threshold.

**Built for the AMD x lablab.ai Developer Hackathon (May 2026).**

---

## What makes ROCKET different

The hackathon is full of great agentic systems for medical triage, code translation, GPU debugging. ROCKET targets a different problem: **"how do I make this model faster on AMD?"** is the first question every developer asks, and ROCKET answers it autonomously.

- **ROCmPort AI** translates CUDA code → ROCm code.
- **ReplayLab** records GPU experiments and recovers from failures.
- **ROCKET** makes the model *fast*. Different verb, different value.

## Architecture

```
                ┌──────────────┐
       ┌──────▶│  Profiler    │  torch.profiler / rocprof
       │       └──────┬───────┘
       │              │  hotspot summary
       │              ▼
       │       ┌──────────────┐
       │       │  Planner     │  Qwen2.5-7B-Instruct on MI300X
       │       └──────┬───────┘  (vLLM endpoint)
       │              │  picks tool from bounded toolbox
       │              ▼
       │       ┌──────────────┐
       │       │  Implementer │  applies one of 5 transformations
       │       └──────┬───────┘
       │              │
       │              ▼
       │       ┌──────────────┐
       └───────│  Validator   │  re-bench + correctness check
               └──────────────┘  keep if speedup ≥ threshold
```

### The bounded toolbox

ROCKET doesn't write arbitrary code. The agent picks from a curated set of high-leverage transformations:

| Tool | What it does |
|---|---|
| `dtype_cast` | Cast model to bf16/fp16 : halves memory, ~2× throughput on MI300X |
| `torch_compile` | Inductor-fused kernels via `torch.compile` |
| `sdpa_attention` | Switch to PyTorch's fused scaled-dot-product attention |
| `input_padding` | Pad shapes to GPU-friendly multiples (128/256) |
| `kv_cache_config` | Ensure KV-caching is enabled — 2-4× on autoregressive generation |

The bounded search space is the point: the agent's job is *which transformation to try, in what order, with which params*, given the profile.

## Tech stack

- **Hardware:** AMD Instinct MI300X (192 GB HBM3) via AMD Developer Cloud
- **Runtime:** ROCm 7.0 + PyTorch 2.6.0
- **Planner brain:** Qwen2.5-7B-Instruct (served via vLLM on the same MI300X)
- **Target model:** Qwen2.5-1.5B-Instruct (dev) / Qwen2.5-7B-Instruct (demo)
- **Frontend:** Streamlit (this Space)
- **Profiling:** `torch.profiler`

## Run it

```bash
# On an MI300X droplet (AMD Developer Cloud, ROCm 7.0 + PyTorch 2.6.0 image)
git clone <repo>
cd rocket
pip install -r requirements.txt

# Start a local Qwen vLLM server (the planner brain)
vllm serve Qwen/Qwen2.5-7B-Instruct --port 8000 &

# Run the orchestrator
python -m rocket.orchestrator --model Qwen/Qwen2.5-1.5B-Instruct --iterations 5
```

The trace is written to `logs/run.jsonl` and is what powers this Space's replay view.

## What's in this Space

This is a **replay** of an actual ROCKET run on AMD MI300X. HF Space free-tier doesn't have MI300X, so the agent ran on the droplet, the trace is shipped here, and the Space animates the journey: live tok/s chart, agent reasoning, decision log.

If you'd like to like this Space ❤️, that helps with the HF community prize at the hackathon.

## Built by

Maruthi Kunchala, hacking through the night for the AMD Developer Hackathon. Repo and team page on lablab.ai.
