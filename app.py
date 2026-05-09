"""ROCKET — HuggingFace Space app (replay mode).

Loads a JSONL trace from a real MI300X run and replays the optimization
journey: dramatic hero, animated chart, agent reasoning timeline.

Entry point for the HF Space. Streamlit framework with heavy custom CSS/SVG
to push past Streamlit's default look-and-feel.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import streamlit as st


# ============================================================================
# branding
# ============================================================================

st.set_page_config(
    page_title="ROCKET 🚀 — Autonomous Perf Researcher for AMD MI300X",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ROCKET_RED = "#ED1C24"
ROCKET_RED_BRIGHT = "#ff4d4d"
INK = "#08080c"
INK_2 = "#12121c"


# Heavy custom CSS — fights Streamlit's defaults to give us a real product look
CSS = f"""
<style>
  /* hide Streamlit chrome */
  #MainMenu {{ visibility: hidden; }}
  footer {{ visibility: hidden; }}
  header {{ visibility: hidden; }}
  .block-container {{ padding-top: 0 !important; padding-bottom: 0 !important; max-width: 100% !important; }}

  .stApp {{
    background:
      radial-gradient(circle at 80% 10%, rgba(237,28,36,0.12) 0%, transparent 40%),
      radial-gradient(circle at 10% 60%, rgba(237,28,36,0.08) 0%, transparent 40%),
      linear-gradient(180deg, {INK} 0%, {INK_2} 100%);
    color: #e9e9ee;
  }}
  body, .stApp {{ font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif; }}

  /* Override stMarkdown default <p> styles (this is what was killing the title) */
  [data-testid="stMarkdownContainer"] p {{ margin: 0; }}

  /* HERO */
  .hero {{
    padding: 60px 40px 40px 40px;
    border-bottom: 1px solid #1f1f2a;
    position: relative;
    overflow: hidden;
  }}
  .hero-tagline {{
    color: {ROCKET_RED};
    font-family: "SF Mono", "Menlo", monospace;
    letter-spacing: 6px;
    font-size: 12px;
    opacity: 0.9;
    margin-bottom: 14px;
    text-transform: uppercase;
  }}
  .hero-title {{
    font-weight: 900;
    font-size: 132px;
    line-height: 0.92;
    letter-spacing: -6px;
    margin: 0;
    background: linear-gradient(180deg, #ffffff 0%, #c9c9d4 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    text-shadow: 0 0 80px rgba(237,28,36,0.25);
  }}
  .hero-title .rocket {{
    display: inline-block;
    -webkit-text-fill-color: initial;
    animation: float 2.6s ease-in-out infinite;
    margin-left: 12px;
    filter: drop-shadow(0 0 20px rgba(237,28,36,0.6));
  }}
  .hero-sub {{
    color: #b3b3c0;
    font-size: 22px;
    margin-top: 18px;
    max-width: 720px;
    line-height: 1.45;
  }}
  .hero-pill {{
    display: inline-block;
    padding: 6px 14px;
    border-radius: 999px;
    background: rgba(237,28,36,0.1);
    border: 1px solid rgba(237,28,36,0.4);
    color: {ROCKET_RED_BRIGHT};
    font-size: 12px;
    font-family: "SF Mono", "Menlo", monospace;
    letter-spacing: 1px;
    margin-right: 8px;
    margin-top: 22px;
  }}

  @keyframes float {{
    0%, 100% {{ transform: translateY(0) rotate(-12deg); }}
    50% {{ transform: translateY(-12px) rotate(-12deg); }}
  }}
  @keyframes fadeUp {{
    0% {{ opacity: 0; transform: translateY(20px); }}
    100% {{ opacity: 1; transform: translateY(0); }}
  }}
  @keyframes glowPulse {{
    0%, 100% {{ text-shadow: 0 0 30px rgba(237,28,36,0.5); }}
    50% {{ text-shadow: 0 0 60px rgba(237,28,36,0.9); }}
  }}

  /* SPEEDUP HERO STAT */
  .stat-row {{
    display: flex;
    align-items: stretch;
    padding: 50px 40px;
    gap: 40px;
    border-bottom: 1px solid #1f1f2a;
  }}
  .speedup-mega {{
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 30px;
    border-radius: 24px;
    background:
      radial-gradient(circle at 30% 30%, rgba(237,28,36,0.18) 0%, transparent 60%),
      linear-gradient(135deg, #15151f 0%, #0a0a14 100%);
    border: 1px solid rgba(237,28,36,0.3);
    position: relative;
    overflow: hidden;
  }}
  .speedup-label {{
    color: #9a9aa8;
    font-family: "SF Mono", monospace;
    letter-spacing: 4px;
    font-size: 12px;
    margin-bottom: 8px;
  }}
  .speedup-value {{
    font-size: 220px;
    font-weight: 900;
    line-height: 0.9;
    letter-spacing: -10px;
    color: #fff;
    background: linear-gradient(135deg, #ffffff 0%, {ROCKET_RED} 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: glowPulse 3s ease-in-out infinite;
  }}
  .speedup-caption {{
    color: #b3b3c0;
    font-size: 18px;
    margin-top: 16px;
    line-height: 1.4;
  }}
  .speedup-caption b {{ color: {ROCKET_RED}; }}

  .stat-side {{
    flex: 0 0 320px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }}
  .stat-card {{
    flex: 1;
    background: #15151f;
    border: 1px solid #2a2a3a;
    border-radius: 14px;
    padding: 18px 22px;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }}
  .stat-card-label {{
    color: #9a9aa8;
    font-size: 11px;
    letter-spacing: 2.5px;
    text-transform: uppercase;
    margin-bottom: 6px;
  }}
  .stat-card-value {{
    color: #fff;
    font-size: 32px;
    font-weight: 800;
    letter-spacing: -1px;
  }}
  .stat-card-delta {{
    color: {ROCKET_RED};
    font-size: 13px;
    margin-top: 4px;
    font-family: "SF Mono", monospace;
  }}

  /* SECTION */
  .section {{
    padding: 50px 40px;
    border-bottom: 1px solid #1f1f2a;
  }}
  .section-eyebrow {{
    color: {ROCKET_RED};
    font-family: "SF Mono", monospace;
    letter-spacing: 4px;
    font-size: 11px;
    text-transform: uppercase;
    margin-bottom: 8px;
  }}
  .section-title {{
    color: #fff;
    font-size: 38px;
    font-weight: 800;
    letter-spacing: -1px;
    margin-bottom: 12px;
  }}
  .section-sub {{
    color: #9a9aa8;
    font-size: 17px;
    max-width: 680px;
    margin-bottom: 28px;
  }}

  /* TIMELINE (agent reasoning) */
  .tl-step {{
    background: linear-gradient(90deg, rgba(237,28,36,0.04) 0%, transparent 50%);
    border-left: 3px solid {ROCKET_RED};
    border-radius: 0 12px 12px 0;
    padding: 18px 22px;
    margin-bottom: 12px;
    animation: fadeUp 0.5s ease-out;
  }}
  .tl-step.reverted {{
    border-left-color: #fbbf24;
    opacity: 0.65;
  }}
  .tl-head {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }}
  .tl-tool {{
    font-family: "SF Mono", monospace;
    font-size: 14px;
    color: #fff;
    font-weight: 600;
  }}
  .tl-tool .badge {{
    background: rgba(237,28,36,0.15);
    color: {ROCKET_RED_BRIGHT};
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 11px;
    margin-right: 8px;
  }}
  .tl-tool .badge.warn {{ background: rgba(251,191,36,0.15); color: #fbbf24; }}
  .tl-result {{
    font-family: "SF Mono", monospace;
    font-size: 13px;
    color: {ROCKET_RED};
  }}
  .tl-result.warn {{ color: #fbbf24; }}
  .tl-reasoning {{
    color: #cfcfd6;
    font-size: 15px;
    line-height: 1.5;
    font-style: italic;
    margin: 8px 0;
  }}
  .tl-meta {{
    color: #6a6a78;
    font-size: 12px;
    font-family: "SF Mono", monospace;
  }}

  /* tools grid */
  .tools-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    gap: 14px;
    margin-top: 24px;
  }}
  .tool-card {{
    background: #12121c;
    border: 1px solid #2a2a3a;
    border-radius: 14px;
    padding: 18px;
  }}
  .tool-card-icon {{
    font-size: 24px;
    margin-bottom: 8px;
  }}
  .tool-card-name {{
    color: #fff;
    font-family: "SF Mono", monospace;
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 6px;
  }}
  .tool-card-desc {{
    color: #9a9aa8;
    font-size: 13px;
    line-height: 1.4;
  }}

  /* cta footer */
  .cta {{
    text-align: center;
    padding: 60px 40px;
    background: radial-gradient(circle at 50% 50%, rgba(237,28,36,0.1) 0%, transparent 50%);
  }}
  .cta-title {{ font-size: 36px; font-weight: 800; color: #fff; letter-spacing: -1px; }}
  .cta-sub {{ color: #9a9aa8; font-size: 16px; margin-top: 8px; }}
  .cta-row {{ margin-top: 22px; display: flex; justify-content: center; gap: 12px; flex-wrap: wrap; }}
  .cta-btn {{
    display: inline-block;
    padding: 12px 22px;
    border-radius: 10px;
    background: {ROCKET_RED};
    color: #fff !important;
    text-decoration: none !important;
    font-weight: 600;
    font-size: 14px;
    transition: transform 0.2s, box-shadow 0.2s;
  }}
  .cta-btn:hover {{ transform: translateY(-2px); box-shadow: 0 8px 30px rgba(237,28,36,0.4); }}
  .cta-btn.ghost {{ background: transparent; border: 1px solid #2a2a3a; color: #cfcfd6 !important; }}

  /* slider tweaks */
  div[data-baseweb="slider"] > div > div > div {{
    background: {ROCKET_RED} !important;
  }}
  /* primary button */
  .stButton button[kind="primary"] {{
    background: {ROCKET_RED} !important;
    border: none !important;
    font-weight: 600 !important;
  }}
  .stButton button[kind="primary"]:hover {{
    background: {ROCKET_RED_BRIGHT} !important;
  }}
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)


# ============================================================================
# load trace
# ============================================================================

DEFAULT_TRACE = Path(__file__).parent / "demo" / "sample_run.jsonl"


@st.cache_data
def load_trace(path_str: str):
    path = Path(path_str)
    if not path.exists():
        return None
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


events = load_trace(str(DEFAULT_TRACE))
if events is None:
    st.error(f"No trace at {DEFAULT_TRACE}.")
    st.stop()

baseline_event = next((e for e in events if e["event"] == "baseline"), None)
iter_events = [e for e in events if e["event"] == "iteration"]
summary_event = next((e for e in events if e["event"] == "summary"), None)

baseline_tok_s = baseline_event["result"]["tokens_per_second"]
device_label = baseline_event["result"]["device_label"]
model_id = baseline_event["result"]["model_id"]
peak_mem_mb = baseline_event["result"].get("peak_memory_mb") or 0
final_tok_s = (
    summary_event["report"]["final_tok_s"] if summary_event else baseline_tok_s
)
speedup = final_tok_s / baseline_tok_s if baseline_tok_s else 1.0
n_iters = len(iter_events)
n_kept = sum(1 for e in iter_events if e["iteration"]["accepted"])


# ============================================================================
# HERO
# ============================================================================

st.markdown(
    f"""
    <div class="hero">
      <div class="hero-tagline">// AMD x LABLAB · AI AGENTS · MI300X</div>
      <h1 class="hero-title">ROCKET<span class="rocket">🚀</span></h1>
      <p class="hero-sub">
        An autonomous agent that makes any model
        <b style="color:{ROCKET_RED};">faster on AMD MI300X</b> &mdash;
        by itself. Profile, hypothesize, optimize, validate, repeat.
      </p>
      <div>
        <span class="hero-pill">QWEN PLANNER</span>
        <span class="hero-pill">ROCm 7.0</span>
        <span class="hero-pill">MI300X · 192GB HBM3</span>
        <span class="hero-pill">SOLO BUILD · 24H</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================================
# SPEEDUP HERO STAT
# ============================================================================

st.markdown(
    f"""
    <div class="stat-row">
      <div class="speedup-mega">
        <div class="speedup-label">MEASURED SPEEDUP &nbsp;·&nbsp; AMD MI300X</div>
        <div class="speedup-value">{speedup:.2f}×</div>
        <div class="speedup-caption">
          <b>{baseline_tok_s:.1f}</b> &rarr; <b>{final_tok_s:.1f}</b> tokens/sec
          on <b>{model_id.split('/')[-1]}</b>
          &nbsp;·&nbsp; {n_kept} of {n_iters} optimizations kept by the agent
        </div>
      </div>
      <div class="stat-side">
        <div class="stat-card">
          <div class="stat-card-label">target hardware</div>
          <div class="stat-card-value" style="font-size: 22px;">AMD Instinct MI300X</div>
          <div class="stat-card-delta">192 GB HBM3 · ROCm 7.0</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-label">target model</div>
          <div class="stat-card-value" style="font-size: 18px;">{model_id}</div>
          <div class="stat-card-delta">peak {peak_mem_mb:.0f} MB on baseline</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-label">planner brain</div>
          <div class="stat-card-value" style="font-size: 22px;">Qwen2.5-7B</div>
          <div class="stat-card-delta">running locally on the same MI300X</div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================================
# JOURNEY (chart + replay)
# ============================================================================

st.markdown(
    """
    <div class="section">
      <div class="section-eyebrow">REPLAY</div>
      <div class="section-title">🎬 The optimization journey</div>
      <div class="section-sub">
        Each point is one decision the agent made. Red = kept (improved tok/s).
        Yellow X = tried and reverted (didn't beat the threshold).
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

play_col, slider_col, _ = st.columns([1, 4, 1])
with play_col:
    autoplay = st.button("▶︎ Replay", type="primary", use_container_width=True)
with slider_col:
    step = st.slider(
        "step",
        min_value=0,
        max_value=n_iters,
        value=n_iters,
        label_visibility="collapsed",
    )

if autoplay:
    step = n_iters

# Build chart data
rows = [
    {"step": 0, "tok_s": baseline_tok_s, "kept_tok_s": baseline_tok_s,
     "tool": "baseline", "kept": True, "reasoning": "starting point"}
]
running = baseline_tok_s
for i, e in enumerate(iter_events[:step], 1):
    it = e["iteration"]
    if it["accepted"]:
        running = it["post_tok_s"]
    rows.append({
        "step": i,
        "tok_s": running,
        "candidate_tok_s": it["post_tok_s"],
        "kept_tok_s": running if it["accepted"] else None,
        "tool": it["decision"]["tool"],
        "reasoning": it["decision"]["reasoning"],
        "kept": it["accepted"],
    })

df = pd.DataFrame(rows)

import plotly.graph_objects as go

fig = go.Figure()

# kept trajectory (the staircase that climbs)
fig.add_trace(go.Scatter(
    x=df["step"],
    y=df["tok_s"],
    mode="lines",
    line=dict(color=ROCKET_RED, width=4, shape="spline", smoothing=0.4),
    fill="tozeroy",
    fillcolor="rgba(237,28,36,0.08)",
    name="cumulative best",
    hovertemplate="step %{x}<br>%{y:.1f} tok/s<extra></extra>",
))

# accepted points (red filled)
kept_df = df[df["kept"] == True]
fig.add_trace(go.Scatter(
    x=kept_df["step"], y=kept_df["tok_s"],
    mode="markers+text",
    marker=dict(size=16, color=ROCKET_RED, line=dict(color="#fff", width=2)),
    text=[f"<b>{t}</b>" for t in kept_df["tool"]],
    textposition="top center",
    textfont=dict(family="SF Mono", size=11, color="#fff"),
    name="kept",
    hovertemplate="<b>%{text}</b><br>%{y:.1f} tok/s<extra></extra>",
))

# rejected points (yellow X)
rej_df = df[(df["kept"] == False)]
if len(rej_df) > 0:
    fig.add_trace(go.Scatter(
        x=rej_df["step"], y=rej_df["candidate_tok_s"],
        mode="markers+text",
        marker=dict(size=14, color="#fbbf24", symbol="x", line=dict(width=2)),
        text=[f"<i>{t} (reverted)</i>" for t in rej_df["tool"]],
        textposition="bottom center",
        textfont=dict(family="SF Mono", size=10, color="#fbbf24"),
        name="reverted",
        hovertemplate="<b>%{text}</b><br>%{y:.1f} tok/s<extra></extra>",
    ))

fig.update_layout(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    height=440,
    margin=dict(l=20, r=20, t=40, b=40),
    xaxis=dict(
        title=None,
        tickmode="linear", dtick=1,
        gridcolor="#1f1f2a", zerolinecolor="#1f1f2a",
        tickfont=dict(family="SF Mono", size=12, color="#9a9aa8"),
    ),
    yaxis=dict(
        title=dict(text="TOKENS / SECOND", font=dict(family="SF Mono", size=11, color="#9a9aa8")),
        gridcolor="#1f1f2a", zerolinecolor="#1f1f2a",
        tickfont=dict(family="SF Mono", size=12, color="#9a9aa8"),
    ),
    showlegend=False,
    hoverlabel=dict(bgcolor="#15151f", font_family="SF Mono", font_color="#fff",
                    bordercolor=ROCKET_RED),
)
st.plotly_chart(fig, use_container_width=True)


# ============================================================================
# AGENT REASONING TIMELINE
# ============================================================================

st.markdown(
    """
    <div class="section" style="border-bottom: none;">
      <div class="section-eyebrow">AGENT TRACE</div>
      <div class="section-title">🧠 What the agent was thinking</div>
      <div class="section-sub">
        Each step: the planner reads the profile, picks one tool from the bounded
        toolbox, applies it, and the validator either keeps or reverts.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

steps_html = ""
for i, e in enumerate(iter_events[:step], 1):
    it = e["iteration"]
    accepted = it["accepted"]
    cls = "" if accepted else " reverted"
    badge_cls = "" if accepted else " warn"
    res_cls = "" if accepted else " warn"
    icon = "✓ KEPT" if accepted else "↩ REVERTED"
    tool = it["decision"]["tool"]
    params = it["decision"]["params"]
    reasoning = it["decision"]["reasoning"]
    pre = it["pre_tok_s"]
    post = it["post_tok_s"]
    speedup_step = it["speedup_vs_prev"]
    cum = it["cumulative_speedup"]
    steps_html += f"""
    <div class="tl-step{cls}">
      <div class="tl-head">
        <div class="tl-tool"><span class="badge{badge_cls}">{icon}</span>{tool}({params})</div>
        <div class="tl-result{res_cls}">{speedup_step:.2f}× &nbsp; / &nbsp; cum {cum:.2f}×</div>
      </div>
      <div class="tl-reasoning">"{reasoning}"</div>
      <div class="tl-meta">{pre:.1f} → {post:.1f} tok/s</div>
    </div>
    """

st.markdown(f'<div style="padding: 0 40px 30px;">{steps_html}</div>', unsafe_allow_html=True)


# ============================================================================
# TOOLBOX SECTION
# ============================================================================

st.markdown(
    """
    <div class="section">
      <div class="section-eyebrow">TOOLBOX</div>
      <div class="section-title">🛠 The agent picks from these</div>
      <div class="section-sub">
        ROCKET doesn't write arbitrary code. The agent's job is to pick the right
        tool for the right hotspot, in the right order. A bounded search space
        means the agent has to be smart, not lucky.
      </div>
      <div class="tools-grid">
        <div class="tool-card">
          <div class="tool-card-icon">⚡</div>
          <div class="tool-card-name">dtype_cast</div>
          <div class="tool-card-desc">Cast model to bf16/fp16 — halves memory, ~2× throughput on MI300X.</div>
        </div>
        <div class="tool-card">
          <div class="tool-card-icon">⚙️</div>
          <div class="tool-card-name">torch_compile</div>
          <div class="tool-card-desc">Inductor-fused kernels via torch.compile. Best for stable shapes.</div>
        </div>
        <div class="tool-card">
          <div class="tool-card-icon">🎯</div>
          <div class="tool-card-name">sdpa_attention</div>
          <div class="tool-card-desc">Memory-efficient attention. Big win on attention-bound workloads.</div>
        </div>
        <div class="tool-card">
          <div class="tool-card-icon">📐</div>
          <div class="tool-card-name">input_padding</div>
          <div class="tool-card-desc">Pad shapes to GPU-friendly multiples (128/256). Free perf when shapes are odd.</div>
        </div>
        <div class="tool-card">
          <div class="tool-card-icon">💾</div>
          <div class="tool-card-name">kv_cache_config</div>
          <div class="tool-card-desc">Enable KV-caching — turns O(n²) into O(n) on autoregressive generation.</div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================================
# CTA
# ============================================================================

st.markdown(
    f"""
    <div class="cta">
      <div class="cta-title">An autopilot for AMD performance.</div>
      <div class="cta-sub">If you got this far, drop a like on this Space — it counts toward the HF community prize.</div>
      <div class="cta-row">
        <a class="cta-btn" href="https://lablab.ai/ai-hackathons/amd-developer" target="_blank">View on lablab.ai →</a>
        <a class="cta-btn ghost" href="https://twitter.com/intent/tweet?text=ROCKET%20%E2%80%94%20an%20autonomous%20agent%20that%20makes%20models%20faster%20on%20AMD%20MI300X.%20%F0%9F%9A%80&hashtags=AMD,MI300X,ROCm" target="_blank">Share on Twitter</a>
      </div>
      <div style="margin-top: 40px; color: #6a6a78; font-size: 12px; font-family: 'SF Mono', monospace;">
        BUILT SOLO · AMD x LABLAB.AI DEVELOPER HACKATHON · MAY 2026
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
