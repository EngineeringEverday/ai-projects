<script>
  import YearSelector from "./YearSelector.svelte";
  import { selectedYear } from "../stores.js";
  import { searchNodes } from "../api.js";

  let { route } = $props();

  const navItems = [
    { id: "dashboard", label: "Dashboard", icon: "▦", tip: "Overview: key stats, top payers, anomaly counts, and community map" },
    { id: "graph", label: "Network Graph", icon: "◎", tip: "Interactive force-directed graph of physician–company payment relationships" },
    { id: "centrality", label: "Centrality", icon: "★", tip: "Rank nodes by PageRank, betweenness, authority score, and payment diversity" },
    { id: "anomalies", label: "Anomalies", icon: "⚑", tip: "Outlier detection: statistically unusual payment patterns and single-payer capture" },
    { id: "communities", label: "Communities", icon: "⬡", tip: "Payment clusters detected via Louvain community detection algorithm" },
    { id: "temporal", label: "Temporal", icon: "⌛", tip: "Year-over-year payment evolution, jumps, and emerging relationships" },
    { id: "concentration", label: "Concentration", icon: "◈", tip: "Market concentration metrics: Gini coefficient, HHI, entropy by specialty / state" },
    { id: "products", label: "Products", icon: "✦", tip: "Top drugs and medical devices by payment volume and physician reach" },
  ];

  const navClass = (id) =>
    id === route
      ? "bg-accent/15 text-accent"
      : "text-muted hover:bg-white/5 hover:text-text";

  // ── Global search ─────────────────────────────────────────────
  let query = $state("");
  let results = $state([]);
  let open = $state(false);
  let timer;

  const TYPE_COLOR = {
    physician: "#4e79a7",
    manufacturer: "#f28e2b",
    teachinghospital: "#e15759",
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
        const d = await searchNodes(query.trim(), $selectedYear, 8);
        results = d.rows ?? [];
        open = results.length > 0;
      } catch {
        results = [];
        open = false;
      }
    }, 280);
  }

  function pick(r) {
    window.location.hash = `node/${r.id}`;
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

  function onBlur() {
    // Small delay so click on result fires first
    setTimeout(() => {
      open = false;
    }, 150);
  }
</script>

<aside
  class="bg-sidebar border-r border-border flex flex-col h-screen sticky top-0 overflow-y-auto w-55"
>
  <!-- Brand -->
  <div
    class="flex items-center gap-4 px-4 pt-4.5 pb-3.5 border-b border-border"
  >
    <span class="text-accent text-xl leading-none">◈</span>
    <div>
      <div class="text-[15px] font-bold text-heading tracking-[0.3px]">
        MappingMoney: Graph Lens
      </div>
    </div>
  </div>

  <!-- Global search -->
  <div class="px-3 pt-2.5 pb-2 border-b border-border relative">
    <div class="relative">
      <span
        class="absolute left-2 top-1/2 -translate-y-1/2 text-muted text-[11px] pointer-events-none"
        >⌕</span
      >
      <input
        type="text"
        placeholder="Search nodes…"
        bind:value={query}
        oninput={onInput}
        onkeydown={onKeydown}
        onblur={onBlur}
        class="w-full bg-bg border border-border rounded-md pl-6 pr-2 py-1.5 text-[12px]
               text-text placeholder:text-muted outline-none
               focus:border-accent transition-colors"
      />
    </div>

    {#if open && results.length}
      <div
        class="absolute left-3 right-3 top-[calc(100%+2px)] bg-card border border-border
                  rounded-md shadow-xl z-50 overflow-hidden"
      >
        {#each results as r}
          {@const tc = TYPE_COLOR[(r.node_type ?? "").toLowerCase()] ?? "#888"}
          <button
            class="w-full text-left px-3 py-2 hover:bg-hover transition-colors cursor-pointer border-b border-border last:border-0"
            onmousedown={() => pick(r)}
          >
            <div class="flex items-center gap-1.5">
              <span
                class="w-1.5 h-1.5 rounded-full shrink-0"
                style="background:{tc}"
              ></span>
              <span class="font-medium text-[12px] text-text truncate"
                >{r.name ?? r.id}</span
              >
            </div>
            <div class="text-[10px] text-muted mt-0.5 pl-3">
              {r.node_type} · {r.state ?? ""}
            </div>
          </button>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Year selector -->
  <div class="px-4 pt-3 pb-2 border-b border-border">
    <div
      class="text-[10px] font-semibold uppercase tracking-[0.8px] text-muted mb-2"
    >
      Year
    </div>
    <YearSelector />
  </div>

  <!-- Nav -->
  <nav class="flex-1 p-2">
    {#each navItems as item}
      <a
        href="#{item.id}"
        class="flex items-center gap-2.5 px-2.5 py-2 rounded-md text-[13px] font-medium mb-0.5 transition-colors duration-100 {navClass(
          item.id,
        )}"
        title={item.tip}
      >
        <span class="w-4.5 text-center text-[13px]">{item.icon}</span>
        {item.label}
      </a>
    {/each}
  </nav>

  <!-- Footer -->
  <div
    class="px-4 py-3 border-t border-border text-[10px] text-muted tracking-[0.3px]"
  >
    2020 – 2024 · CS6242
  </div>
</aside>
