<script>
  import { selectedYear } from "../stores.js";
  import { getCentrality } from "../api.js";
  import LoadingSpinner from "../components/LoadingSpinner.svelte";
  import DataTable from "../components/DataTable.svelte";
  import PlotlyChart from "../components/PlotlyChart.svelte";

  const METRICS = [
    { id: "pagerank", label: "PageRank", tip: "Google's PageRank: measures influence by who pays you and how influential those payers are" },
    { id: "in_strength", label: "Total Received ($)", tip: "Sum of all payment dollars received from pharmaceutical companies" },
    { id: "in_degree", label: "Company Count", tip: "Number of distinct companies that paid this physician" },
    { id: "betweenness", label: "Betweenness", tip: "Fraction of shortest paths through this node — high = bridge between communities" },
    { id: "authority_score", label: "Authority Score", tip: "HITS authority score: high if paid by highly connected hub companies" },
    { id: "payment_diversity", label: "Payment Diversity", tip: "Number of distinct drug / device categories in received payments" },
  ];

  const NODE_COLORS = {
    Physician: "#4e79a7",
    Manufacturer: "#f28e2b",
    TeachingHospital: "#e15759",
  };

  let metric = $state("pagerank");
  let topK = $state(200);
  let view = $state("scatter"); // 'scatter' | 'table'

  const FIELDS =
    "id,name,node_type,specialty,state,pagerank,in_strength,in_degree,betweenness,authority_score,payment_diversity,cash_ratio";

  let promise = $derived(getCentrality($selectedYear, metric, topK, FIELDS));

  let TABLE_COLS = $derived([
    "name",
    "node_type",
    "specialty",
    "state",
    metric,
    "in_strength",
    "in_degree",
  ]);

  // ── Build scatter traces (PageRank × In-Strength, coloured by node type) ──
  function buildScatter(rows) {
    const byType = {};
    for (const r of rows) {
      const t = r.node_type ?? "Unknown";
      if (!byType[t]) byType[t] = [];
      byType[t].push(r);
    }
    return Object.entries(byType).map(([type, pts]) => ({
      type: "scatter",
      mode: "markers",
      name: type,
      x: pts.map((r) => r.pagerank),
      y: pts.map((r) => r.in_strength),
      customdata: pts.map((r) => r.id),
      text: pts.map((r) => r.name),
      hovertemplate:
        "<b>%{text}</b><br>" +
        "PageRank: %{x:.5f}<br>" +
        "Received: $%{y:,.0f}<br>" +
        "<extra></extra>",
      marker: {
        color: NODE_COLORS[type] ?? "#888",
        size: pts.map((r) =>
          Math.max(4, Math.min(18, 3 + Math.sqrt(r.betweenness || 0) * 12)),
        ),
        opacity: 0.72,
        line: { color: "rgba(0,0,0,0.3)", width: 0.5 },
      },
    }));
  }

  // ── Build betweenness × authority bubble chart ──
  function buildBubble(rows) {
    const byType = {};
    for (const r of rows) {
      const t = r.node_type ?? "Unknown";
      if (!byType[t]) byType[t] = [];
      byType[t].push(r);
    }
    return Object.entries(byType).map(([type, pts]) => ({
      type: "scatter",
      mode: "markers",
      name: type,
      x: pts.map((r) => r.betweenness),
      y: pts.map((r) => r.authority_score),
      customdata: pts.map((r) => r.id),
      text: pts.map((r) => r.name),
      hovertemplate:
        "<b>%{text}</b><br>" +
        "Betweenness: %{x:.4f}<br>" +
        "Authority: %{y:.5f}<br>" +
        "Received: $%{marker.size:,.0f}<br>" +
        "<extra></extra>",
      marker: {
        color: NODE_COLORS[type] ?? "#888",
        size: pts.map((r) =>
          Math.max(4, Math.min(20, 2 + Math.log1p(r.in_strength || 0) * 1.2)),
        ),
        opacity: 0.7,
        sizemode: "area",
        line: { color: "rgba(0,0,0,0.3)", width: 0.5 },
      },
    }));
  }

  const scatterLayout = {
    margin: { t: 16, r: 16, b: 56, l: 80 },
    xaxis: {
      title: { text: "PageRank", font: { color: "#6b7280", size: 11 } },
      type: "log",
    },
    yaxis: {
      title: {
        text: "Total Received (USD)",
        font: { color: "#6b7280", size: 11 },
      },
      type: "log",
      tickprefix: "$",
    },
  };

  const bubbleLayout = {
    margin: { t: 16, r: 16, b: 56, l: 80 },
    xaxis: {
      title: {
        text: "Betweenness Centrality",
        font: { color: "#6b7280", size: 11 },
      },
      type: "log",
    },
    yaxis: {
      title: { text: "Authority Score", font: { color: "#6b7280", size: 11 } },
      type: "log",
    },
  };
</script>

<div class="page-header">
  <h1 class="page-title">Centrality Rankings</h1>
  <div class="controls">
    <div class="view-toggle">
      <button
        class="btn"
        class:btn-active={view === "scatter"}
        class:btn-ghost={view !== "scatter"}
        onclick={() => (view = "scatter")}
        data-tip="PageRank vs Total Received scatter — node size proportional to betweenness"
        >Scatter</button
      >
      <button
        class="btn"
        class:btn-active={view === "table"}
        class:btn-ghost={view !== "table"}
        onclick={() => (view = "table")}
        data-tip="Sortable ranked table of top nodes by selected metric"
        >Table</button
      >
    </div>
    <div class="sep"></div>
    {#each METRICS as m}
      <button
        class="btn"
        class:btn-active={metric === m.id}
        class:btn-ghost={metric !== m.id}
        onclick={() => (metric = m.id)}
        data-tip={m.tip}>{m.label}</button
      >
    {/each}
  </div>
</div>

<div class="topk-row">
  <label
    class="range-label"
    data-tip="Limit the chart and table to the top N nodes by the selected metric"
    >Top <strong>{topK}</strong> nodes
    <input type="range" min="50" max="500" step="25" bind:value={topK} />
  </label>
</div>

{#await promise}
  <LoadingSpinner />
{:then data}
  {#if view === "scatter"}
    <div class="charts-row">
      <!-- PageRank vs Total Received -->
      <div class="card chart-card">
        <div class="chart-title">
          PageRank vs Total Received - node size ∝ betweenness
        </div>
        <PlotlyChart
          traces={buildScatter(data.rows)}
          layout={scatterLayout}
          height={380}
          onClick={(pt) => {
            if (pt.customdata) window.location.hash = `node/${pt.customdata}`;
          }}
        />
      </div>
      <!-- Betweenness vs Authority -->
      <div class="card chart-card">
        <div class="chart-title">
          Betweenness vs Authority Score - size ∝ payments
        </div>
        <PlotlyChart
          traces={buildBubble(data.rows)}
          layout={bubbleLayout}
          height={380}
          onClick={(pt) => {
            if (pt.customdata) window.location.hash = `node/${pt.customdata}`;
          }}
        />
      </div>
    </div>
    <p class="hint">Click any point to open Node Detail.</p>
  {:else}
    <div class="card">
      <DataTable
        columns={TABLE_COLS}
        rows={data.rows}
        pageSize={25}
        onRowClick={(row) => {
          if (row.id) window.location.hash = `node/${row.id}`;
        }}
      />
    </div>
  {/if}
{:catch err}
  <p class="error-message">{err.message}</p>
{/await}

<style>
  .controls {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    align-items: center;
  }
  .view-toggle {
    display: flex;
    gap: 4px;
  }
  .sep {
    width: 1px;
    height: 22px;
    background: var(--color-border);
    margin: 0 4px;
  }

  .topk-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    font-size: 13px;
    color: var(--color-muted);
  }
  .topk-row input {
    width: 140px;
  }

  .charts-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 16px;
  }

  .chart-card {
    min-width: 0;
  }

  .chart-title {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--color-muted);
    margin-bottom: 4px;
  }

  .hint {
    font-size: 11px;
    color: var(--color-muted);
    margin-bottom: 16px;
    font-style: italic;
  }

  @media (max-width: 860px) {
    .charts-row {
      grid-template-columns: 1fr;
    }
  }
</style>
