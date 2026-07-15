<script>
  import {
    selectedYear,
    exploreTab,
    activeState,
    openNode,
  } from "../stores.js";
  import {
    getDashboardOverview,
    getConcentration,
    getEvolution,
    getTopProducts,
    getProductDiversity,
    getPaymentFormTrends,
    getJumps,
    getEmerging,
    getStateFlows,
    emptyTable,
  } from "../api.js";
  import PlotlyChart from "../components/PlotlyChart.svelte";
  import NetworkGraph from "../components/NetworkGraph.svelte";
  import Map3D from "../components/Map3D.svelte";
  import {
    Network,
    Pill,
    Clock,
    X,
    TrendingUp,
    Waves,
    Zap,
    BarChart2,
  } from "lucide-svelte";

  // ── State map abbreviations ───────────────────────────────────
  const STATE_ABB = {
    Alabama: "AL",
    Alaska: "AK",
    Arizona: "AZ",
    Arkansas: "AR",
    California: "CA",
    Colorado: "CO",
    Connecticut: "CT",
    Delaware: "DE",
    Florida: "FL",
    Georgia: "GA",
    Hawaii: "HI",
    Idaho: "ID",
    Illinois: "IL",
    Indiana: "IN",
    Iowa: "IA",
    Kansas: "KS",
    Kentucky: "KY",
    Louisiana: "LA",
    Maine: "ME",
    Maryland: "MD",
    Massachusetts: "MA",
    Michigan: "MI",
    Minnesota: "MN",
    Mississippi: "MS",
    Missouri: "MO",
    Montana: "MT",
    Nebraska: "NE",
    Nevada: "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    Ohio: "OH",
    Oklahoma: "OK",
    Oregon: "OR",
    Pennsylvania: "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    Tennessee: "TN",
    Texas: "TX",
    Utah: "UT",
    Vermont: "VT",
    Virginia: "VA",
    Washington: "WA",
    "West Virginia": "WV",
    Wisconsin: "WI",
    Wyoming: "WY",
    "District of Columbia": "DC",
  };
  const ABB_STATE = Object.fromEntries(
    Object.entries(STATE_ABB).map(([k, v]) => [v, k]),
  );

  // ── Concentration mode ────────────────────────────────────────
  const CONC_MODES = [
    { id: "gini", label: "Gini", fmt: (v) => v.toFixed(3) },
    { id: "hhi", label: "HHI", fmt: (v) => v.toFixed(0) },
    { id: "cr_5", label: "CR-5", fmt: (v) => (v * 100).toFixed(1) + "%" },
    { id: "total_payment", label: "Total ($)", fmt: (v) => fmtUSD(v) },
    { id: "n_entities", label: "# Entities", fmt: (v) => (+v).toFixed(0) },
    { id: "theil_t", label: "Theil-T", fmt: (v) => v.toFixed(3) },
  ];
  let concMode = $state("gini");

  // ── Data ──────────────────────────────────────────────────────
  let overviewPromise = $derived(getDashboardOverview($selectedYear, 6));
  let concPromise = $derived(getConcentration($selectedYear, "state", 60));
  let stateFlowsPromise = $derived(getStateFlows($selectedYear, 50));
  let evolutionPromise = $derived(getEvolution());

  // Products tab — only fetch when tab is active
  let prodTab = $state("drugs");
  let drugsPromise = $derived($exploreTab === "products" ? getTopProducts($selectedYear, "drug", 60) : emptyTable());
  let devsPromise = $derived($exploreTab === "products" ? getTopProducts($selectedYear, "device", 60) : emptyTable());
  let divPromise = $derived($exploreTab === "products" ? getProductDiversity($selectedYear, 0, 100) : emptyTable());

  // Temporal tab — only fetch when tab is active
  let tempTab = $state("evolution");
  const YEARS = [2020, 2021, 2022, 2023, 2024];
  let jumpsPromise = $derived($exploreTab === "temporal" ? getJumps("in_strength", 100) : emptyTable());
  let formsPromise = $derived($exploreTab === "temporal" ? getPaymentFormTrends("global") : emptyTable());
  let emergingPromise = $derived($exploreTab === "temporal" ? getEmerging("in_strength", 30) : emptyTable());

  // ── KPI stats from overview ───────────────────────────────────
  function fmtUSD(n) {
    if (!n) return "$0";
    if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
    if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
    if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
    return `$${(+n).toFixed(0)}`;
  }

  // ── Evolution charts ──────────────────────────────────────────
  function buildEvolutionLine(rows) {
    return [
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Total Payments ($)",
        x: rows.map((r) => r.year),
        y: rows.map((r) => r.total_payment_usd ?? r.total_amount ?? 0),
        yaxis: "y",
        line: { color: "#2F81F7", width: 2 },
        marker: { size: 6, color: "#2F81F7" },
        fill: "tozeroy",
        fillcolor: "rgba(47,129,247,0.07)",
        hovertemplate: "<b>%{x}</b><br>$%{y:,.0f}<extra></extra>",
      },
      {
        type: "bar",
        name: "Payment Records",
        yaxis: "y2",
        x: rows.map((r) => r.year),
        y: rows.map((r) => r.n_edges ?? r.edge_count ?? 0),
        marker: { color: "#484F58", opacity: 0.55 },
        hovertemplate: "<b>%{x}</b><br>%{y:,} records<extra></extra>",
      },
    ];
  }

  const evoLayout = {
    margin: { t: 10, r: 50, b: 40, l: 80 },
    xaxis: {
      dtick: 1,
      tickfont: { size: 10, color: "#7D8590" },
      gridcolor: "#30363D",
    },
    yaxis: {
      title: { text: "Total Payments", font: { color: "#7D8590", size: 10 } },
      tickprefix: "$",
      tickfont: { size: 10, color: "#7D8590" },
      gridcolor: "#30363D",
    },
    yaxis2: {
      title: { text: "Edge Count", font: { color: "#7D8590", size: 10 } },
      overlaying: "y",
      side: "right",
      tickfont: { size: 10, color: "#7D8590" },
      gridcolor: "transparent",
    },
    legend: { font: { size: 10 }, x: 0.01, y: 0.99 },
    barmode: "overlay",
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
  };

  // ── Payment forms stacked area ────────────────────────────────
  function buildFormsArea(rows) {
    const byForm = {};
    rows.forEach((r) => {
      if (!byForm[r.form]) byForm[r.form] = {};
      byForm[r.form][r.year] =
        (byForm[r.form][r.year] ?? 0) + (r.total_amount ?? 0);
    });
    const allYears = [...new Set(rows.map((r) => r.year))].sort();
    const palette = [
      "#2F81F7",
      "#F0883E",
      "#3FB950",
      "#F85149",
      "#8957E5",
      "#58A6FF",
      "#D29922",
    ];
    return Object.entries(byForm).map(([form, byYear], i) => ({
      type: "scatter",
      mode: "lines",
      name: form,
      x: allYears,
      y: allYears.map((y) => byYear[y] ?? 0),
      stackgroup: "one",
      fillcolor: palette[i % palette.length],
      line: { color: palette[i % palette.length], width: 0.5 },
      hovertemplate: `<b>${form}</b><br>%{x}: $%{y:,.0f}<extra></extra>`,
    }));
  }

  const formsAreaLayout = {
    margin: { t: 10, r: 80, b: 40, l: 80 },
    xaxis: { dtick: 1, tickfont: { size: 10, color: "#7D8590" } },
    yaxis: {
      title: { text: "USD", font: { color: "#7D8590", size: 10 } },
      tickprefix: "$",
      tickfont: { size: 10, color: "#7D8590" },
    },
    legend: { font: { size: 9 }, orientation: "h", y: -0.18 },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
  };

  // ── Emerging entities chart ───────────────────────────────────
  function buildEmerging(rows) {
    const top = rows.slice(0, 20).reverse();
    return [
      {
        type: "bar",
        orientation: "h",
        x: top.map((r) => r.growth_factor ?? r.growth_rate ?? 0),
        y: top.map((r) => (r.name ?? r.id ?? "").slice(0, 28)),
        customdata: top.map((r) => ({
          id: r.id,
          value_last: r.value_last,
          n_years: r.n_years,
        })),
        marker: {
          color: top.map((r) => r.growth_factor ?? 0),
          colorscale: [
            [0, "#1C3B6E"],
            [0.4, "#2F81F7"],
            [0.7, "#3FB950"],
            [1, "#D29922"],
          ],
          showscale: false,
          opacity: 0.88,
        },
        hovertemplate:
          "<b>%{y}</b><br>" +
          "Growth factor: %{x:.1f}×<br>" +
          "Payment received: $%{customdata.value_last:,.0f}<br>" +
          "Active years: %{customdata.n_years}<extra></extra>",
      },
    ];
  }

  const emergingLayout = {
    margin: { t: 8, r: 20, b: 40, l: 200 },
    xaxis: {
      title: {
        text: "Growth Factor (×)",
        font: { color: "#7D8590", size: 10 },
      },
      tickfont: { size: 10, color: "#7D8590" },
      gridcolor: "#30363D",
    },
    yaxis: { tickfont: { size: 9, color: "#C9D1D9" } },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
  };

  // ── Jump dot-plot ─────────────────────────────────────────────
  function buildJumps(rows) {
    const top = rows.slice(0, 100);
    return [
      {
        type: "scatter",
        mode: "markers",
        x: top.map((r) => r.year_to ?? r.year ?? 0),
        y: top.map((r) => r.jump_factor ?? 0),
        text: top.map((r) => r.name ?? r.id ?? ""),
        customdata: top.map((r) => ({
          from: r.year_from ?? "?",
          to: r.year_to ?? "?",
          v_from: r.value_from ?? 0,
          v_to: r.value_to ?? 0,
          state: r.state ?? "-",
          specialty: r.specialty?.split("|").pop() ?? "-",
        })),
        marker: {
          color: top.map((r) => r.jump_factor ?? 0),
          colorscale: [
            [0, "#D29922"],
            [0.5, "#F0883E"],
            [1, "#F85149"],
          ],
          showscale: true,
          colorbar: {
            title: { text: "Factor", font: { color: "#7D8590", size: 9 } },
            thickness: 10,
            tickfont: { color: "#7D8590", size: 9 },
          },
          size: top.map((r) =>
            Math.max(5, Math.min(16, Math.log1p(r.jump_factor ?? 0) * 3.5)),
          ),
          opacity: 0.85,
          line: { color: "rgba(0,0,0,0.2)", width: 0.5 },
        },
        hovertemplate:
          "<b>%{text}</b><br>" +
          "%{customdata.specialty} · %{customdata.state}<br>" +
          "Jump: %{customdata.from} → %{customdata.to} (%{y:.0f}×)<br>" +
          "$%{customdata.v_from:,.0f} → $%{customdata.v_to:,.0f}<extra></extra>",
      },
    ];
  }

  const jumpLayout = {
    margin: { t: 8, r: 90, b: 40, l: 60 },
    xaxis: {
      title: { text: "Year", font: { color: "#7D8590", size: 10 } },
      dtick: 1,
      tickfont: { size: 10, color: "#7D8590" },
      gridcolor: "#30363D",
    },
    yaxis: {
      title: { text: "Jump Factor (×)", font: { color: "#7D8590", size: 10 } },
      type: "log",
      tickfont: { size: 10, color: "#7D8590" },
      gridcolor: "#30363D",
    },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
  };

  // ── Products charts ───────────────────────────────────────────
  function buildProdTreemap(rows) {
    const top = rows.slice(0, 50);
    return [
      {
        type: "treemap",
        ids: top.map((r) => r.product_name),
        labels: top.map((r) => r.product_name),
        parents: top.map(() => ""),
        values: top.map((r) => r.n_records ?? 0),
        customdata: top,
        textfont: { size: 10, color: "#f1f5f9" },
        hovertemplate:
          "<b>%{label}</b><br>Records: %{value:,}<br>Years: %{customdata.n_years}<extra></extra>",
        marker: {
          colors: top.map((r) => r.n_years ?? 0),
          colorscale: [
            [0, "#1C2128"],
            [0.3, "#1C3B6E"],
            [0.7, "#2F81F7"],
            [1, "#3FB950"],
          ],
          line: { color: "#0D1117", width: 1 },
        },
        tiling: { pad: 3 },
      },
    ];
  }

  const treemapLayout = {
    margin: { t: 4, r: 4, b: 4, l: 4 },
    paper_bgcolor: "transparent",
  };

  function buildDiversityScatter(rows) {
    return [
      {
        type: "scatter",
        mode: "markers",
        x: rows.map((r) => r.distinct_products),
        y: rows.map((r) => r.total_payment),
        customdata: rows.map((r) => r.dst_id),
        text: rows.map((r) => r.dst_id),
        marker: {
          color: rows.map((r) => r.product_diversity_score ?? 0),
          colorscale: [
            [0, "#2F81F7"],
            [0.5, "#D29922"],
            [1, "#F85149"],
          ],
          size: 5,
          opacity: 0.7,
          showscale: true,
          colorbar: {
            title: { text: "Score", font: { color: "#7D8590", size: 9 } },
            thickness: 10,
            tickfont: { size: 9, color: "#7D8590" },
          },
        },
        hovertemplate:
          "<b>%{text}</b><br>Products: %{x}<br>$%{y:,.0f}<extra></extra>",
      },
    ];
  }

  const divScatterLayout = {
    margin: { t: 8, r: 80, b: 48, l: 80 },
    xaxis: {
      title: {
        text: "Distinct products",
        font: { color: "#7D8590", size: 10 },
      },
      tickfont: { size: 10, color: "#7D8590" },
    },
    yaxis: {
      title: {
        text: "Total payments (log)",
        font: { color: "#7D8590", size: 10 },
      },
      type: "log",
      tickprefix: "$",
      tickfont: { size: 10, color: "#7D8590" },
    },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
  };
</script>

<!-- ── Explore header ────────────────────────────────────────────── -->
<div
  style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:8px"
>
  <div>
    <h1 class="page-title">Explore Payment Network</h1>
    <p
      style="font-size:12px;color:var(--color-muted);margin:3px 0 0;font-family:var(--font-sans)"
    >
      {$selectedYear} · Interactive map, network graph, products and trends
    </p>
  </div>
  {#if $activeState}
    <div style="display:flex;align-items:center;gap:6px">
      <span style="font-size:11px;color:var(--color-warning);font-weight:600"
        >Filtering: {ABB_STATE[$activeState] ?? $activeState}</span
      >
      <button
        class="btn btn-ghost"
        style="padding:3px 10px;font-size:11px;display:inline-flex;align-items:center;gap:4px"
        onclick={() => activeState.set(null)}
      >
        <X size={11} /> Clear
      </button>
    </div>
  {/if}
</div>

<!-- ── Tab bar ────────────────────────────────────────────────────── -->
<div class="tab-row">
  <button
    class="tab-btn"
    class:active={$exploreTab === "network"}
    onclick={() => exploreTab.set("network")}
  >
    <Network size={13} /> Network
  </button>
  <button
    class="tab-btn"
    class:active={$exploreTab === "products"}
    onclick={() => exploreTab.set("products")}
  >
    <Pill size={13} /> Products
  </button>
  <button
    class="tab-btn"
    class:active={$exploreTab === "temporal"}
    onclick={() => exploreTab.set("temporal")}
  >
    <Clock size={13} /> Temporal
  </button>
</div>

<!-- ════════════════════════════════════════════════════════════════ -->
<!-- NETWORK TAB                                                     -->
<!-- ════════════════════════════════════════════════════════════════ -->
{#if $exploreTab === "network"}
  <div class="split-view" style="height:calc(100vh - 240px);min-height:420px">
    <!-- Left: 3D USA Map -->
    <div
      class="card-flat"
      style="overflow:hidden;display:flex;flex-direction:column;"
    >
      <div
        style="padding:10px 14px 6px;border-bottom:1px solid var(--color-border)"
      >
        <div
          style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px"
        >
          <div>
            <div class="section-label" style="margin:0">
              Payment Concentration · USA 3D
            </div>
            <div style="font-size:10px;color:var(--color-muted)">
              Click a state bubble to filter · arcs = cross-state flows
            </div>
          </div>
        </div>
        <!-- Concentration mode buttons -->
        <div style="display:flex;gap:4px;flex-wrap:wrap">
          {#each CONC_MODES as m}
            <button
              class="mode-pill"
              class:active={concMode === m.id}
              onclick={() => (concMode = m.id)}>{m.label}</button
            >
          {/each}
        </div>
      </div>

      {#await concPromise}
        <div class="loading-center" style="flex:1">
          <div class="spinner"></div>
        </div>
      {:then concData}
        {@const rows = concData.rows ?? []}
        {@const top3 = [...rows]
          .sort((a, b) => (b[concMode] ?? 0) - (a[concMode] ?? 0))
          .slice(0, 3)}
        {#if top3.length}
          <div
            style="padding:5px 14px 0;font-size:11px;color:var(--color-accent)"
          >
            Top {CONC_MODES.find((m) => m.id === concMode)?.label}: {top3
              .map((r) => STATE_ABB[r.state] ?? r.state)
              .join(", ")}
          </div>
        {/if}
        <div
          style="flex:1;min-height:0;display:flex;flex-direction:column;position:relative"
        >
          {#await stateFlowsPromise then flowData}
            <Map3D
              concRows={rows}
              flowRows={flowData.rows ?? []}
              {concMode}
              activeState={$activeState}
              onStateClick={(abb) =>
                activeState.set($activeState === abb ? null : abb)}
            />
          {:catch}
            <Map3D
              concRows={rows}
              flowRows={[]}
              {concMode}
              activeState={$activeState}
              onStateClick={(abb) =>
                activeState.set($activeState === abb ? null : abb)}
            />
          {/await}
        </div>
      {:catch}
        <div class="loading-center" style="flex:1">
          <span style="color:var(--color-muted)">Map unavailable</span>
        </div>
      {/await}
    </div>

    <!-- Right: Network Graph -->
    <div
      class="card-flat"
      style="overflow:hidden;display:flex;flex-direction:column;position:relative;"
    >
      <NetworkGraph stateFilter={$activeState} />
    </div>
  </div>

  <!-- KPI strip below -->
  {#await overviewPromise then ov}
    {@const s = ov?.summary ?? {}}
    <div class="stat-grid" style="margin-top:14px">
      {#each [["Total Payments", fmtUSD(s.total_payment_usd), "all payment types"], ["Payment Records", (s.edges ?? 0).toLocaleString(), "manufacturer→physician edges"], ["Physicians", (s.node_types?.Physician ?? 0).toLocaleString(), "receiving entities"], ["Manufacturers", (s.node_types?.Manufacturer ?? 0).toLocaleString(), "paying companies"], ["Avg per Record", fmtUSD(s.avg_edge_weight_usd), "mean payment size"], ["Teaching Hospitals", (s.node_types?.TeachingHospital ?? 0).toLocaleString(), "academic centers"]] as [label, val, meta]}
        <div class="stat-card">
          <div class="stat-label">{label}</div>
          <div class="stat-value">{val ?? "-"}</div>
          <div class="stat-meta">{meta}</div>
        </div>
      {/each}
    </div>
  {/await}

  <!-- ════════════════════════════════════════════════════════════════ -->
  <!-- PRODUCTS TAB                                                    -->
  <!-- ════════════════════════════════════════════════════════════════ -->
{:else if $exploreTab === "products"}
  <div
    style="display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap;align-items:center"
  >
    {#each [["drugs", "drug", "Drugs"], ["devices", "device", "Devices"], ["diversity", "", "Diversity"]] as [id, , lbl]}
      <button
        class="tab-btn"
        class:active={prodTab === id}
        onclick={() => (prodTab = id)}
        style="font-size:12px">{lbl}</button
      >
    {/each}
  </div>

  {#if prodTab === "diversity"}
    {#await divPromise}
      <div class="loading-center"><div class="spinner"></div></div>
    {:then data}
      <div class="card" style="margin-bottom:14px">
        <div class="insight-block" style="margin-bottom:10px">
          Physicians with high <strong>product diversity</strong> receive payments
          for many different drugs/devices - a potential indicator of broad industry
          relationships. Points in the upper-right corner represent the highest-value,
          most-diverse practitioners.
        </div>
        <div class="section-label">
          Product Diversity vs Total Payments · Click point to open dossier
        </div>
        <PlotlyChart
          traces={buildDiversityScatter(data.rows ?? [])}
          layout={divScatterLayout}
          height={420}
          onClick={(pt) => {
            if (pt.customdata) openNode(pt.customdata);
          }}
        />
      </div>
    {:catch e}
      <div class="error-msg">{e.message}</div>
    {/await}
  {:else}
    {@const promise = prodTab === "drugs" ? drugsPromise : devsPromise}
    {#await promise}
      <div class="loading-center"><div class="spinner"></div></div>
    {:then data}
      <div class="split-view" style="height:auto;grid-template-columns:1fr 1fr">
        <div class="card">
          <div class="section-label" style="margin-bottom:6px">
            Top {prodTab} - size = records, colour = years active
          </div>
          <PlotlyChart
            traces={buildProdTreemap(data.rows ?? [])}
            layout={treemapLayout}
            height={360}
          />
        </div>
        <div class="card">
          <div class="section-label" style="margin-bottom:6px">
            Top 20 by payment record count
          </div>
          <PlotlyChart
            traces={[
              {
                type: "bar",
                orientation: "h",
                x: (data.rows ?? [])
                  .slice(0, 20)
                  .reverse()
                  .map((r) => r.n_records ?? 0),
                y: (data.rows ?? [])
                  .slice(0, 20)
                  .reverse()
                  .map((r) => (r.product_name ?? "").slice(0, 30)),
                marker: { color: "#2F81F7", opacity: 0.85 },
                hovertemplate: "<b>%{y}</b><br>%{x:,} records<extra></extra>",
              },
            ]}
            layout={{
              margin: { t: 8, r: 20, b: 40, l: 200 },
              xaxis: { tickfont: { size: 10, color: "#7D8590" } },
              yaxis: { tickfont: { size: 9 } },
              paper_bgcolor: "transparent",
              plot_bgcolor: "transparent",
            }}
            height={360}
          />
        </div>
      </div>
    {:catch e}
      <div class="error-msg">{e.message}</div>
    {/await}
  {/if}

  <!-- ════════════════════════════════════════════════════════════════ -->
  <!-- TEMPORAL TAB                                                    -->
  <!-- ════════════════════════════════════════════════════════════════ -->
{:else if $exploreTab === "temporal"}
  <div style="display:flex;gap:2px;margin-bottom:14px;flex-wrap:wrap">
    <button
      class="tab-btn"
      class:active={tempTab === "evolution"}
      onclick={() => (tempTab = "evolution")}
    >
      <TrendingUp size={12} /> Evolution
    </button>
    <button
      class="tab-btn"
      class:active={tempTab === "forms"}
      onclick={() => (tempTab = "forms")}
    >
      <Waves size={12} /> Payment Forms
    </button>
    <button
      class="tab-btn"
      class:active={tempTab === "emerging"}
      onclick={() => (tempTab = "emerging")}
    >
      <Zap size={12} /> Emerging
    </button>
    <button
      class="tab-btn"
      class:active={tempTab === "jumps"}
      onclick={() => (tempTab = "jumps")}
    >
      <BarChart2 size={12} /> Sudden Jumps
    </button>
  </div>

  {#if tempTab === "evolution"}
    {#await evolutionPromise}
      <div class="loading-center"><div class="spinner"></div></div>
    {:then data}
      <div class="card" style="margin-bottom:14px">
        <div class="insight-block" style="margin-bottom:10px">
          The <strong>bars show transaction volume</strong> (right axis) while
          the <strong>line tracks total payment dollars</strong> (left axis). Divergence
          between the two signals price changes in high-value payments - a pattern
          seen in 2022–2023 post-COVID.
        </div>
        <div class="section-label" style="margin-bottom:8px">
          Network Evolution 2020–2024
        </div>
        <PlotlyChart
          traces={buildEvolutionLine(data.rows ?? [])}
          layout={evoLayout}
          height={280}
        />
      </div>
    {:catch e}
      <div class="error-msg">{e.message}</div>
    {/await}
  {:else if tempTab === "forms"}
    {#await formsPromise}
      <div class="loading-center"><div class="spinner"></div></div>
    {:then data}
      <div class="card">
        <div class="insight-block" style="margin-bottom:10px">
          <strong>Stacked areas</strong> show how payment forms (cash, food, travel,
          consulting fees, etc.) have shifted over time. A growing cash share warrants
          attention under CMS disclosure rules.
        </div>
        <div class="section-label" style="margin-bottom:8px">
          Payment Form Trends 2020–2024
        </div>
        <PlotlyChart
          traces={buildFormsArea(data.rows ?? [])}
          layout={formsAreaLayout}
          height={320}
        />
      </div>
    {:catch e}
      <div class="error-msg">{e.message}</div>
    {/await}
  {:else if tempTab === "emerging"}
    {#await emergingPromise}
      <div class="loading-center"><div class="spinner"></div></div>
    {:then data}
      <div class="card">
        <div class="insight-block" style="margin-bottom:10px">
          <strong>Emerging entities</strong> are nodes whose payment receipts grew
          the most year-over-year. Rapid growth can indicate new manufacturer partnerships
          or expanding prescribing relationships.
        </div>
        <div class="section-label" style="margin-bottom:8px">
          Fastest-Growing Entities (YoY payment growth)
        </div>
        <PlotlyChart
          traces={buildEmerging(data.rows ?? [])}
          layout={emergingLayout}
          height={400}
          onClick={(pt) => {
            if (pt.y) openNode(pt.y);
          }}
        />
      </div>
    {:catch e}
      <div class="error-msg">{e.message}</div>
    {/await}
  {:else if tempTab === "jumps"}
    {#await jumpsPromise}
      <div class="loading-center"><div class="spinner"></div></div>
    {:then data}
      <div class="card">
        <div class="insight-block" style="margin-bottom:10px">
          <strong>Sudden jumps</strong> are entities whose payments spiked by a large
          multiple in a single year. Red dots indicate jumps >5×. These can signal
          new drug launches, exclusive agreements, or data anomalies worth investigating.
        </div>
        <div class="section-label" style="margin-bottom:8px">
          Sudden Payment Jumps · Hover for entity name
        </div>
        <PlotlyChart
          traces={buildJumps(data.rows ?? [])}
          layout={jumpLayout}
          height={320}
          onClick={(pt) => {
            if (pt.text) openNode(pt.text);
          }}
        />
      </div>
    {:catch e}
      <div class="error-msg">{e.message}</div>
    {/await}
  {/if}
{/if}

<style>
  .page-title {
    font-size: 20px;
    font-weight: 800;
    color: var(--color-heading);
    margin: 0;
    letter-spacing: -0.5px;
    font-family: var(--font-display);
  }

  .mode-pill {
    padding: 2px 9px;
    font-size: 10px;
    font-weight: 600;
    border-radius: 20px;
    border: 1px solid var(--color-border);
    background: transparent;
    color: var(--color-muted);
    cursor: pointer;
    transition:
      background 0.15s,
      color 0.15s,
      border-color 0.15s;
    font-family: var(--font-sans);
    letter-spacing: 0.3px;
  }
  .mode-pill:hover {
    border-color: var(--color-accent);
    color: var(--color-accent);
  }
  .mode-pill.active {
    background: var(--color-accent-dim);
    border-color: rgba(47, 129, 247, 0.4);
    color: var(--color-accent);
  }
</style>
