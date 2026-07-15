<script>
  import { selectedYear, openNode } from "../stores.js";
  import { searchNodes, getCentrality, getNodesByType } from "../api.js";
  import PlotlyChart from "../components/PlotlyChart.svelte";
  import {
    Search,
    Building2,
    Stethoscope,
    Hospital,
    TriangleAlert,
    ChevronRight,
  } from "lucide-svelte";

  // ── Search state ──────────────────────────────────────────────
  let query = $state("");
  let results = $state([]);
  let searching = $state(false);
  let timer;
  let inputEl = $state(null);

  // ── Top-list browsing ─────────────────────────────────────────
  let topTab = $state("manufacturers"); // 'manufacturers' | 'physicians' | 'hospitals'
  let topPromise = $derived(loadTopList(topTab));

  async function loadTopList(type) {
    const typeMap = {
      manufacturers: "Manufacturer",
      physicians: "Physician",
      hospitals: "TeachingHospital",
    };
    return getNodesByType($selectedYear, typeMap[type], 20);
  }

  const TYPE_COLOR = {
    Physician: "#2F81F7",
    Manufacturer: "#F0883E",
    TeachingHospital: "#F85149",
  };

  function onInput() {
    clearTimeout(timer);
    if (query.trim().length < 2) {
      results = [];
      return;
    }
    searching = true;
    timer = setTimeout(async () => {
      try {
        const d = await searchNodes(query.trim(), $selectedYear, 20);
        results = d.rows ?? [];
      } catch {
        results = [];
      } finally {
        searching = false;
      }
    }, 220);
  }

  // ── Top entities by payment (for the leaderboard) ─────────────
  // Physicians + Hospitals receive payments → in_strength
  // Manufacturers pay out → out_strength
  // For physicians: composite rank = weighted(pagerank, in_strength, in_degree, betweenness)
  let centralityPromise = $derived(
    getCentrality(
      $selectedYear,
      "in_strength",
      60,
      "id,name,node_type,state,in_strength,in_degree,cash_ratio,pagerank,betweenness,out_degree",
    ),
  );
  let mfrCentralityPromise = $derived(
    getCentrality(
      $selectedYear,
      "out_strength",
      30,
      "id,name,node_type,out_strength,out_degree",
    ),
  );

  // Composite influence score - normalises each metric to [0,1] then weights
  // Weights: payment volume 40%, PageRank 30%, connections 20%, betweenness 10%
  function compositeScore(rows) {
    if (!rows?.length) return [];
    const max = (key) => Math.max(...rows.map((r) => r[key] ?? 0), 1);
    const mIS = max("in_strength"),
      mPR = max("pagerank"),
      mID = max("in_degree"),
      mBT = max("betweenness");
    return rows
      .map((r) => ({
        ...r,
        composite:
          0.4 * ((r.in_strength ?? 0) / mIS) +
          0.3 * ((r.pagerank ?? 0) / mPR) +
          0.2 * ((r.in_degree ?? 0) / mID) +
          0.1 * ((r.betweenness ?? 0) / mBT),
      }))
      .sort((a, b) => b.composite - a.composite);
  }

  function fmtUSD(n) {
    if (!n) return "$0";
    if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
    if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
    if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
    return `$${(+n).toFixed(0)}`;
  }

  // ── Distribution chart ─────────────────────────────────────────
  function buildDistribution(rows) {
    const physicians = rows.filter((r) => r.node_type === "Physician");
    const mfrs = rows.filter((r) => r.node_type === "Manufacturer");

    return [
      {
        type: "bar",
        name: "Physicians",
        x: physicians.map((r) => (r.name ?? r.id ?? "").slice(0, 20)),
        y: physicians.map((r) => r.in_strength ?? 0),
        marker: { color: "#2F81F7", opacity: 0.85 },
        hovertemplate: "<b>%{x}</b><br>$%{y:,.0f}<extra></extra>",
      },
      {
        type: "bar",
        name: "Manufacturers",
        x: mfrs.map((r) => (r.name ?? r.id ?? "").slice(0, 20)),
        y: mfrs.map((r) => r.in_strength ?? 0),
        marker: { color: "#F0883E", opacity: 0.85 },
        hovertemplate: "<b>%{x}</b><br>$%{y:,.0f}<extra></extra>",
      },
    ];
  }

  const distLayout = {
    barmode: "group",
    margin: { t: 8, r: 16, b: 80, l: 80 },
    xaxis: { tickangle: -40, tickfont: { size: 9, color: "#7D8590" } },
    yaxis: {
      tickprefix: "$",
      tickfont: { size: 10, color: "#7D8590" },
      gridcolor: "#30363D",
    },
    legend: { font: { size: 10, color: "#7D8590" } },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
  };

  // ── Scatter: Payment × Cash ratio ─────────────────────────────
  function buildRiskScatter(rows) {
    return [
      {
        type: "scatter",
        mode: "markers",
        x: rows.map((r) => r.in_strength ?? 0),
        y: rows.map((r) => (r.cash_ratio ?? 0) * 100),
        text: rows.map((r) => r.name ?? r.id ?? ""),
        customdata: rows.map((r) => r.id),
        marker: {
          color: rows.map((r) =>
            (r.cash_ratio ?? 0) > 0.5 ? "#F85149" : "#2F81F7",
          ),
          size: 8,
          opacity: 0.75,
          line: { color: "rgba(0,0,0,0.2)", width: 0.5 },
        },
        hovertemplate:
          "<b>%{text}</b><br>Received: $%{x:,.0f}<br>Cash: %{y:.1f}%<extra></extra>",
      },
    ];
  }

  const riskScatterLayout = {
    margin: { t: 8, r: 20, b: 48, l: 80 },
    xaxis: {
      title: {
        text: "Total Received (USD)",
        font: { color: "#7D8590", size: 10 },
      },
      type: "log",
      tickprefix: "$",
      tickfont: { size: 10, color: "#7D8590" },
      gridcolor: "#30363D",
    },
    yaxis: {
      title: { text: "Cash Ratio (%)", font: { color: "#7D8590", size: 10 } },
      ticksuffix: "%",
      tickfont: { size: 10, color: "#7D8590" },
      gridcolor: "#30363D",
    },
    shapes: [
      {
        type: "line",
        x0: 0,
        x1: 1e8,
        y0: 50,
        y1: 50,
        xref: "x",
        yref: "y",
        line: { color: "rgba(248,81,73,0.4)", width: 1.5, dash: "dash" },
      },
    ],
    annotations: [
      {
        x: 6,
        y: 52,
        xref: "x",
        yref: "y",
        text: "50% cash threshold",
        font: { size: 9, color: "#F85149" },
        showarrow: false,
      },
    ],
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
  };
</script>

<!-- ── Page header ────────────────────────────────────────────────── -->
<div style="margin-bottom:20px">
  <h1 class="page-title">Investigate</h1>
  <p
    style="font-size:12px;color:var(--color-muted);margin:3px 0 0;font-family:var(--font-sans)"
  >
    Search any physician, hospital, or company to pull their full dossier -
    payments, centrality, network connections, and risk indicators.
  </p>
</div>

<!-- ── Hero Search ────────────────────────────────────────────────── -->
<div class="hero-search">
  <div class="hero-search-inner">
    <span class="hero-icon-wrap"
      ><Search size={20} color="var(--color-muted)" /></span
    >
    <input
      bind:this={inputEl}
      type="text"
      placeholder="Search doctor, hospital, company…"
      bind:value={query}
      oninput={onInput}
      class="hero-input"
      aria-label="Search entities"
    />
    {#if searching}
      <div
        class="spinner"
        style="width:18px;height:18px;border-width:1.5px;margin-right:12px"
      ></div>
    {/if}
  </div>

  {#if query.length >= 2 && results.length > 0}
    <div class="hero-results">
      {#each results as r}
        {@const dot = TYPE_COLOR[r.node_type] ?? "#888"}
        <button
          class="hero-result"
          onclick={() => {
            openNode(r.id);
            query = "";
            results = [];
          }}
        >
          <div class="hr-left">
            <span class="hr-dot" style="background:{dot}"></span>
            <div>
              <div class="hr-name">{r.name ?? r.id}</div>
              <div class="hr-meta">
                {r.node_type} · {r.state ?? "-"}{r.specialty
                  ? " · " + r.specialty.split("|").pop()
                  : ""}
              </div>
            </div>
          </div>
          <span class="hr-arrow"><ChevronRight size={16} /></span>
        </button>
      {/each}
    </div>
  {:else if query.length >= 2 && !searching && results.length === 0}
    <div
      style="padding:20px;text-align:center;color:var(--color-muted);font-size:12px"
    >
      No results for "{query}" in {$selectedYear}
    </div>
  {/if}
</div>

<!-- ── Body: two-column layout ────────────────────────────────────── -->
<div class="body-grid">
  <!-- Left: Top entities leaderboard -->
  <div>
    <div class="section-label" style="margin-bottom:10px">
      Top Entities by Payment Volume · {$selectedYear}
    </div>
    <div style="display:flex;gap:2px;margin-bottom:10px">
      <button
        class="tab-btn"
        class:active={topTab === "manufacturers"}
        onclick={() => (topTab = "manufacturers")}
        title="Top pharmaceutical manufacturers by total payments sent"
      >
        <Building2 size={12} /> Manufacturers
      </button>
      <button
        class="tab-btn"
        class:active={topTab === "physicians"}
        onclick={() => (topTab = "physicians")}
        title="Top physicians by total payments received"
      >
        <Stethoscope size={12} /> Physicians
      </button>
      <button
        class="tab-btn"
        class:active={topTab === "hospitals"}
        onclick={() => (topTab = "hospitals")}
        title="Top teaching hospitals by total payments received"
      >
        <Hospital size={12} /> Hospitals
      </button>
    </div>

    {#if topTab === "manufacturers"}
      {#await mfrCentralityPromise}
        <div class="loading-center" style="padding:20px">
          <div class="spinner"></div>
        </div>
      {:then data}
        {@const filtered = (data.rows ?? [])
          .filter((r) => r.node_type === "Manufacturer")
          .slice(0, 15)}
        <div class="leaderboard">
          {#each filtered as r, i}
            <button class="lb-row" onclick={() => openNode(r.id)}>
              <span class="lb-rank">#{i + 1}</span>
              <span class="lb-dot" style="background:#F0883E"></span>
              <div class="lb-info">
                <div class="lb-name">{(r.name ?? r.id ?? "").slice(0, 34)}</div>
                <div class="lb-meta">{r.out_degree ?? 0} recipients</div>
              </div>
              <div class="lb-amount">{fmtUSD(r.out_strength)}</div>
            </button>
          {/each}
        </div>
      {:catch e}
        <div class="error-msg">{e.message}</div>
      {/await}
    {:else}
      {#await centralityPromise}
        <div class="loading-center" style="padding:20px">
          <div class="spinner"></div>
        </div>
      {:then data}
        {@const nodeType =
          topTab === "hospitals" ? "TeachingHospital" : "Physician"}
        {@const dot = TYPE_COLOR[nodeType] ?? "#888"}
        {@const raw = (data.rows ?? []).filter((r) => r.node_type === nodeType)}
        {@const ranked = compositeScore(raw).slice(0, 15)}

        <!-- Composite rank legend -->
        <div class="composite-legend">
          <span class="cl-item" style="--c:#2F81F7">40% Volume</span>
          <span class="cl-item" style="--c:#8957E5">30% PageRank</span>
          <span class="cl-item" style="--c:#3FB950">20% Connections</span>
          <span class="cl-item" style="--c:#F0883E">10% Betweenness</span>
        </div>

        <div class="leaderboard">
          {#each ranked as r, i}
            {@const cashRisk = (r.cash_ratio ?? 0) > 0.5}
            {@const scorePct = (r.composite * 100).toFixed(1)}
            <button class="lb-row" onclick={() => openNode(r.id)}>
              <span class="lb-rank">#{i + 1}</span>
              <span class="lb-dot" style="background:{dot}"></span>
              <div class="lb-info">
                <div class="lb-name">{(r.name ?? r.id ?? "").slice(0, 32)}</div>
                <!-- Composite score bar -->
                <div class="composite-bar-wrap">
                  <div
                    class="composite-bar"
                    style="width:{scorePct}%;background:linear-gradient(90deg,#2F81F7,#8957E5)"
                  ></div>
                </div>
                <div class="lb-meta">
                  Score {scorePct}% &nbsp;·&nbsp; {r.in_degree ?? 0} payers &nbsp;·&nbsp;
                  PR {((r.pagerank ?? 0) * 1e5).toFixed(2)}
                  {#if cashRisk}&nbsp;·&nbsp;<TriangleAlert
                      size={10}
                      color="var(--color-warning)"
                    />{/if}
                </div>
              </div>
              <div class="lb-amount">
                {fmtUSD(r.in_strength)}
                {#if cashRisk}
                  <span class="risk-dot risk-dot-high" style="margin-left:4px"
                  ></span>
                {/if}
              </div>
            </button>
          {/each}
        </div>
      {:catch e}
        <div class="error-msg">{e.message}</div>
      {/await}
    {/if}
  </div>

  <!-- Right: Charts -->
  <div>
    <div class="section-label" style="margin-bottom:10px">
      Payment vs. Cash Risk · Top 30 entities
    </div>
    {#await centralityPromise}
      <div class="loading-center"><div class="spinner"></div></div>
    {:then data}
      <div class="card" style="margin-bottom:14px">
        <div class="insight-block" style="margin-bottom:10px">
          Points above the <span style="color:#F85149">red dashed line</span> receive
          more than 50% of their payments in cash - a pattern associated with undisclosed
          financial relationships under CMS Open Payments rules. Click a point to
          open its dossier.
        </div>
        <PlotlyChart
          traces={buildRiskScatter(data.rows ?? [])}
          layout={riskScatterLayout}
          height={280}
          onClick={(pt) => {
            if (pt.customdata) openNode(pt.customdata);
          }}
        />
      </div>

      <div class="card">
        <div class="section-label" style="margin-bottom:8px">
          Top Entities - Total Received
        </div>
        <PlotlyChart
          traces={buildDistribution(data.rows ?? [])}
          layout={distLayout}
          height={240}
          onClick={(pt) => {
            const row = (data.rows ?? []).find((r) =>
              (r.name ?? r.id ?? "").startsWith(pt.x?.slice?.(0, 10) ?? ""),
            );
            if (row) openNode(row.id);
          }}
        />
      </div>
    {:catch e}
      <div class="error-msg">{e.message}</div>
    {/await}
  </div>
</div>

<style>
  /* Composite rank legend */
  .composite-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 8px;
  }
  .cl-item {
    font-size: 9px;
    font-weight: 700;
    color: var(--c, var(--color-muted));
    background: color-mix(in srgb, var(--c, #888) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--c, #888) 30%, transparent);
    border-radius: 999px;
    padding: 2px 8px;
    letter-spacing: 0.3px;
    font-family: var(--font-sans);
  }

  /* Composite score bar */
  .composite-bar-wrap {
    width: 100%;
    height: 3px;
    background: var(--color-hover);
    border-radius: 2px;
    margin: 3px 0 2px;
    overflow: hidden;
  }
  .composite-bar {
    height: 100%;
    border-radius: 2px;
    transition: width 0.3s ease;
  }

  /* Hero search */
  .hero-search {
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: 12px;
    overflow: hidden;
    margin-bottom: 24px;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
  }
  .hero-search:focus-within {
    border-color: var(--color-accent);
    box-shadow:
      0 0 0 3px rgba(47, 129, 247, 0.12),
      0 4px 24px rgba(0, 0, 0, 0.3);
  }
  .hero-search-inner {
    display: flex;
    align-items: center;
    padding: 0 16px;
    height: 56px;
    gap: 12px;
  }
  .hero-icon-wrap {
    display: flex;
    align-items: center;
    flex-shrink: 0;
  }
  .hero-input {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    font-size: 16px;
    color: var(--color-heading);
    font-family: var(--font-sans);
  }
  .hero-input::placeholder {
    color: var(--color-subtle);
  }

  .hero-results {
    border-top: 1px solid var(--color-border);
  }

  .hero-result {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 12px 16px;
    border: none;
    background: transparent;
    cursor: pointer;
    border-bottom: 1px solid var(--color-border);
    transition: background 0.1s;
    font-family: var(--font-sans);
  }
  .hero-result:last-child {
    border-bottom: none;
  }
  .hero-result:hover {
    background: var(--color-hover);
  }

  .hr-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .hr-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .hr-name {
    font-size: 13px;
    color: var(--color-heading);
    font-weight: 500;
    text-align: left;
  }
  .hr-meta {
    font-size: 10px;
    color: var(--color-muted);
    text-align: left;
    margin-top: 1px;
  }
  .hr-arrow {
    display: flex;
    align-items: center;
    color: var(--color-muted);
    transition:
      transform 0.15s,
      color 0.15s;
  }
  .hero-result:hover .hr-arrow {
    transform: translateX(3px);
    color: var(--color-accent);
  }

  .page-title {
    font-size: 20px;
    font-weight: 800;
    color: var(--color-heading);
    margin: 0 0 2px;
    letter-spacing: -0.5px;
    font-family: var(--font-sans);
  }

  /* Body grid */
  .body-grid {
    display: grid;
    grid-template-columns: 360px 1fr;
    gap: 20px;
    align-items: start;
  }

  @media (max-width: 900px) {
    .body-grid {
      grid-template-columns: 1fr;
    }
  }

  /* Leaderboard */
  .leaderboard {
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: 10px;
    overflow: hidden;
  }
  .lb-row {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 10px 12px;
    border: none;
    background: transparent;
    cursor: pointer;
    border-bottom: 1px solid var(--color-border);
    transition: background 0.1s;
    font-family: var(--font-sans);
  }
  .lb-row:last-child {
    border-bottom: none;
  }
  .lb-row:hover {
    background: var(--color-hover);
  }

  .lb-rank {
    font-size: 10px;
    color: var(--color-subtle);
    min-width: 22px;
    font-family: var(--font-mono);
  }
  .lb-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .lb-info {
    flex: 1;
    min-width: 0;
    text-align: left;
  }
  .lb-name {
    font-size: 12px;
    color: var(--color-heading);
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .lb-meta {
    font-size: 10px;
    color: var(--color-muted);
    margin-top: 1px;
  }
  .lb-amount {
    font-size: 12px;
    font-weight: 700;
    color: var(--color-heading);
    display: flex;
    align-items: center;
    flex-shrink: 0;
  }
</style>
