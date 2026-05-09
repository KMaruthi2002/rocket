#!/usr/bin/env bash
# ROCKET — droplet bootstrap.
# Run this on the AMD Developer Cloud MI300X droplet (ROCm 7.0 + PyTorch 2.6.0 image)
# right after SSH'ing in.
set -euo pipefail

echo "==> ROCKET droplet bootstrap"
echo "==> hostname: $(hostname)"
echo "==> rocm-smi (sanity check)"
rocm-smi --showproductname || echo "rocm-smi not on PATH; continuing"

echo "==> python: $(python3 --version)"
echo "==> torch: $(python3 -c 'import torch, torch.version as v; print(torch.__version__, "hip=", v.hip)')"

# Workspace
mkdir -p ~/rocket
cd ~/rocket

# pip deps (the Quick Start image has torch/transformers; we add the rest)
pip install --quiet \
  "transformers>=4.46" "accelerate>=1.0" \
  "openai>=1.50" "anthropic>=0.40" \
  "streamlit>=1.39" "plotly>=5.20" \
  "rich" "typer" "python-dotenv" "pydantic>=2"

# Sanity baseline on tiny model (5 sec, validates GPU works)
python3 - <<'PY'
import torch
print("[bootstrap] cuda available:", torch.cuda.is_available())
print("[bootstrap] device:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "n/a")
print("[bootstrap] hbm:",
      torch.cuda.get_device_properties(0).total_memory // (1024**3), "GB"
      if torch.cuda.is_available() else "n/a")
PY

echo "==> ready. Next:"
echo "    1) git clone <your-repo>  OR  scp the rocket/ folder up"
echo "    2) Optional: vllm serve Qwen/Qwen2.5-7B-Instruct --port 8000 &  (planner brain)"
echo "    3) python -m rocket.orchestrator --model Qwen/Qwen2.5-1.5B-Instruct --offline"
echo "       (use --offline first; swap to LLM planner once vLLM is up)"
