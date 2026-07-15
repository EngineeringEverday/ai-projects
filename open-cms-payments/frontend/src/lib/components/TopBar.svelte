<script>
  import {
    Globe,
    Search,
    ShieldAlert,
    Network,
    Calendar,
    ChevronRight,
    Info,
  } from "lucide-svelte";
  import { selectedYear, activeMode, openNode } from "../stores.js";
  import { searchNodes } from "../api.js";

  let { route = "explore" } = $props();

  const YEARS = [2020, 2021, 2022, 2023, 2024];

  const modes = [
    {
      id: "explore",
      label: "Explore",
      icon: Globe,
      desc: "Map · Network · Products · Temporal",
    },
    {
      id: "investigate",
      label: "Investigate",
      icon: Search,
      desc: "Search any entity, get full dossier",
    },
    {
      id: "risk",
      label: "Risk",
      icon: ShieldAlert,
      desc: "Anomalies · Concentration · Communities",
    },
    {
      id: "about",
      label: "About",
      icon: Info,
      desc: "Project details and team",
    },
  ];

  function setMode(id) {
    activeMode.set(id);
    window.location.hash = id;
  }

  // ── Global search ────────────────────────────────────────────
  let query = $state("");
  let results = $state([]);
  let open = $state(false);
  let inputEl = $state(null);
  let timer;

  const TYPE_COLOR = {
    Physician: "#4e79a7",
    Manufacturer: "#f28e2b",
    TeachingHospital: "#e15759",
  };

  function onInput() {
    clearTimeout(timer);
    if (query.trim().length < 2) {
      results = [];
      open = false;
      return;
    }
    timer = setTimeout(async () => {
      try {
        const d = await searchNodes(query.trim(), $selectedYear, 10);
        results = d.rows ?? [];
        open = results.length > 0;
      } catch {
        results = [];
        open = false;
      }
    }, 240);
  }

  function pick(r) {
    openNode(r.id);
    query = "";
    results = [];
    open = false;
  }

  function onKeydown(e) {
    if (e.key === "Escape") {
      query = "";
      results = [];
      open = false;
    }
  }

  // ⌘K global shortcut
  $effect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputEl?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });
</script>

<header class="topbar">
  <!-- Brand -->
  <a
    class="brand"
    href="#explore"
    onclick={(e) => {
      e.preventDefault();
      setMode("explore");
    }}
  >
    <div class="brand-icon">
      <Network size={16} color="#8B5CF6" />
    </div>
    <div class="brand-text">
      <span class="brand-name">MappingMoney: Graph Lens</span>
    </div>
  </a>

  <!-- Divider -->
  <div class="v-divider"></div>

  <!-- Mode nav -->
  <nav class="mode-nav" aria-label="Main navigation">
    {#each modes as m}
      {@const Icon = m.icon}
      <button
        class="mode-btn"
        class:active={route === m.id}
        onclick={() => setMode(m.id)}
        title={m.desc}
        aria-current={route === m.id ? "page" : undefined}
      >
        <span class="mode-icon-wrap">
          <Icon size={14} />
        </span>
        <span class="mode-label">{m.label}</span>
        {#if route === m.id}
          <span class="mode-active-dot"></span>
        {/if}
      </button>
    {/each}
  </nav>

  <!-- Spacer -->
  <div style="flex:1"></div>

  <!-- Right: year + search -->
  <div class="topbar-right">
    <!-- Year selector -->
    <div class="year-selector">
      <Calendar size={12} color="var(--color-muted)" />
      <div class="year-pills">
        {#each YEARS as y}
          <button
            class="year-pill"
            class:active={$selectedYear === y}
            onclick={() => selectedYear.set(y)}>{y}</button
          >
        {/each}
      </div>
    </div>

    <div class="v-divider"></div>

    <!-- Search box -->
    <div class="search-wrap">
      <span class="search-icon-left">
        <Search size={13} color="var(--color-muted)" />
      </span>
      <input
        bind:this={inputEl}
        type="text"
        placeholder="Search entity…"
        bind:value={query}
        oninput={onInput}
        onkeydown={onKeydown}
        onblur={() =>
          setTimeout(() => {
            open = false;
          }, 160)}
        class="search-input"
        aria-label="Search entities"
      />
      <kbd class="search-kbd">⌘K</kbd>

      {#if open && results.length}
        <div class="search-dropdown" role="listbox">
          {#each results as r}
            {@const dot = TYPE_COLOR[r.node_type] ?? "#888"}
            <button
              class="search-result"
              role="option"
              aria-selected="false"
              onmousedown={() => pick(r)}
            >
              <span class="result-dot" style="background:{dot}"></span>
              <span class="result-name">{r.name ?? r.id}</span>
              <span class="result-type" style="color:{dot}">{r.node_type}</span>
              <span class="result-state">{r.state ?? "-"}</span>
              <ChevronRight size={11} color="var(--color-subtle)" />
            </button>
          {/each}
        </div>
      {/if}
    </div>
  </div>
</header>

<style>
  /* ── Topbar ──────────────────────────────────────────────── */
  .topbar {
    display: flex;
    align-items: center;
    height: var(--topbar-h);
    padding: 0 20px 0 0;
    gap: 0;
  }

  /* ── Brand ───────────────────────────────────────────────── */
  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 22px;
    height: 100%;
    text-decoration: none;
    flex-shrink: 0;
    transition: opacity 0.15s;
  }
  .brand:hover {
    opacity: 0.85;
  }

  .brand-icon {
    width: 30px;
    height: 30px;
    background: rgba(139, 92, 246, 0.08);
    border: 1px solid rgba(139, 92, 246, 0.22);
    border-radius: 7px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .brand-text {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }
  .brand-name {
    font-size: 15px;
    font-weight: 800;
    color: var(--color-heading);
    letter-spacing: -0.5px;
    line-height: 1;
    font-family: var(--font-display);
  }
  .brand-sub {
    font-size: 9px;
    color: var(--color-muted);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    font-weight: 600;
    line-height: 1;
  }

  /* ── Dividers ─────────────────────────────────────────────── */
  .v-divider {
    width: 1px;
    height: 24px;
    background: var(--color-border);
    flex-shrink: 0;
    margin: 0 4px;
  }

  /* ── Mode nav ────────────────────────────────────────────── */
  .mode-nav {
    display: flex;
    align-items: center;
    height: 100%;
    padding: 0 4px;
  }

  .mode-btn {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 0 16px;
    height: 100%;
    font-size: 13px;
    font-weight: 500;
    color: var(--color-muted);
    cursor: pointer;
    border: none;
    background: transparent;
    border-bottom: 2px solid transparent;
    transition: all 0.15s;
    font-family: var(--font-sans);
    white-space: nowrap;
  }
  .mode-btn:hover {
    color: var(--color-text);
    background: var(--color-hover);
  }
  .mode-btn.active {
    color: var(--color-heading);
    border-bottom-color: var(--color-accent);
    font-weight: 600;
  }
  .mode-icon-wrap {
    display: flex;
    align-items: center;
    opacity: 0.75;
    transition: opacity 0.15s;
  }
  .mode-btn.active .mode-icon-wrap {
    opacity: 1;
  }
  .mode-btn:hover .mode-icon-wrap {
    opacity: 1;
  }
  .mode-label {
    line-height: 1;
  }

  .mode-active-dot {
    position: absolute;
    bottom: -1px;
    left: 50%;
    transform: translateX(-50%);
    width: 3px;
    height: 3px;
    border-radius: 50%;
    background: var(--color-accent);
  }

  /* ── Right section ───────────────────────────────────────── */
  .topbar-right {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }

  /* ── Year selector ───────────────────────────────────────── */
  .year-selector {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .year-pills {
    display: flex;
    gap: 2px;
  }
  .year-pill {
    padding: 4px 9px;
    border-radius: 5px;
    font-size: 11px;
    font-weight: 600;
    color: var(--color-muted);
    background: transparent;
    border: 1px solid transparent;
    cursor: pointer;
    transition: all 0.12s;
    font-family: var(--font-sans);
  }
  .year-pill:hover {
    color: var(--color-text);
    background: var(--color-hover);
  }
  .year-pill.active {
    color: var(--color-accent);
    background: var(--color-accent-dim);
    border-color: rgba(139, 92, 246, 0.28);
    font-weight: 600;
  }

  /* ── Search ──────────────────────────────────────────────── */
  .search-wrap {
    position: relative;
    display: flex;
    align-items: center;
  }
  .search-icon-left {
    position: absolute;
    left: 9px;
    display: flex;
    align-items: center;
    pointer-events: none;
    z-index: 1;
  }
  .search-input {
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 6px 52px 6px 30px;
    font-size: 12px;
    color: var(--color-text);
    width: 200px;
    outline: none;
    transition:
      border-color 0.15s,
      width 0.22s cubic-bezier(0.16, 1, 0.3, 1),
      box-shadow 0.15s;
    font-family: var(--font-sans);
  }
  .search-input::placeholder {
    color: var(--color-muted);
  }
  .search-input:focus {
    border-color: var(--color-accent);
    box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.12);
    width: 260px;
  }

  .search-kbd {
    position: absolute;
    right: 8px;
    font-size: 9px;
    color: var(--color-subtle);
    background: var(--color-hover);
    border: 1px solid var(--color-border);
    border-radius: 4px;
    padding: 2px 5px;
    pointer-events: none;
    font-family: var(--font-sans);
    letter-spacing: 0.3px;
  }

  .search-dropdown {
    position: absolute;
    top: calc(100% + 6px);
    right: 0;
    min-width: 320px;
    background: var(--color-card-2);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    box-shadow: 0 16px 40px rgba(1, 4, 9, 0.6);
    z-index: 500;
    overflow: hidden;
    animation: slide-in-bottom 0.15s cubic-bezier(0.16, 1, 0.3, 1);
  }

  @keyframes slide-in-bottom {
    from {
      opacity: 0;
      transform: translateY(-6px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .search-result {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 10px 14px;
    border: none;
    background: transparent;
    cursor: pointer;
    border-bottom: 1px solid var(--color-border);
    transition: background 0.1s;
    font-family: var(--font-sans);
  }
  .search-result:last-child {
    border-bottom: none;
  }
  .search-result:hover {
    background: var(--color-hover);
  }

  .result-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .result-name {
    flex: 1;
    font-size: 12px;
    font-weight: 500;
    color: var(--color-heading);
    text-align: left;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .result-type {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    flex-shrink: 0;
  }
  .result-state {
    font-size: 10px;
    color: var(--color-muted);
    flex-shrink: 0;
    background: var(--color-hover);
    padding: 1px 6px;
    border-radius: 3px;
    font-weight: 600;
  }
</style>
