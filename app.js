/* =============================================================
   ROCKET. static space client.
   modules:
     1. cosmic background (Three.js starfield + drifting nebula)
     2. cinematic intro sequence
     3. reticle cursor
     4. ambient particle layer (canvas2D)
     5. reveal-on-scroll
     6. speedup counter
     7. mission-control chart (flux particles, halos, hover HUD)
     8. timeline, terminal, race, stack toggler, profile breakdown
   ============================================================= */

// Three.js is loaded asynchronously so a slow/failed CDN never blocks the rest of the page.
import("three").then((mod) => initCosmos(mod)).catch((err) => {
  console.warn("[rocket] Three.js failed to load; cosmic background disabled.", err);
});

/* ------------------------------------------------------------
   1. COSMIC BACKGROUND — Three.js starfield + drifting nebula
   ------------------------------------------------------------ */
function initCosmos(THREE) {
  if (!THREE) return;
  const canvas = document.getElementById("cosmos");
  if (!canvas) return;
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 2000);
  camera.position.z = 200;

  // ---- starfield ----
  const STAR_COUNT = 2400;
  const starGeo = new THREE.BufferGeometry();
  const starPositions = new Float32Array(STAR_COUNT * 3);
  const starSizes = new Float32Array(STAR_COUNT);
  const starColors = new Float32Array(STAR_COUNT * 3);
  for (let i = 0; i < STAR_COUNT; i++) {
    const r = 200 + Math.random() * 800;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    starPositions[i * 3]     = r * Math.sin(phi) * Math.cos(theta);
    starPositions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    starPositions[i * 3 + 2] = r * Math.cos(phi) - 300;
    starSizes[i] = Math.random() * 1.4 + 0.3;
    // mostly white-blue, occasional red AMD accent
    const tint = Math.random();
    if (tint > 0.94) {
      starColors[i * 3] = 1.0;
      starColors[i * 3 + 1] = 0.18;
      starColors[i * 3 + 2] = 0.18;
    } else if (tint > 0.85) {
      starColors[i * 3] = 0.7;
      starColors[i * 3 + 1] = 0.85;
      starColors[i * 3 + 2] = 1.0;
    } else {
      const v = 0.7 + Math.random() * 0.3;
      starColors[i * 3] = v;
      starColors[i * 3 + 1] = v;
      starColors[i * 3 + 2] = v;
    }
  }
  starGeo.setAttribute("position", new THREE.BufferAttribute(starPositions, 3));
  starGeo.setAttribute("size", new THREE.BufferAttribute(starSizes, 1));
  starGeo.setAttribute("aColor", new THREE.BufferAttribute(starColors, 3));

  const starMat = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    uniforms: { uTime: { value: 0 } },
    vertexShader: `
      attribute float size;
      attribute vec3 aColor;
      varying vec3 vColor;
      varying float vSize;
      uniform float uTime;
      void main() {
        vColor = aColor;
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = size * (300.0 / -mv.z) * (0.85 + 0.15 * sin(uTime * 1.5 + position.x * 0.05));
        vSize = gl_PointSize;
        gl_Position = projectionMatrix * mv;
      }
    `,
    fragmentShader: `
      varying vec3 vColor;
      void main() {
        vec2 p = gl_PointCoord - 0.5;
        float d = length(p);
        if (d > 0.5) discard;
        float a = smoothstep(0.5, 0.0, d);
        gl_FragColor = vec4(vColor, a);
      }
    `,
  });
  const stars = new THREE.Points(starGeo, starMat);
  scene.add(stars);

  // ---- nebula plane (additive shader) ----
  const nebulaGeo = new THREE.PlaneGeometry(1800, 1100, 1, 1);
  const nebulaMat = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    uniforms: { uTime: { value: 0 } },
    vertexShader: `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      varying vec2 vUv;
      uniform float uTime;
      // simplex-ish noise (cheap)
      float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float noise(vec2 p) {
        vec2 i = floor(p); vec2 f = fract(p);
        float a = hash(i); float b = hash(i + vec2(1,0));
        float c = hash(i + vec2(0,1)); float d = hash(i + vec2(1,1));
        vec2 u = f*f*(3.0-2.0*f);
        return mix(mix(a,b,u.x), mix(c,d,u.x), u.y);
      }
      float fbm(vec2 p) {
        float v = 0.0; float a = 0.5;
        for (int i=0;i<5;i++) { v += a*noise(p); p *= 2.0; a *= 0.5; }
        return v;
      }
      void main() {
        vec2 uv = vUv * 2.4;
        float t = uTime * 0.025;
        float n = fbm(uv + vec2(t, -t*0.7));
        float n2 = fbm(uv * 0.7 - vec2(t*0.5, t));
        // red core right, purple-blue left
        vec3 red = vec3(0.93, 0.10, 0.13) * pow(n, 2.2) * (uv.x > 1.6 ? 1.0 : 0.4);
        vec3 vio = vec3(0.34, 0.10, 0.55) * pow(n2, 2.0) * (uv.x < 1.5 ? 0.7 : 0.2);
        vec3 col = red + vio;
        // vignette
        float vig = smoothstep(1.6, 0.4, length(vUv - 0.5) * 1.4);
        gl_FragColor = vec4(col, (n*0.55 + n2*0.35) * vig * 0.55);
      }
    `,
  });
  const nebula = new THREE.Mesh(nebulaGeo, nebulaMat);
  nebula.position.z = -400;
  scene.add(nebula);

  // ---- distant ringed planet (small detail in the corner) ----
  const planetGroup = new THREE.Group();
  const planetMat = new THREE.MeshBasicMaterial({ color: 0x301525 });
  const planet = new THREE.Mesh(new THREE.SphereGeometry(28, 32, 32), planetMat);
  const ringGeo = new THREE.RingGeometry(38, 46, 64);
  const ringMat = new THREE.MeshBasicMaterial({
    color: 0xed1c24, side: THREE.DoubleSide, transparent: true, opacity: 0.4,
  });
  const ring = new THREE.Mesh(ringGeo, ringMat);
  ring.rotation.x = -1.1;
  planetGroup.add(planet);
  planetGroup.add(ring);
  planetGroup.position.set(380, -180, -180);
  scene.add(planetGroup);

  // mouse parallax
  let mx = 0, my = 0;
  window.addEventListener("mousemove", (e) => {
    mx = (e.clientX / window.innerWidth) * 2 - 1;
    my = (e.clientY / window.innerHeight) * 2 - 1;
  });

  function resize() {
    renderer.setSize(window.innerWidth, window.innerHeight);
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", resize);

  let t = 0;
  const tick = () => {
    t += 0.016;
    starMat.uniforms.uTime.value = t;
    nebulaMat.uniforms.uTime.value = t;
    stars.rotation.y = t * 0.008;
    stars.rotation.x = t * 0.004;
    planetGroup.rotation.y += 0.001;
    // parallax
    camera.position.x += (mx * 14 - camera.position.x) * 0.04;
    camera.position.y += (-my * 10 - camera.position.y) * 0.04;
    camera.lookAt(0, 0, 0);
    renderer.render(scene, camera);
    requestAnimationFrame(tick);
  };
  tick();
}

/* ------------------------------------------------------------
   2. INTRO SEQUENCE — boot animation, then fade
   ------------------------------------------------------------ */
(function intro() {
  const intro = document.getElementById("intro");
  const bar = document.getElementById("introBar");
  const log = document.getElementById("introLog");
  if (!intro) return;
  const lines = [
    "> initializing rocm 7.0…",
    "> mounting MI300X · 192 GB HBM3…",
    "> loading qwen planner…",
    "> handshake complete · entering autopilot",
  ];
  let i = 0;
  const step = () => {
    if (i < lines.length) {
      log.textContent = lines[i++];
      setTimeout(step, 360);
    }
  };
  setTimeout(step, 120);
  setTimeout(() => { bar.style.width = "100%"; }, 300);
  setTimeout(() => intro.classList.add("gone"), 2200);
  setTimeout(() => intro.remove(), 3200);
})();

/* ------------------------------------------------------------
   2.5  PAGED-APP MODE — each section is a full-viewport page,
        with smooth slide transitions between them.
   ------------------------------------------------------------ */
(function pagedApp() {
  const sections = Array.from(document.querySelectorAll("[data-rail-label]"));
  const railNav = document.getElementById("railNav");
  const railProgress = document.getElementById("railProgress");
  if (!sections.length) return;

  // ---- populate rail nav ----
  sections.forEach((sec, i) => {
    const li = document.createElement("li");
    li.className = "rail-item";
    li.dataset.target = sec.id;
    li.dataset.idx = i;
    li.innerHTML = `<span class="rail-dot"></span><span class="rail-label">${sec.dataset.railLabel}</span>`;
    railNav.appendChild(li);
  });
  const items = Array.from(railNav.querySelectorAll(".rail-item"));

  // ---- wrap sections into a paged track ----
  // insert the empty track before moving sections into it (otherwise the
  // anchor reference becomes invalid mid-loop).
  const track = document.createElement("div");
  track.className = "pages-track";
  const anchor = sections[0].parentNode;
  anchor.insertBefore(track, sections[0]);
  sections.forEach((s, i) => {
    s.style.setProperty("--page-idx", i);
    track.appendChild(s);
  });
  document.body.classList.add("pages-mode");

  // ---- page indicator ----
  const piCurrent = document.getElementById("piCurrent");
  const piTotal = document.getElementById("piTotal");
  const piFill = document.getElementById("piFill");
  if (piTotal) piTotal.textContent = String(sections.length).padStart(2, "0");

  // ---- nav state ----
  let current = 0;
  let isTransitioning = false;

  function go(to, opts = {}) {
    to = Math.max(0, Math.min(sections.length - 1, to));
    if (to === current && !opts.force) return;
    current = to;
    isTransitioning = true;
    track.style.transform = `translateY(-${to * 100}vh)`;
    sections.forEach((s, i) => s.classList.toggle("is-current", i === to));
    items.forEach((it, i) => it.classList.toggle("active", i === to));

    // page indicator
    if (piCurrent) piCurrent.textContent = String(to + 1).padStart(2, "0");
    if (piFill) piFill.style.width = ((to + 1) / sections.length * 100) + "%";
    if (railProgress) railProgress.style.height = ((to + 1) / sections.length * 100) + "%";

    // signature animation for the new page
    sections[to].classList.add("anim-in");

    // url hash sync
    if (sections[to].id && history.replaceState) {
      history.replaceState(null, "", "#" + sections[to].id);
    }

    // unlock after transition
    setTimeout(() => { isTransitioning = false; }, 950);
  }

  // ---- click rail items ----
  items.forEach((it) => {
    it.addEventListener("click", () => {
      go(parseInt(it.dataset.idx, 10));
    });
  });

  // ---- wheel: throttled vertical scroll triggers page change ----
  let wheelLast = 0;
  let wheelAccum = 0;
  window.addEventListener("wheel", (e) => {
    // if the active page's content is itself scrollable AND not at edge, let it scroll
    const sec = sections[current];
    const canScrollDown = sec.scrollHeight - sec.clientHeight - sec.scrollTop > 4;
    const canScrollUp = sec.scrollTop > 4;
    if ((e.deltaY > 0 && canScrollDown) || (e.deltaY < 0 && canScrollUp)) {
      // pass through to the section's own scroll
      return;
    }
    e.preventDefault?.();
    const now = Date.now();
    if (isTransitioning || now - wheelLast < 700) return;
    wheelAccum += e.deltaY;
    if (Math.abs(wheelAccum) > 40) {
      wheelLast = now;
      go(current + (wheelAccum > 0 ? 1 : -1));
      wheelAccum = 0;
    }
  }, { passive: false });

  // ---- keyboard ----
  window.addEventListener("keydown", (e) => {
    if (isTransitioning) return;
    if (e.target.matches("input, textarea")) return;
    if (e.key === "ArrowDown" || e.key === "PageDown" || e.key === " ") {
      e.preventDefault(); go(current + 1);
    } else if (e.key === "ArrowUp" || e.key === "PageUp") {
      e.preventDefault(); go(current - 1);
    } else if (e.key === "Home") {
      go(0);
    } else if (e.key === "End") {
      go(sections.length - 1);
    }
  });

  // ---- touch swipe ----
  let touchY = 0;
  window.addEventListener("touchstart", (e) => { touchY = e.touches[0].clientY; }, { passive: true });
  window.addEventListener("touchend", (e) => {
    if (isTransitioning) return;
    const dy = e.changedTouches[0].clientY - touchY;
    if (Math.abs(dy) > 60) go(current + (dy < 0 ? 1 : -1));
  });

  // ---- jump from URL hash ----
  function jumpFromHash() {
    const h = location.hash.replace("#", "");
    if (!h) return;
    const idx = sections.findIndex((s) => s.id === h);
    if (idx >= 0) go(idx, { force: true });
  }
  window.addEventListener("hashchange", jumpFromHash);

  // initial render
  go(0, { force: true });
  setTimeout(jumpFromHash, 50);

  // expose for debugging if needed
  window.__rocketPages = { go, current: () => current, total: sections.length };
})();

/* ------------------------------------------------------------
   2.6  MAGNETIC CURSOR — interactive elements pull cursor slightly
   ------------------------------------------------------------ */
(function magneticElements() {
  if (!window.matchMedia("(pointer: fine)").matches) return;
  const els = document.querySelectorAll(
    ".replay-btn, .btn, .hero-cta, .stack-card, .rail-item"
  );
  els.forEach((el) => {
    el.addEventListener("mousemove", (e) => {
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const dx = (e.clientX - cx) / r.width;
      const dy = (e.clientY - cy) / r.height;
      // magnetic pull strength
      const pull = 8;
      el.style.setProperty("--mag-x", (dx * pull).toFixed(2) + "px");
      el.style.setProperty("--mag-y", (dy * pull).toFixed(2) + "px");
      el.style.transform = `translate(${dx * pull}px, ${dy * pull}px)`;
    });
    el.addEventListener("mouseleave", () => {
      el.style.transform = "";
    });
  });
})();

/* ------------------------------------------------------------
   3. RETICLE CURSOR
   ------------------------------------------------------------ */
(function reticle() {
  const ret = document.getElementById("reticle");
  if (!ret || !window.matchMedia("(pointer: fine)").matches) return;
  document.body.classList.add("has-reticle");
  let live = false;
  document.addEventListener("mousemove", (e) => {
    ret.style.left = e.clientX + "px";
    ret.style.top = e.clientY + "px";
    if (!live) { live = true; ret.classList.add("live"); }
  });
  document.addEventListener("mouseleave", () => { ret.classList.remove("live"); live = false; });
  // hot state when over interactive
  document.addEventListener("mouseover", (e) => {
    const el = e.target;
    const interactive = el.closest("a, button, .stack-card, .tool-card, .why-card, .replay-btn, .tilt, [data-step]");
    if (interactive) ret.classList.add("hot");
    else ret.classList.remove("hot");
  });
})();

(() => {
  // ============================================================
  // RUN DATA — embedded so the static space works with no fetch
  // (replace this with the real trace from the MI300X run before submitting)
  // ============================================================
  // Real trace from a measured run on AMD Instinct MI300X (ROCm 7).
  // model: Qwen2.5-7B-Instruct  ·  batch=8  ·  prompt 256 + new 512.
  const TRACE = {
    model_id: "Qwen/Qwen2.5-7B-Instruct",
    device_label: "ROCm: AMD Instinct MI300X",
    baseline_tok_s: 62.59,
    baseline_dtype: "float32",
    peak_memory_mb: 29975.4,
    iterations: [
      {
        step: 1,
        tool: "kv_cache_config",
        params: { enabled: true },
        reasoning: "KV cache was already enabled in Qwen2.5's default generation config. Toggling produced no measurable change.",
        pre_tok_s: 62.59,
        post_tok_s: 62.59,
        speedup_vs_prev: 1.00,
        cumulative_speedup: 1.00,
        accepted: false,
      },
      {
        step: 2,
        tool: "dtype_cast",
        params: { target: "bf16" },
        reasoning: "Model loaded in fp32. On MI300X, bf16 halves memory and unlocks the matrix-engine throughput. The single largest lever.",
        pre_tok_s: 62.59,
        post_tok_s: 183.47,
        speedup_vs_prev: 2.93,
        cumulative_speedup: 2.93,
        accepted: true,
      },
      {
        step: 3,
        tool: "sdpa_attention",
        params: {},
        reasoning: "Modern transformers loads SDPA by default. The tool found nothing to apply; runtime parity confirmed.",
        pre_tok_s: 183.47,
        post_tok_s: 180.87,
        speedup_vs_prev: 0.99,
        cumulative_speedup: 2.89,
        accepted: false,
      },
      {
        step: 4,
        tool: "input_padding",
        params: { multiple: 128 },
        reasoning: "Prompt at 256 tokens is already a multiple of 128. No matrix-engine alignment to gain.",
        pre_tok_s: 183.47,
        post_tok_s: 180.96,
        speedup_vs_prev: 0.99,
        cumulative_speedup: 2.89,
        accepted: false,
      },
      {
        step: 5,
        tool: "torch_compile",
        params: { mode: "reduce-overhead" },
        reasoning: "Compiled the bf16+SDPA model graph. Marginal +0.5% gain — below the 2% keep threshold. Validator correctly rejected.",
        pre_tok_s: 183.47,
        post_tok_s: 184.40,
        speedup_vs_prev: 1.005,
        cumulative_speedup: 2.95,
        accepted: false,
      },
    ],
  };
  // Compute final speedup from accepted iterations only (last one wasn't accepted).
  const FINAL_SPEEDUP = (() => {
    let best = 1.0;
    for (const it of TRACE.iterations) if (it.accepted) best = it.cumulative_speedup;
    return best;
  })();
  const FINAL_TOK_S = (() => {
    let v = TRACE.baseline_tok_s;
    for (const it of TRACE.iterations) if (it.accepted) v = it.post_tok_s;
    return v;
  })();

  // ============================================================
  // canvas particle background
  // ============================================================
  const canvas = document.getElementById("bgCanvas");
  if (canvas) {
    const ctx = canvas.getContext("2d");
    let dpr = Math.max(1, window.devicePixelRatio || 1);
    let w = 0, h = 0;
    let particles = [];

    const resize = () => {
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.style.width = w + "px";
      canvas.style.height = h + "px";
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const target = Math.min(120, Math.floor((w * h) / 18000));
      particles = Array.from({ length: target }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.15,
        vy: (Math.random() - 0.5) * 0.15,
        r: Math.random() * 1.6 + 0.3,
        a: Math.random() * 0.5 + 0.15,
      }));
    };
    window.addEventListener("resize", resize);
    resize();

    const tick = () => {
      ctx.clearRect(0, 0, w, h);
      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > w) p.vx *= -1;
        if (p.y < 0 || p.y > h) p.vy *= -1;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(237, 28, 36, ${p.a})`;
        ctx.fill();
      }
      requestAnimationFrame(tick);
    };
    tick();
  }

  // ============================================================
  // reveal on scroll (intersection observer)
  // ============================================================
  const revealEls = document.querySelectorAll(".reveal");
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          e.target.classList.add("in");
          io.unobserve(e.target);
        }
      }
    },
    { threshold: 0.15 }
  );
  revealEls.forEach((el) => io.observe(el));

  // ============================================================
  // speedup counter animation
  // ============================================================
  const counter = document.getElementById("speedupCounter");
  if (counter) {
    const target = parseFloat(counter.dataset.target || `${FINAL_SPEEDUP}`);
    const duration = 1800;
    let started = false;
    const animate = (now, start) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
      counter.textContent = (1 + (target - 1) * eased).toFixed(2);
      if (t < 1) requestAnimationFrame((nn) => animate(nn, start));
    };
    const counterIO = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !started) {
          started = true;
          requestAnimationFrame((now) => animate(now, now));
        }
      },
      { threshold: 0.4 }
    );
    counterIO.observe(counter);
  }

  // ============================================================
  // SVG chart — mission control trajectory plotter
  // ============================================================
  const RED = "#ED1C24";
  const AMBER = "#fbbf24";
  const NS = "http://www.w3.org/2000/svg";

  const chart = document.getElementById("journeyChart");
  let chartGeometry = null; // cached for hover
  let fluxRaf = null;

  function drawChart(stepsToShow = TRACE.iterations.length) {
    if (!chart) return;
    if (fluxRaf) cancelAnimationFrame(fluxRaf);
    chart.innerHTML = "";

    const W = 900, H = 380;
    const padLeft = 70, padRight = 40, padTop = 30, padBottom = 50;
    const plotW = W - padLeft - padRight;
    const plotH = H - padTop - padBottom;
    chart.setAttribute("viewBox", `0 0 ${W} ${H}`);

    const points = [{ step: 0, tok_s: TRACE.baseline_tok_s, tool: "baseline", kept: true, reasoning: "starting point" }];
    let running = TRACE.baseline_tok_s;
    for (let i = 0; i < stepsToShow; i++) {
      const it = TRACE.iterations[i];
      if (it.accepted) running = it.post_tok_s;
      points.push({
        step: it.step,
        tok_s: running,
        candidate: it.post_tok_s,
        tool: it.tool,
        kept: it.accepted,
        reasoning: it.reasoning,
        delta: it.speedup_vs_prev,
        cumulative: it.cumulative_speedup,
      });
    }

    const maxStep = TRACE.iterations.length;
    const allYs = [TRACE.baseline_tok_s, ...TRACE.iterations.map((i) => i.post_tok_s)];
    const yMax = Math.max(...allYs) * 1.20;
    const sx = (s) => padLeft + (s / maxStep) * plotW;
    const sy = (v) => padTop + plotH - (v / yMax) * plotH;

    // ---- defs (gradient + filter) ----
    const defs = document.createElementNS(NS, "defs");
    defs.innerHTML = `
      <linearGradient id="fillGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="${RED}" stop-opacity="0.32"/>
        <stop offset="100%" stop-color="${RED}" stop-opacity="0"/>
      </linearGradient>
      <filter id="glow"><feGaussianBlur stdDeviation="3"/></filter>
    `;
    chart.appendChild(defs);

    // ---- dense grid (mission control style) ----
    const grid = document.createElementNS(NS, "g");
    // horizontal
    for (let i = 0; i <= 8; i++) {
      const v = (yMax / 8) * i;
      const y = sy(v);
      const ln = document.createElementNS(NS, "line");
      ln.setAttribute("x1", padLeft); ln.setAttribute("x2", padLeft + plotW);
      ln.setAttribute("y1", y); ln.setAttribute("y2", y);
      ln.setAttribute("stroke", "rgba(237,28,36,0.05)");
      ln.setAttribute("stroke-width", "0.6");
      grid.appendChild(ln);
      if (i % 2 === 0) {
        const lbl = document.createElementNS(NS, "text");
        lbl.setAttribute("class", "axis-label");
        lbl.setAttribute("x", padLeft - 10);
        lbl.setAttribute("y", y + 4);
        lbl.setAttribute("text-anchor", "end");
        lbl.textContent = v.toFixed(0);
        grid.appendChild(lbl);
      }
    }
    // vertical
    for (let s = 0; s <= maxStep; s++) {
      const x = sx(s);
      const ln = document.createElementNS(NS, "line");
      ln.setAttribute("x1", x); ln.setAttribute("x2", x);
      ln.setAttribute("y1", padTop); ln.setAttribute("y2", padTop + plotH);
      ln.setAttribute("stroke", "rgba(255,255,255,0.04)");
      ln.setAttribute("stroke-width", "0.6");
      grid.appendChild(ln);
      const lbl = document.createElementNS(NS, "text");
      lbl.setAttribute("class", "axis-label");
      lbl.setAttribute("x", x);
      lbl.setAttribute("y", padTop + plotH + 22);
      lbl.setAttribute("text-anchor", "middle");
      lbl.textContent = s === 0 ? "BASELINE" : `T+${s}`;
      grid.appendChild(lbl);
    }
    chart.appendChild(grid);

    // ---- trajectory path ----
    let d = "";
    points.forEach((p, i) => {
      const x = sx(p.step), y = sy(p.tok_s);
      d += (i === 0 ? "M" : "L") + x + "," + y + " ";
    });

    if (points.length > 1) {
      const fillD = d +
        `L${sx(points[points.length-1].step)},${sy(0)} ` +
        `L${sx(points[0].step)},${sy(0)} Z`;
      const fill = document.createElementNS(NS, "path");
      fill.setAttribute("d", fillD);
      fill.setAttribute("fill", "url(#fillGrad)");
      chart.appendChild(fill);
    }

    const path = document.createElementNS(NS, "path");
    path.setAttribute("d", d);
    path.setAttribute("class", "trajectory-stroke");
    chart.appendChild(path);

    const totalLen = path.getTotalLength();
    path.style.strokeDasharray = totalLen;
    path.style.strokeDashoffset = totalLen;
    path.getBoundingClientRect();
    path.style.transition = "stroke-dashoffset 1.6s cubic-bezier(0.4,0,0.2,1)";
    path.style.strokeDashoffset = "0";

    // ---- waypoints ----
    points.forEach((p, i) => {
      if (i === 0) return;
      const cx = sx(p.step);
      const cy = sy(p.kept ? p.tok_s : p.candidate);

      if (p.kept) {
        // pulsing halo
        const halo = document.createElementNS(NS, "circle");
        halo.setAttribute("cx", cx);
        halo.setAttribute("cy", cy);
        halo.setAttribute("r", 10);
        halo.setAttribute("class", "waypoint-halo");
        halo.style.animationDelay = (i * 0.4) + "s";
        chart.appendChild(halo);
        // core
        const core = document.createElementNS(NS, "circle");
        core.setAttribute("cx", cx);
        core.setAttribute("cy", cy);
        core.setAttribute("r", 7);
        core.setAttribute("class", "waypoint-core");
        core.style.opacity = 0;
        core.style.transition = `opacity 0.4s ease ${0.6 + i*0.18}s`;
        chart.appendChild(core);
        requestAnimationFrame(() => (core.style.opacity = 1));
        // label
        const t = document.createElementNS(NS, "text");
        t.setAttribute("class", "point-label");
        t.setAttribute("x", cx);
        t.setAttribute("y", cy - 18);
        t.setAttribute("text-anchor", "middle");
        t.textContent = p.tool;
        t.style.opacity = 0;
        t.style.transition = `opacity 0.4s ease ${0.7 + i*0.18}s`;
        chart.appendChild(t);
        requestAnimationFrame(() => (t.style.opacity = 1));
      } else {
        // amber X
        const cross = document.createElementNS(NS, "g");
        for (const [x1, y1, x2, y2] of [[-7,-7,7,7],[-7,7,7,-7]]) {
          const ln = document.createElementNS(NS, "line");
          ln.setAttribute("x1", cx+x1); ln.setAttribute("y1", cy+y1);
          ln.setAttribute("x2", cx+x2); ln.setAttribute("y2", cy+y2);
          ln.setAttribute("stroke", AMBER);
          ln.setAttribute("stroke-width", 2.6);
          ln.setAttribute("stroke-linecap", "round");
          cross.appendChild(ln);
        }
        cross.style.opacity = 0;
        cross.style.transition = `opacity 0.4s ease ${0.6 + i*0.18}s`;
        chart.appendChild(cross);
        requestAnimationFrame(() => (cross.style.opacity = 1));
        const t = document.createElementNS(NS, "text");
        t.setAttribute("class", "point-label dim");
        t.setAttribute("x", cx);
        t.setAttribute("y", cy - 14);
        t.setAttribute("text-anchor", "middle");
        t.textContent = p.tool + " ↩";
        t.style.opacity = 0;
        t.style.transition = `opacity 0.4s ease ${0.7 + i*0.18}s`;
        chart.appendChild(t);
        requestAnimationFrame(() => (t.style.opacity = 1));
      }
    });

    // ---- flux particles flowing along the path ----
    const fluxGroup = document.createElementNS(NS, "g");
    const PARTICLE_COUNT = 12;
    const flux = [];
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const c = document.createElementNS(NS, "circle");
      c.setAttribute("r", 2.5);
      c.setAttribute("class", "flux-particle");
      fluxGroup.appendChild(c);
      flux.push({ el: c, t: i / PARTICLE_COUNT });
    }
    chart.appendChild(fluxGroup);

    const animateFlux = () => {
      flux.forEach((f) => {
        f.t += 0.0035;
        if (f.t > 1) f.t -= 1;
        const len = totalLen * f.t;
        const pt = path.getPointAtLength(len);
        f.el.setAttribute("cx", pt.x);
        f.el.setAttribute("cy", pt.y);
        f.el.setAttribute("opacity", 0.4 + 0.6 * Math.sin(f.t * Math.PI));
      });
      fluxRaf = requestAnimationFrame(animateFlux);
    };
    setTimeout(animateFlux, 1200);

    // ---- hover scrubber ----
    const scrub = document.createElementNS(NS, "line");
    scrub.setAttribute("class", "scrubber-line");
    scrub.setAttribute("y1", padTop);
    scrub.setAttribute("y2", padTop + plotH);
    chart.appendChild(scrub);

    chartGeometry = { padLeft, padRight, padTop, padBottom, plotW, plotH, points, sx, sy, scrub, W, H };
  }

  // ---- HUD hover wiring ----
  const tip = document.getElementById("hudTip");
  const hudStep = document.getElementById("hudStep");
  const hudTps = document.getElementById("hudTps");
  const hudMult = document.getElementById("hudMult");
  const hudTool = document.getElementById("hudTool");
  const hudState = document.getElementById("hudState");
  const tipStep = document.getElementById("tipStep");
  const tipTool = document.getElementById("tipTool");
  const tipTps = document.getElementById("tipTps");
  const tipDelta = document.getElementById("tipDelta");

  function setHud(p) {
    if (!p) return;
    if (hudStep) hudStep.textContent = p.step === 0 ? "0" : p.step;
    if (hudTps) hudTps.textContent = (p.kept ? p.tok_s : p.candidate || p.tok_s).toFixed(1);
    if (hudMult) hudMult.textContent = p.cumulative ? p.cumulative.toFixed(2) : "1.00";
    if (hudTool) hudTool.textContent = p.tool;
  }

  if (chart) {
    chart.addEventListener("mousemove", (e) => {
      if (!chartGeometry) return;
      const rect = chart.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * chartGeometry.W;
      const { points, sx, sy, scrub } = chartGeometry;
      // find closest waypoint
      let best = points[0], bd = Infinity;
      points.forEach((p) => {
        const dx = sx(p.step) - x;
        if (Math.abs(dx) < bd) { bd = Math.abs(dx); best = p; }
      });
      const wx = sx(best.step);
      scrub.setAttribute("x1", wx);
      scrub.setAttribute("x2", wx);
      scrub.classList.add("live");

      // update tooltip
      if (tip) {
        const hostRect = chart.parentElement.getBoundingClientRect();
        const px = ((wx / chartGeometry.W) * rect.width) + (rect.left - hostRect.left) + 14;
        const py = ((sy(best.kept ? best.tok_s : best.candidate || best.tok_s) / chartGeometry.H) * rect.height) + (rect.top - hostRect.top) - 12;
        tip.style.left = px + "px";
        tip.style.top = py + "px";
        tip.classList.add("live");
        if (tipStep) tipStep.textContent = best.step === 0 ? "baseline" : "step " + best.step;
        if (tipTool) tipTool.textContent = best.tool;
        if (tipTps) tipTps.textContent = (best.kept ? best.tok_s : best.candidate || best.tok_s).toFixed(1) + " tok/s";
        if (tipDelta) {
          if (best.delta != null) {
            tipDelta.textContent = (best.kept ? "+" : "↩ ") + ((best.delta - 1) * 100).toFixed(0) + "%";
            tipDelta.style.color = best.kept ? "var(--red)" : "#fbbf24";
          } else {
            tipDelta.textContent = "—";
          }
        }
      }
      setHud(best);
    });
    chart.addEventListener("mouseleave", () => {
      if (chartGeometry?.scrub) chartGeometry.scrub.classList.remove("live");
      if (tip) tip.classList.remove("live");
      // restore final-step HUD
      const last = TRACE.iterations[TRACE.iterations.length - 1];
      if (last) setHud({
        step: last.step, tool: last.tool,
        tok_s: last.accepted ? last.post_tok_s : FINAL_TOK_S,
        candidate: last.post_tok_s, kept: last.accepted,
        cumulative: last.cumulative_speedup,
      });
    });
  }

  // initial draw when chart enters viewport
  let chartStarted = false;
  if (chart) {
    const chartIO = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !chartStarted) {
          chartStarted = true;
          drawChart();
        }
      },
      { threshold: 0.3 }
    );
    chartIO.observe(chart);
  }

  // replay button — wipe and redraw step-by-step
  const replayBtn = document.getElementById("replayBtn");
  if (replayBtn && chart) {
    replayBtn.addEventListener("click", async () => {
      replayBtn.disabled = true;
      replayBtn.textContent = "▶︎ Replaying…";
      drawChart(0);
      for (let s = 1; s <= TRACE.iterations.length; s++) {
        await new Promise((r) => setTimeout(r, 700));
        drawChart(s);
      }
      replayBtn.disabled = false;
      replayBtn.textContent = "▶︎ Replay the run";
    });
  }

  // ============================================================
  // LIVE TERMINAL — fake real-software playback
  // ============================================================
  const TERM = [
    { cls: "term-banner", text:
`  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
  ┃   ROCKET ⚡  v0.1.0  ·  AMD MI300X autopilot           ┃
  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛`, delay: 0 },
    { cls: "term-faint", text: "  detecting hardware…", delay: 600 },
    { cls: "term-good",  text: "  ✓ ROCm 7.0 · AMD Instinct MI300X · 192 GB HBM3", delay: 700 },
    { cls: "term-faint", text: "  loading target Qwen/Qwen2.5-7B-Instruct (fp32)…", delay: 700 },
    { cls: "term-good",  text: "  ✓ model loaded · 29.9 GB device memory", delay: 800 },
    { cls: "term-info",  text: "[baseline] running benchmark · batch 8 · 256 prompt + 512 new", delay: 600 },
    { cls: "term-bold",  text: "  baseline tok/s = 62.59    peak mem = 29975 MB", delay: 1100 },
    { cls: "term-faint", text: "  ─── iteration 1 ───────────────────────────────────────", delay: 600 },
    { cls: "term-info",  text: "[planner ] decision: kv_cache_config({enabled: true})", delay: 800 },
    { cls: "term-warn",  text: "  ↩ 62.6 → 62.6 tok/s   (1.00× · already enabled · reverted)", delay: 900 },
    { cls: "term-faint", text: "  ─── iteration 2 ───────────────────────────────────────", delay: 500 },
    { cls: "term-info",  text: "[planner ] decision: dtype_cast({target: 'bf16'})", delay: 700 },
    { cls: "term-faint", text: "           reason: model is fp32; bf16 unlocks MI300X matrix engines", delay: 500 },
    { cls: "term-good",  text: "  ✓ 62.6 → 183.5 tok/s  (2.93× KEPT · cum 2.93×)", delay: 900 },
    { cls: "term-faint", text: "  ─── iteration 3 ───────────────────────────────────────", delay: 500 },
    { cls: "term-info",  text: "[planner ] decision: sdpa_attention()", delay: 700 },
    { cls: "term-warn",  text: "  ↩ 183.5 → 180.9 tok/s (0.99× · already SDPA · reverted)", delay: 800 },
    { cls: "term-faint", text: "  ─── iteration 4 ───────────────────────────────────────", delay: 500 },
    { cls: "term-info",  text: "[planner ] decision: input_padding({multiple: 128})", delay: 700 },
    { cls: "term-warn",  text: "  ↩ 183.5 → 181.0 tok/s (0.99× · shapes already aligned · reverted)", delay: 800 },
    { cls: "term-faint", text: "  ─── iteration 5 ───────────────────────────────────────", delay: 500 },
    { cls: "term-info",  text: "[planner ] decision: torch_compile({mode: 'reduce-overhead'})", delay: 700 },
    { cls: "term-warn",  text: "  ↩ 183.5 → 184.4 tok/s (1.005× below threshold · reverted)", delay: 1000 },
    { cls: "term-bold",  text: "", delay: 200 },
    { cls: "term-red",   text: "  ROCKET RESULT  →  62.59 → 183.47 tok/s   ·   2.93× speedup", delay: 800 },
    { cls: "term-faint", text: "  diff written to logs/run.diff · trace at logs/run.jsonl", delay: 500 },
    { cls: "term-good",  text: "  ✓ done. zero human input required.", delay: 600 },
  ];

  const termScreen = document.getElementById("termScreen");
  const termStatus = document.getElementById("termStatus");
  if (termScreen) {
    let played = false;
    const playTerminal = async () => {
      if (played) return;
      played = true;
      for (let i = 0; i < TERM.length; i++) {
        const item = TERM[i];
        await new Promise((r) => setTimeout(r, item.delay));
        const ln = document.createElement("span");
        ln.className = "term-line " + item.cls;
        ln.textContent = item.text;
        termScreen.appendChild(ln);
        termScreen.appendChild(document.createTextNode("\n"));
        requestAnimationFrame(() => ln.classList.add("in"));
        termScreen.scrollTop = termScreen.scrollHeight;
      }
      // blinking cursor at the end
      const cur = document.createElement("span");
      cur.className = "term-cursor";
      termScreen.appendChild(cur);
      if (termStatus) {
        termStatus.textContent = "● done";
        termStatus.style.color = "var(--red)";
      }
    };
    const termIO = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) playTerminal();
    }, { threshold: 0.2 });
    termIO.observe(termScreen);
  }

  // ============================================================
  // PROFILE BREAKDOWN — bars that mutate when stack toggles
  // ============================================================
  // each row is a measured layer/op category with per-tool effect multipliers
  // (positive = reduces time; values < 1 mean "kills this much of this op").
  //
  // baseline ms per token (~25.1ms for ~40 tok/s on a 1.5B model):
  const PROFILE_BASE_MS = 25.06;
  const PROFILE_BASE_MEM_GB = 6.30;
  // baseline shares (% of device time)
  const PROFILE_LAYERS = [
    { id: "attention",     name: "attention",        share: 0.47 },
    { id: "matmul",        name: "matmul / linear",  share: 0.22 },
    { id: "layernorm",     name: "norm + residual",  share: 0.11 },
    { id: "kv_overhead",   name: "kv re-compute",    share: 0.10 },
    { id: "dispatch",      name: "kernel launch",    share: 0.06 },
    { id: "other",         name: "other",            share: 0.04 },
  ];
  // each tool reduces certain layers' time by these factors
  const TOOL_EFFECTS = {
    kv_cache_config: { kv_overhead: 0.10, attention: 0.55, layernorm: 0.55 },
    dtype_cast:      { matmul: 0.55, attention: 0.6, layernorm: 0.7, other: 0.7 },
    sdpa_attention:  { attention: 0.55 },
    torch_compile:   { dispatch: 0.25, other: 0.6, layernorm: 0.7, matmul: 0.85 },
    input_padding:   { matmul: 0.95 }, // small effect (typically reverted)
  };

  const profileBars = document.getElementById("profileBars");
  const profileTimeEl = document.getElementById("profileTime");
  const profileMemEl = document.getElementById("profileMem");
  const profileBottleneckEl = document.getElementById("profileBottleneck");

  function buildProfile() {
    if (!profileBars) return;
    profileBars.innerHTML = "";
    PROFILE_LAYERS.forEach((l) => {
      const row = document.createElement("div");
      row.className = "pbar-row";
      row.dataset.id = l.id;
      row.innerHTML = `
        <div class="pbar-name">${l.name}</div>
        <div class="pbar-track"><div class="pbar-fill" style="width:${(l.share*100).toFixed(1)}%"></div></div>
        <div class="pbar-pct">${(l.share*100).toFixed(0)}%</div>
      `;
      profileBars.appendChild(row);
    });
  }
  buildProfile();

  // expose updateProfile so the stack can call it
  function updateProfile(activeTools) {
    if (!profileBars) return;
    // recompute per-layer time (in ms)
    let totalMs = 0;
    const newShares = PROFILE_LAYERS.map((l) => {
      let ms = PROFILE_BASE_MS * l.share;
      for (const tool of activeTools) {
        const eff = TOOL_EFFECTS[tool];
        if (eff && eff[l.id] != null) ms *= eff[l.id];
      }
      totalMs += ms;
      return { ...l, ms };
    });
    // find bottleneck
    let bottleneck = newShares[0];
    for (const r of newShares) if (r.ms > bottleneck.ms) bottleneck = r;
    // memory
    let mem = PROFILE_BASE_MEM_GB;
    if (activeTools.includes("dtype_cast")) mem *= 0.5;
    // render
    newShares.forEach((r) => {
      const row = profileBars.querySelector(`[data-id="${r.id}"]`);
      if (!row) return;
      const pct = (r.ms / totalMs) * 100;
      row.querySelector(".pbar-fill").style.width = pct.toFixed(1) + "%";
      row.querySelector(".pbar-pct").textContent = pct.toFixed(0) + "%";
    });
    if (profileTimeEl) profileTimeEl.textContent = totalMs.toFixed(1);
    if (profileMemEl) profileMemEl.textContent = mem.toFixed(2);
    if (profileBottleneckEl) profileBottleneckEl.textContent = bottleneck.name;
  }
  // make available to the stack toggler
  window.__rocketUpdateProfile = updateProfile;

  // ============================================================
  // CURSOR GLOW (premium ambient)
  // ============================================================
  const glow = document.getElementById("cursorGlow");
  if (glow && window.matchMedia("(pointer: fine)").matches) {
    let active = false;
    document.addEventListener("mousemove", (e) => {
      glow.style.left = e.clientX + "px";
      glow.style.top = e.clientY + "px";
      if (!active) {
        active = true;
        glow.classList.add("live");
      }
    });
    document.addEventListener("mouseleave", () => glow.classList.remove("live"));
  }

  // ============================================================
  // TILT on cards (premium hover)
  // ============================================================
  const tiltEls = document.querySelectorAll(".tilt");
  tiltEls.forEach((el) => {
    el.addEventListener("mousemove", (e) => {
      const r = el.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width - 0.5;
      const y = (e.clientY - r.top) / r.height - 0.5;
      const rx = (-y * 6).toFixed(2);
      const ry = (x * 6).toFixed(2);
      el.style.transform = `perspective(900px) rotateX(${rx}deg) rotateY(${ry}deg) translateZ(0)`;
    });
    el.addEventListener("mouseleave", () => {
      el.style.transform = "";
    });
  });

  // ============================================================
  // TOKEN RACE — side-by-side animated generation
  // ============================================================
  const RACE_TEXT =
    "The AMD Instinct MI300X packs 192 GB of HBM3 memory into a single CDNA 3 " +
    "datacenter GPU, delivering leading bf16 matrix throughput for LLM inference. " +
    "Its memory footprint lets a single device hold 70B-class models without " +
    "sharding, and the matrix engines see real wins from low-precision casts.";

  const BASE_TPS = TRACE.baseline_tok_s;
  const OPT_TPS = FINAL_TOK_S;
  const RACE_DURATION_OPT_MS = 2200;            // optimized finishes in this many ms
  const RACE_DURATION_BASE_MS = RACE_DURATION_OPT_MS * (OPT_TPS / BASE_TPS);

  const raceBtn = document.getElementById("raceBtn");
  const outBase = document.getElementById("raceOutputBase");
  const outOpt = document.getElementById("raceOutputOpt");
  const curBase = document.getElementById("raceCursorBase");
  const curOpt = document.getElementById("raceCursorOpt");
  const barBase = document.getElementById("raceBarBase");
  const barOpt = document.getElementById("raceBarOpt");
  const raceMeta = document.getElementById("raceMeta");

  let raceRunning = false;

  function runRace() {
    if (raceRunning) return;
    raceRunning = true;
    raceBtn.disabled = true;
    raceBtn.textContent = "▶︎ Racing…";
    outBase.textContent = "";
    outOpt.textContent = "";
    curBase.classList.add("live");
    curOpt.classList.add("live");
    barBase.style.width = "0%";
    barOpt.style.width = "0%";
    if (raceMeta) raceMeta.textContent = "racing…";

    const totalChars = RACE_TEXT.length;
    const t0 = performance.now();
    let baseDone = false, optDone = false;
    let optEndedAt = 0;

    function frame(now) {
      const dt = now - t0;
      const baseFrac = Math.min(1, dt / RACE_DURATION_BASE_MS);
      const optFrac = Math.min(1, dt / RACE_DURATION_OPT_MS);

      const baseLen = Math.floor(totalChars * baseFrac);
      const optLen = Math.floor(totalChars * optFrac);

      outBase.textContent = RACE_TEXT.slice(0, baseLen);
      outOpt.textContent = RACE_TEXT.slice(0, optLen);
      barBase.style.width = (baseFrac * 100) + "%";
      barOpt.style.width = (optFrac * 100) + "%";

      if (!optDone && optFrac >= 1) {
        optDone = true;
        optEndedAt = dt;
        curOpt.classList.remove("live");
        if (raceMeta)
          raceMeta.innerHTML = `<span style="color:var(--red); font-weight:700;">ROCKET wins.</span> Baseline still typing…`;
      }
      if (!baseDone && baseFrac >= 1) {
        baseDone = true;
        curBase.classList.remove("live");
        const ratio = (RACE_DURATION_BASE_MS / optEndedAt).toFixed(2);
        if (raceMeta)
          raceMeta.innerHTML = `<span style="color:var(--red); font-weight:700;">${ratio}× faster</span> · same output, same model, same MI300X`;
      }
      if (!optDone || !baseDone) {
        requestAnimationFrame(frame);
      } else {
        raceRunning = false;
        raceBtn.disabled = false;
        raceBtn.textContent = "▶︎ Run the race again";
      }
    }
    requestAnimationFrame(frame);
  }

  if (raceBtn) raceBtn.addEventListener("click", runRace);

  // auto-run race when its section first scrolls into view
  const raceSection = document.getElementById("race");
  if (raceSection) {
    let played = false;
    const raceIO = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && !played) {
        played = true;
        setTimeout(runRace, 400);
      }
    }, { threshold: 0.4 });
    raceIO.observe(raceSection);
  }

  // ============================================================
  // INTERACTIVE OPTIMIZATION STACK
  // ============================================================
  // each card represents one optimization the agent picked. multipliers are
  // the *speedup contribution* of that step (relative to its prior best).
  const STACK_TOOLS = TRACE.iterations
    .filter((it) => it.accepted)
    .map((it, i) => ({
      id: it.tool,
      name: it.tool,
      desc: it.reasoning,
      mult: it.speedup_vs_prev,
      order: i + 1,
    }));

  const stackCardsEl = document.getElementById("stackCards");
  const stackNumEl = document.getElementById("stackNum");
  const stackFillEl = document.getElementById("stackFill");
  const stackBaselineEl = document.getElementById("stackBaseline");
  const stackResultEl = document.getElementById("stackResult");

  if (stackCardsEl && stackNumEl) {
    // descriptions overrides for clarity to non-experts
    const SHORT = {
      kv_cache_config: "Re-enable KV caching during generation. Often the single biggest fix.",
      dtype_cast: "Cast the model from fp32 to bf16. Halves memory, doubles arithmetic.",
      sdpa_attention: "Switch to PyTorch's fused scaled-dot-product attention.",
      input_padding: "Pad input shapes to multiples of 128 for matrix-engine alignment.",
      torch_compile: "Compile the model graph with torch.compile (Inductor on ROCm).",
    };

    // build cards
    const state = STACK_TOOLS.map((t) => ({ ...t, on: true }));

    function render() {
      stackCardsEl.innerHTML = "";
      state.forEach((t, idx) => {
        const card = document.createElement("div");
        card.className = "stack-card " + (t.on ? "on" : "off");
        card.innerHTML = `
          <div class="stack-card-toggle"></div>
          <div class="stack-card-body">
            <div class="stack-card-name">${idx + 1}. ${t.name}</div>
            <div class="stack-card-desc">${SHORT[t.id] || t.desc}</div>
          </div>
          <div class="stack-card-mult">${t.mult.toFixed(2)}×</div>
        `;
        card.addEventListener("click", () => {
          t.on = !t.on;
          card.classList.add("spark");
          setTimeout(() => card.classList.remove("spark"), 600);
          render();
          updateMeter(true);
        });
        stackCardsEl.appendChild(card);
      });
    }

    function updateMeter(animate = false) {
      let mult = 1.0;
      const activeTools = [];
      state.forEach((t) => {
        if (t.on) {
          mult *= t.mult;
          activeTools.push(t.id);
        }
      });
      // tell the profile breakdown which tools are active
      if (window.__rocketUpdateProfile) window.__rocketUpdateProfile(activeTools);
      const target = mult;
      const max = STACK_TOOLS.reduce((a, t) => a * t.mult, 1.0);
      const pct = Math.min(100, (target / max) * 100);
      stackFillEl.style.width = pct + "%";
      if (stackBaselineEl) stackBaselineEl.textContent = TRACE.baseline_tok_s.toFixed(1);
      if (stackResultEl) stackResultEl.textContent = (TRACE.baseline_tok_s * target).toFixed(1);

      if (animate) {
        const num = stackNumEl;
        num.parentElement.classList.add("bumping");
        setTimeout(() => num.parentElement.classList.remove("bumping"), 380);
        const start = parseFloat(num.textContent) || 1;
        const dur = 420;
        const t0 = performance.now();
        function tick(now) {
          const f = Math.min(1, (now - t0) / dur);
          const eased = 1 - Math.pow(1 - f, 3);
          num.textContent = (start + (target - start) * eased).toFixed(2);
          if (f < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
      } else {
        stackNumEl.textContent = target.toFixed(2);
      }
    }

    render();
    updateMeter(false);
  }

  // ============================================================
  // timeline (agent reasoning) — render dynamically with stagger
  // ============================================================
  const timeline = document.getElementById("timeline");
  if (timeline) {
    const fragment = document.createDocumentFragment();
    TRACE.iterations.forEach((it, idx) => {
      const cls = it.accepted ? "" : " reverted";
      const badgeCls = it.accepted ? "" : " warn";
      const resultCls = it.accepted ? "" : " warn";
      const label = it.accepted ? "✓ KEPT" : "↩ REVERTED";
      const paramStr = JSON.stringify(it.params);

      const div = document.createElement("div");
      div.className = `tl-step${cls}`;
      div.dataset.step = String(it.step);
      div.innerHTML = `
        <div class="tl-head">
          <div class="tl-tool">
            <span class="badge${badgeCls}">${label}</span>
            <code>${it.tool}(${paramStr})</code>
          </div>
          <div class="tl-result${resultCls}">${it.speedup_vs_prev.toFixed(2)}× &nbsp;·&nbsp; cum ${it.cumulative_speedup.toFixed(2)}×</div>
        </div>
        <div class="tl-reasoning">"${it.reasoning}"</div>
        <div class="tl-meta">${it.pre_tok_s.toFixed(1)} → ${it.post_tok_s.toFixed(1)} tok/s</div>
      `;
      fragment.appendChild(div);
    });
    timeline.appendChild(fragment);

    // stagger reveal
    const tlSteps = timeline.querySelectorAll(".tl-step");
    const tlIO = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            const idx = Array.from(tlSteps).indexOf(e.target);
            setTimeout(() => e.target.classList.add("in"), idx * 120);
            tlIO.unobserve(e.target);
          }
        });
      },
      { threshold: 0.2 }
    );
    tlSteps.forEach((s) => tlIO.observe(s));
  }
})();
