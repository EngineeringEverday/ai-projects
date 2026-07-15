<script>
  import TopBar from "./lib/components/TopBar.svelte";
  import NodePanel from "./lib/components/NodePanel.svelte";
  import SplashScreen from "./lib/components/SplashScreen.svelte";

  import { activeMode, panelNodeId, openNode } from "./lib/stores.js";
  import { onMount } from "svelte";

  // ── Splash screen gate ──────────────────────────────────────────
  let splashDone = $state(false);

  function onEnter() {
    splashDone = true;
  }

  // ── Hash router ────────────────────────────────────────────────
  let lastMode = "explore";

  function parseHash(raw) {
    const h = (raw + "").replace(/^#/, "") || "explore";
    if (h.startsWith("node/")) {
      openNode(h.slice(5));
      return lastMode;
    }
    lastMode = h;
    return h;
  }

  let route = $state(parseHash(window.location.hash));

  $effect(() => {
    const unsub = activeMode.subscribe((m) => {
      if (m !== route) {
        route = m;
        history.replaceState(null, "", `#${m}`);
      }
    });
    return unsub;
  });

  $effect(() => {
    const handler = () => {
      const r = parseHash(window.location.hash);
      route = r;
      activeMode.set(r);
    };
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  });

  // ── Dynamic route loading with module cache ─────────────────────
  const _routeCache = {};

  function getRoute(name) {
    if (!_routeCache[name]) {
      const loaders = {
        explore: () => import("./lib/routes/Explore.svelte"),
        investigate: () => import("./lib/routes/Investigate.svelte"),
        risk: () => import("./lib/routes/Risk.svelte"),
        about: () => import("./lib/routes/About.svelte"),
      };
      _routeCache[name] = (loaders[name] ?? loaders.explore)().then(
        (m) => m.default,
      );
    }
    return _routeCache[name];
  }

  // Preload explore immediately; preload others after 2s
  getRoute("explore");
  setTimeout(() => {
    getRoute("investigate");
    getRoute("risk");
    getRoute("about");
  }, 2000);

  // ── Background particles ────────────────────────────────────────
  let particleCanvas = $state(null);

  function deriveTooltipText(el) {
    const fromData = el.getAttribute("data-tooltip") || "";
    const fromAria = el.getAttribute("aria-label") || "";

    let fromLabelledBy = "";
    const labelledBy = el.getAttribute("aria-labelledby");
    if (labelledBy) {
      fromLabelledBy = labelledBy
        .split(/\s+/)
        .map((id) => document.getElementById(id)?.textContent?.trim() || "")
        .filter(Boolean)
        .join(" ");
    }

    let fromAssocLabel = "";
    const id = el.getAttribute("id");
    if (id) {
      const label = document.querySelector(`label[for="${id}"]`);
      fromAssocLabel = label?.textContent?.trim() || "";
    }

    const fromPlaceholder = el.getAttribute("placeholder") || "";
    const fromValue =
      el instanceof HTMLOptionElement
        ? el.label || el.textContent || ""
        : el.textContent || "";
    const fromName = el.getAttribute("name") || "";

    const text = [
      fromData,
      fromAria,
      fromLabelledBy,
      fromAssocLabel,
      fromPlaceholder,
      fromValue,
      fromName,
    ]
      .map((v) => (v || "").replace(/\s+/g, " ").trim())
      .find(Boolean);

    if (!text) return "";
    return text.length > 120 ? `${text.slice(0, 117)}...` : text;
  }

  function applyGlobalTooltips(root = document) {
    const selector = [
      "button",
      "a",
      "input",
      "select",
      "option",
      "textarea",
      "label",
      "[role='tab']",
      "[role='button']",
      "[role='option']",
      "[role='menuitem']",
      "[data-tooltip]",
    ].join(",");

    root.querySelectorAll(selector).forEach((el) => {
      if (el.hasAttribute("title")) return;
      const text = deriveTooltipText(el);
      if (text) el.setAttribute("title", text);
    });
  }

  onMount(() => {
    const canvas = particleCanvas;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    let raf;

    const COLORS = [
      [139, 92, 246], // violet
      [167, 139, 250], // violet-light
      [245, 158, 11], // amber
      [96, 165, 250], // blue
    ];

    // Spawn N particles
    const N = 48;
    const particles = Array.from({ length: N }, () => mkParticle(true));

    function mkParticle(init = false) {
      const [r, g, b] = COLORS[Math.floor(Math.random() * COLORS.length)];
      return {
        x: Math.random() * window.innerWidth,
        y: init ? Math.random() * window.innerHeight : window.innerHeight + 8,
        size: 0.8 + Math.random() * 1.8,
        speedY: 0.18 + Math.random() * 0.32,
        speedX: (Math.random() - 0.5) * 0.12,
        alpha: 0,
        maxAlpha: 0.1 + Math.random() * 0.14,
        fadeIn: 0.003 + Math.random() * 0.003,
        r,
        g,
        b,
      };
    }

    function resize() {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener("resize", resize);

    function draw(ts) {
      raf = requestAnimationFrame(draw);
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      for (const p of particles) {
        p.y -= p.speedY;
        p.x += p.speedX;
        p.alpha = Math.min(p.alpha + p.fadeIn, p.maxAlpha);

        if (p.y < -8 || p.x < -8 || p.x > canvas.width + 8) {
          Object.assign(p, mkParticle(false));
        }

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${p.r},${p.g},${p.b},${p.alpha.toFixed(3)})`;
        ctx.fill();
      }
    }

    raf = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  });

  onMount(() => {
    // Keep native hover tooltips present for controls as routes and panels update.
    applyGlobalTooltips(document);

    let scheduled = false;
    const observer = new MutationObserver((mutations) => {
      if (scheduled) return;
      const hasRelevantChange = mutations.some(
        (m) => m.type === "childList" || m.type === "attributes",
      );
      if (!hasRelevantChange) return;

      scheduled = true;
      requestAnimationFrame(() => {
        applyGlobalTooltips(document);
        scheduled = false;
      });
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["aria-label", "aria-labelledby", "placeholder", "data-tooltip"],
    });

    return () => observer.disconnect();
  });
</script>

<!-- ── Background particle canvas ───────────────────────────────── -->
<canvas
  bind:this={particleCanvas}
  style="position:fixed;inset:0;pointer-events:none;z-index:0;"
  aria-hidden="true"
></canvas>

<!-- ── Splash gate ──────────────────────────────────────────────── -->
{#if !splashDone}
  <SplashScreen {onEnter} />
{/if}

<!-- ── Main app (rendered under splash, visible after entry) ───── -->
<div class="app-shell" class:app-visible={splashDone}>
  <TopBar {route} />

  <main class="main-content">
    {#await getRoute(route)}
      <div class="loading-center">
        <div class="spinner"></div>
        <span>Loading…</span>
      </div>
    {:then Component}
      {#key route}
        <div class="route-view">
          <Component />
        </div>
      {/key}
    {:catch}
      <div class="error-msg">Failed to load view. Please refresh.</div>
    {/await}
  </main>
</div>

<!-- ── Node dossier overlay ─────────────────────────────────────── -->
{#if $panelNodeId}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="panel-backdrop animate-fade-in"
    onclick={() => panelNodeId.set(null)}
  ></div>
  <div class="node-panel animate-slide-in">
    <NodePanel id={$panelNodeId} onClose={() => panelNodeId.set(null)} />
  </div>
{/if}

<style>
  .app-shell {
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.5s ease 0.2s;
  }
  .app-shell.app-visible {
    opacity: 1;
    pointer-events: auto;
  }
</style>
