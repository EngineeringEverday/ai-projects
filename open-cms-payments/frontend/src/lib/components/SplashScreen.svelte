<script>
  import * as THREE from "three";
  import { onMount } from "svelte";

  let { onEnter } = $props();

  let canvasEl = $state(null);
  let pixelEl = $state(null); // corner pixel-art canvas
  let exiting = $state(false);
  let phase = $state(0); // drives staggered entrance

  function handleEnter() {
    exiting = true;
    setTimeout(() => onEnter?.(), 800);
  }

  onMount(() => {
    // Stagger entrance phases
    setTimeout(() => (phase = 1), 80);
    setTimeout(() => (phase = 2), 280);
    setTimeout(() => (phase = 3), 440);
    setTimeout(() => (phase = 4), 580);
    setTimeout(() => (phase = 5), 700);

    // ── Three.js network globe ────────────────────────────────
    if (!canvasEl) return;

    const scene = new THREE.Scene();
    const w = window.innerWidth,
      h = window.innerHeight;
    const camera = new THREE.PerspectiveCamera(60, w / h, 0.1, 1000);
    camera.position.z = 90;

    const renderer = new THREE.WebGLRenderer({
      canvas: canvasEl,
      antialias: true,
      alpha: true,
    });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);

    const group = new THREE.Group();
    const N = 110;
    const positions = [];

    const palette = [
      0x8b5cf6, 0xa78bfa, 0xc4b5fd, 0xf59e0b, 0xfbbf24, 0x6d28d9, 0x7c3aed,
    ];

    for (let i = 0; i < N; i++) {
      const phi = Math.acos(-1 + (2 * i) / N);
      const theta = Math.sqrt(N * Math.PI) * phi;
      const r = 24 + Math.random() * 22;
      const x = r * Math.sin(phi) * Math.cos(theta);
      const y = r * Math.sin(phi) * Math.sin(theta);
      const z = r * Math.cos(phi);
      positions.push(new THREE.Vector3(x, y, z));

      const size = 0.18 + Math.random() * 0.52;
      const col = palette[Math.floor(Math.random() * palette.length)];
      const geo = new THREE.SphereGeometry(size, 7, 5);
      const mat = new THREE.MeshBasicMaterial({
        color: col,
        transparent: true,
        opacity: 0.28 + Math.random() * 0.45,
      });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.set(x, y, z);
      group.add(mesh);
    }

    // Very dim connection lines
    const edgeVerts = [];
    for (let i = 0; i < N; i++) {
      const dists = [];
      for (let j = 0; j < N; j++) {
        if (i !== j)
          dists.push({ j, d: positions[i].distanceTo(positions[j]) });
      }
      dists.sort((a, b) => a.d - b.d);
      const k = 1 + Math.floor(Math.random() * 2);
      for (let c = 0; c < k; c++) {
        if (dists[c]?.d < 28) {
          const p = positions[i],
            q = positions[dists[c].j];
          edgeVerts.push(p.x, p.y, p.z, q.x, q.y, q.z);
        }
      }
    }
    const edgeGeo = new THREE.BufferGeometry();
    edgeGeo.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(edgeVerts, 3),
    );
    const edgeMat = new THREE.LineBasicMaterial({
      color: 0x8b5cf6,
      transparent: true,
      opacity: 0.07,
    });
    group.add(new THREE.LineSegments(edgeGeo, edgeMat));
    scene.add(group);

    let animId,
      t = 0;
    function animate() {
      animId = requestAnimationFrame(animate);
      t += 0.0015;
      group.rotation.y = t * 0.12;
      group.rotation.x = Math.sin(t * 0.06) * 0.08;
      renderer.render(scene, camera);
    }
    animate();

    // ── Corner pixel-art canvas ───────────────────────────────
    let pixAnimId;
    if (pixelEl) {
      const ctx = pixelEl.getContext("2d");
      const pw = window.innerWidth,
        ph = window.innerHeight;
      pixelEl.width = pw;
      pixelEl.height = ph;

      const SZ = 3; // pixel square size
      const GAP = 8; // gap between squares
      const STEP = SZ + GAP;
      const COLS = 9;
      const ROWS = 7;
      const MARGIN = 32;

      // corner origins: top-left, top-right, bottom-left, bottom-right
      const origins = [
        { ox: MARGIN, oy: MARGIN, dirX: 1, dirY: 1 },
        { ox: pw - MARGIN - (COLS - 1) * STEP, oy: MARGIN, dirX: -1, dirY: 1 },
        { ox: MARGIN, oy: ph - MARGIN - (ROWS - 1) * STEP, dirX: 1, dirY: -1 },
        {
          ox: pw - MARGIN - (COLS - 1) * STEP,
          oy: ph - MARGIN - (ROWS - 1) * STEP,
          dirX: -1,
          dirY: -1,
        },
      ];

      // Build sparse pixel list with per-pixel phase + brightness
      const pixels = [];
      for (const { ox, oy, dirX, dirY } of origins) {
        for (let row = 0; row < ROWS; row++) {
          for (let col = 0; col < COLS; col++) {
            // density falloff: pixels far from corner are rarer
            const normX =
              dirX > 0 ? col / (COLS - 1) : (COLS - 1 - col) / (COLS - 1);
            const normY =
              dirY > 0 ? row / (ROWS - 1) : (ROWS - 1 - row) / (ROWS - 1);
            const distFromCorner =
              Math.sqrt(normX ** 2 + normY ** 2) / Math.SQRT2;
            if (Math.random() > 0.55 - distFromCorner * 0.35) continue;

            const isAmber = Math.random() > 0.72;
            pixels.push({
              x: ox + col * STEP,
              y: oy + row * STEP,
              phase: Math.random() * Math.PI * 2,
              speed: 0.35 + Math.random() * 0.7,
              baseAlpha: 0.06 + (1 - distFromCorner) * 0.22,
              r: isAmber ? 245 : 139,
              g: isAmber ? 158 : 92,
              b: isAmber ? 11 : 246,
            });
          }
        }
      }

      function drawPixels(ts) {
        pixAnimId = requestAnimationFrame(drawPixels);
        ctx.clearRect(0, 0, pw, ph);
        for (const p of pixels) {
          const pulse = (Math.sin(p.phase + ts * 0.001 * p.speed) + 1) / 2;
          const alpha = p.baseAlpha * (0.25 + 0.75 * pulse);
          ctx.fillStyle = `rgba(${p.r},${p.g},${p.b},${alpha.toFixed(3)})`;
          ctx.fillRect(p.x, p.y, SZ, SZ);
        }
      }
      drawPixels(0);
    }

    const onResize = () => {
      const nw = window.innerWidth,
        nh = window.innerHeight;
      camera.aspect = nw / nh;
      camera.updateProjectionMatrix();
      renderer.setSize(nw, nh);
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(animId);
      cancelAnimationFrame(pixAnimId);
      window.removeEventListener("resize", onResize);
      renderer.dispose();
    };
  });

  const FEATURES = [
    { label: "Network Graph", icon: "⬡" },
    { label: "Community Analysis", icon: "◎" },
    { label: "Anomaly Detection", icon: "⚡" },
    { label: "Risk Scoring", icon: "◈" },
  ];
</script>

<div class="splash" class:exiting>
  <!-- Three.js network globe bg -->
  <canvas bind:this={canvasEl} class="splash-canvas"></canvas>

  <!-- Corner pixel-art particles -->
  <canvas bind:this={pixelEl} class="pixel-canvas"></canvas>

  <!-- Very subtle radial glow behind content -->
  <div class="glow-orb"></div>

  <!-- Content -->
  <div class="splash-body">
    <!-- Logo mark -->
    <div class="logo-wrap" class:in={phase >= 1}>
      <svg width="44" height="44" viewBox="0 0 44 44" fill="none">
        <circle
          cx="22"
          cy="22"
          r="20"
          stroke="rgba(139,92,246,0.22)"
          stroke-width="1"
        />
        <polygon
          points="22,5 36,13.5 36,30.5 22,39 8,30.5 8,13.5"
          stroke="rgba(139,92,246,0.45)"
          stroke-width="1"
          fill="none"
        />
        <circle cx="22" cy="22" r="4.5" fill="#8B5CF6" opacity="0.9" />
        <circle cx="22" cy="7" r="2.2" fill="#A78BFA" opacity="0.75" />
        <circle cx="34" cy="14" r="2.2" fill="#F59E0B" opacity="0.75" />
        <circle cx="34" cy="30" r="2.2" fill="#FBBF24" opacity="0.65" />
        <circle cx="22" cy="37" r="2.2" fill="#C4B5FD" opacity="0.75" />
        <circle cx="10" cy="30" r="2.2" fill="#F59E0B" opacity="0.65" />
        <circle cx="10" cy="14" r="2.2" fill="#A78BFA" opacity="0.65" />
        <line
          x1="22"
          y1="18"
          x2="22"
          y2="9"
          stroke="rgba(139,92,246,0.35)"
          stroke-width="0.8"
        />
        <line
          x1="22"
          y1="18"
          x2="33"
          y2="15"
          stroke="rgba(139,92,246,0.35)"
          stroke-width="0.8"
        />
        <line
          x1="22"
          y1="26"
          x2="33"
          y2="29"
          stroke="rgba(139,92,246,0.35)"
          stroke-width="0.8"
        />
        <line
          x1="22"
          y1="26"
          x2="22"
          y2="35"
          stroke="rgba(139,92,246,0.35)"
          stroke-width="0.8"
        />
        <line
          x1="22"
          y1="26"
          x2="11"
          y2="29"
          stroke="rgba(139,92,246,0.35)"
          stroke-width="0.8"
        />
        <line
          x1="22"
          y1="18"
          x2="11"
          y2="15"
          stroke="rgba(139,92,246,0.35)"
          stroke-width="0.8"
        />
      </svg>
    </div>

    <!-- Product name above wordmark -->
    <p class="product-name" class:in={phase >= 2}>MappingMoney</p>

    <!-- Wordmark -->
    <div class="wordmark" class:in={phase >= 2}>
      <span class="word-graph">Graph</span><span class="word-sep">
        :
      </span><span class="word-lens">Lens</span>
    </div>

    <!-- Tagline -->
    <p class="tagline" class:in={phase >= 3}>Pharma Payment Intelligence</p>

    <!-- Divider line with gradient -->
    <div class="divider-line" class:in={phase >= 3}></div>

    <!-- Feature tags -->
    <div class="features" class:in={phase >= 4}>
      {#each FEATURES as f}
        <span class="feat-tag">
          <span class="feat-icon">{f.icon}</span>
          {f.label}
        </span>
      {/each}
    </div>

    <!-- CTA -->
    <button class="cta" class:in={phase >= 5} onclick={handleEnter}>
      Enter Dashboard
      <svg
        class="cta-arrow"
        width="15"
        height="15"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M5 12h14" /><path d="M12 5l7 7-7 7" />
      </svg>
    </button>

    <!-- Footer credit -->
    <p class="credit" class:in={phase >= 5}>
      CS 6242 · Georgia Tech · CMS Open Payments
    </p>
  </div>
</div>

<style>
  /* ── Shell ─────────────────────────────────────────────────── */
  .splash {
    position: fixed;
    inset: 0;
    z-index: 9000;
    background: #08090f;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: opacity 0.8s cubic-bezier(0.4, 0, 0.2, 1);
  }
  .splash.exiting {
    opacity: 0;
    pointer-events: none;
  }

  .splash-canvas {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }

  /* Corner pixel canvas sits above Three.js, below content */
  .pixel-canvas {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 2;
  }

  /* ── Very subtle radial glow ────────────────────────────── */
  .glow-orb {
    position: absolute;
    inset: 0;
    z-index: 3;
    background: radial-gradient(
      ellipse 50% 40% at 50% 52%,
      rgba(139, 92, 246, 0.055) 0%,
      rgba(139, 92, 246, 0.02) 50%,
      transparent 70%
    );
    pointer-events: none;
  }

  /* ── Content body ───────────────────────────────────────── */
  .splash-body {
    position: relative;
    z-index: 10;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 0;
    padding: 0 24px;
    max-width: 600px;
    width: 100%;
  }

  /* ── Entrance animation helper ──────────────────────────── */
  .logo-wrap,
  .product-name,
  .wordmark,
  .tagline,
  .divider-line,
  .features,
  .cta,
  .credit {
    opacity: 0;
    transform: translateY(14px);
    filter: blur(4px);
    transition:
      opacity 0.65s cubic-bezier(0.16, 1, 0.3, 1),
      transform 0.65s cubic-bezier(0.16, 1, 0.3, 1),
      filter 0.65s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .logo-wrap.in,
  .product-name.in,
  .wordmark.in,
  .tagline.in,
  .divider-line.in,
  .features.in,
  .cta.in,
  .credit.in {
    opacity: 1;
    transform: translateY(0);
    filter: blur(0);
  }

  /* ── Logo ───────────────────────────────────────────────── */
  .logo-wrap {
    margin-bottom: 20px;
  }

  /* ── Product name (MappingMoney) ────────────────────────── */
  .product-name {
    font-family: var(--font-display), system-ui, sans-serif;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 3.5px;
    text-transform: uppercase;
    color: rgba(196, 181, 253, 0.55);
    margin: 0 0 10px;
    /* slight delay so it appears just before the big wordmark */
    transition-delay: 0.04s;
  }

  /* ── Wordmark ───────────────────────────────────────────── */
  .wordmark {
    font-family: var(--font-display), system-ui, sans-serif;
    font-size: clamp(48px, 8.5vw, 82px);
    font-weight: 800;
    letter-spacing: -3px;
    line-height: 0.95;
    margin-bottom: 22px;
  }
  .word-graph {
    background: linear-gradient(160deg, #ffffff 0%, #ede9ff 60%, #c4b5fd 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .word-sep {
    /* muted separator */
    background: linear-gradient(
      160deg,
      rgba(196, 181, 253, 0.4) 0%,
      rgba(139, 92, 246, 0.35) 100%
    );
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: 0;
    font-weight: 300;
    font-size: 0.75em;
    vertical-align: middle;
    margin: 0 2px;
  }
  .word-lens {
    background: linear-gradient(160deg, #8b5cf6 0%, #a78bfa 55%, #c4b5fd 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  /* ── Tagline ────────────────────────────────────────────── */
  .tagline {
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: rgba(189, 200, 214, 0.45);
    margin: 0 0 20px;
    font-family: var(--font-sans), system-ui, sans-serif;
  }

  /* ── Divider ────────────────────────────────────────────── */
  .divider-line {
    width: 50px;
    height: 1px;
    background: linear-gradient(
      90deg,
      transparent,
      rgba(139, 92, 246, 0.6),
      transparent
    );
    margin-bottom: 28px;
    flex-shrink: 0;
  }

  /* ── Feature tags ───────────────────────────────────────── */
  .features {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: center;
    margin-bottom: 36px;
  }

  .feat-tag {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 500;
    color: rgba(189, 200, 214, 0.6);
    background: rgba(255, 255, 255, 0.025);
    border: 1px solid rgba(255, 255, 255, 0.06);
    font-family: var(--font-sans), system-ui, sans-serif;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
    transition:
      border-color 0.2s,
      color 0.2s;
  }
  .feat-tag:hover {
    border-color: rgba(139, 92, 246, 0.25);
    color: rgba(167, 139, 250, 0.9);
  }

  .feat-icon {
    font-size: 10px;
    opacity: 0.5;
  }

  /* ── CTA ────────────────────────────────────────────────── */
  .cta {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 13px 36px;
    border-radius: 9px;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.2px;
    cursor: pointer;
    font-family: var(--font-sans), system-ui, sans-serif;
    border: none;
    background: linear-gradient(135deg, #6d28d9, #9d6ff8);
    color: #f5f3ff;
    box-shadow:
      0 0 0 1px rgba(139, 92, 246, 0.35),
      0 4px 18px rgba(139, 92, 246, 0.18),
      0 1px 0 rgba(255, 255, 255, 0.12) inset;
    transition:
      box-shadow 0.2s,
      transform 0.2s;
    margin-bottom: 24px;
  }
  .cta:hover {
    box-shadow:
      0 0 0 1px rgba(167, 139, 250, 0.5),
      0 6px 28px rgba(139, 92, 246, 0.28),
      0 1px 0 rgba(255, 255, 255, 0.18) inset;
    transform: translateY(-2px);
  }
  .cta:active {
    transform: translateY(0);
  }

  .cta-arrow {
    transition: transform 0.2s;
  }
  .cta:hover .cta-arrow {
    transform: translateX(3px);
  }

  /* ── Credit ─────────────────────────────────────────────── */
  .credit {
    font-size: 10px;
    font-weight: 400;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: rgba(255, 255, 255, 0.14);
    margin: 0;
    font-family: var(--font-sans), system-ui, sans-serif;
  }
</style>
