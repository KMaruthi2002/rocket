"""ROCKET — autonomous performance researcher for AMD MI300X.

Pipeline:
    Profiler → Planner (Qwen) → Implementer (toolbox) → Validator → loop

The agent reads a model's profile, hypothesizes which optimization to try next
from a bounded toolbox, applies it, validates correctness, and keeps it if
performance improves. All on AMD MI300X.
"""
__version__ = "0.1.0"
