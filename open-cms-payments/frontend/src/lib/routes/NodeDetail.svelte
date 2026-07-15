<script>
  import { selectedYear } from "../stores.js";
  import { getNode, getNodeCentrality, getTrajectory } from "../api.js";
  import LoadingSpinner from "../components/LoadingSpinner.svelte";
  import DataTable from "../components/DataTable.svelte";
  import PlotlyChart from "../components/PlotlyChart.svelte";
  import * as d3 from "d3";

  let { id } = $props();

  let resolvedData = $state(null);
  let nodePromise = $derived(
    getNode($selectedYear, id).then((d) => {
      resolvedData = d;
      return d;
    }),
  );
  let centralityPromise = $derived(getNodeCentrality($selectedYear, id));
  let trajectoryPromise = $derived(getTrajectory("in_strength", id));

  let egoEl = $state(null);

  $effect(() => {
    if (resolvedData && egoEl) drawEgo(resolvedData);
  });

  const IN_COLS = [
    "src_id",
    "total_amount",
    "payment_count",
    "natures",
    "payment_forms",
    "products",
  ];
  const OUT_COLS = [
    "dst_id",
    "dst_type",
    "total_amount",
    "payment_count",
    "natures",
    "payment_forms",
  ];

  // ── Formatters ────────────────────────────────────────────────
  function fmtUSD(n) {
    if (!n) return "$0";
    if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
    if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
    return `$${n.toFixed(0)}`;
  }

  // ── Ego network (D3 force) ─────────────────────────────────────
  function drawEgo(nodeData) {
    if (!egoEl) return;
    const center = nodeData.node;
    const incoming = nodeData.incoming_edges?.rows ?? [];
    const outgoing = nodeData.outgoing_edges?.rows ?? [];

    const nodes = [
      {
        id: center.id,
        name: center.name,
        type: center.node_type,
        isCenter: true,
      },
      ...incoming
        .slice(0, 30)
        .map((e) => ({ id: e.src_id, name: e.src_id, type: "Manufacturer" })),
      ...outgoing
        .slice(0, 30)
        .map((e) => ({
          id: e.dst_id,
          name: e.dst_id,
          type: e.dst_type ?? "Physician",
        })),
    ];
    const seen = new Set();
    const uniqueNodes = nodes.filter((n) => {
      if (seen.has(n.id)) return false;
      seen.add(n.id);
      return true;
    });

    const links = [
      ...incoming
        .slice(0, 30)
        .map((e) => ({
          source: e.src_id,
          target: center.id,
          weight: e.total_amount ?? 1,
        })),
      ...outgoing
        .slice(0, 30)
        .map((e) => ({
          source: center.id,
          target: e.dst_id,
          weight: e.total_amount ?? 1,
        })),
    ];

    const W = egoEl.clientWidth || 460,
      H = 300;
    d3.select(egoEl).selectAll("*").remove();

    const svg = d3.select(egoEl).attr("viewBox", [0, 0, W, H]);
    const g = svg.append("g");

    const colorMap = {
      Physician: "#4e79a7",
      Manufacturer: "#f28e2b",
      TeachingHospital: "#e15759",
    };
    const nodeColor = (d) =>
      d.isCenter ? "var(--color-accent)" : (colorMap[d.type] ?? "#888");
    const nodeR = (d) => (d.isCenter ? 10 : 5);

    const sim = d3
      .forceSimulation(uniqueNodes)
      .force(
        "link",
        d3
          .forceLink(links)
          .id((d) => d.id)
          .distance(60),
      )
      .force("charge", d3.forceManyBody().strength(-80))
      .force("center", d3.forceCenter(W / 2, H / 2))
      .force("collision", d3.forceCollide(10));

    const link = g
      .append("g")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", "rgba(255,255,255,.1)")
      .attr("stroke-width", (d) => Math.max(0.5, Math.log1p(d.weight) / 10));

    const node = g
      .append("g")
      .selectAll("circle")
      .data(uniqueNodes)
      .join("circle")
      .attr("r", nodeR)
      .attr("fill", nodeColor)
      .attr("fill-opacity", 0.9);

    node.append("title").text((d) => d.name ?? d.id);
    node.on("click", (_, d) => {
      if (!d.isCenter && d.id !== id) window.location.hash = `node/${d.id}`;
    });

    sim.on("tick", () => {
      link
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);
      node.attr("cx", (d) => d.x).attr("cy", (d) => d.y);
    });

    svg.call(
      d3
        .zoom()
        .scaleExtent([0.3, 5])
        .on("zoom", (e) => g.attr("transform", e.transform)),
    );
  }

  // ── Radar chart (Plotly scatterpolar) ─────────────────────────
  function buildRadar(c) {
    // Normalise each metric to [0,1] relative to reasonable max values
    const dims = [
      { key: "pagerank", label: "PageRank", max: 0.001 },
      { key: "in_strength", label: "Payments", max: 1e7 },
      { key: "betweenness", label: "Betweenness", max: 0.05 },
      { key: "authority_score", label: "Authority", max: 0.001 },
      { key: "payment_diversity", label: "Diversity", max: 20 },
    ];
    const vals = dims.map((d) => Math.min(1, (c[d.key] ?? 0) / d.max));
    const labels = dims.map((d) => d.label);
    // Close the polygon
    return [
      {
        type: "scatterpolar",
        r: [...vals, vals[0]],
        theta: [...labels, labels[0]],
        fill: "toself",
        fillcolor: "rgba(124,111,205,0.2)",
        line: { color: "#7c6fcd", width: 2 },
        name: "Centrality profile",
      },
    ];
  }

  const radarLayout = {
    polar: {
      bgcolor: "#1a1d27",
      angularaxis: {
        tickfont: { color: "#c8d0e0", size: 10 },
        linecolor: "#2a2d3e",
        gridcolor: "#2a2d3e",
      },
      radialaxis: {
        visible: true,
        range: [0, 1],
        tickfont: { color: "#6b7280", size: 9 },
        gridcolor: "#2a2d3e",
        linecolor: "#2a2d3e",
      },
    },
    showlegend: false,
    margin: { t: 20, r: 30, b: 20, l: 30 },
  };

  // ── Payment breakdown donut ────────────────────────────────────
  function buildDonut(c) {
    const cash = Math.max(0, c.cash_ratio ?? 0);
    const disputed = Math.max(0, c.disputed_ratio ?? 0);
    const third = Math.max(0, c.third_party_ratio ?? 0);
    const other = Math.max(0, 1 - cash - disputed - third);
    return [
      {
        type: "pie",
        hole: 0.55,
        labels: ["Cash", "Disputed", "Third-party", "Other"],
        values: [cash, disputed, third, other],
        marker: { colors: ["#e15759", "#f28e2b", "#4e79a7", "#59a14f"] },
        textinfo: "percent",
        textfont: { size: 10, color: "#c8d0e0" },
        hovertemplate: "<b>%{label}</b><br>%{percent}<extra></extra>",
      },
    ];
  }

  const donutLayout = {
    margin: { t: 10, r: 10, b: 10, l: 10 },
    showlegend: true,
    legend: { font: { size: 10 }, orientation: "h", y: -0.15 },
  };

  // ── Trajectory line ────────────────────────────────────────────
  function buildTraj(rows) {
    return [
      {
        type: "scatter",
        mode: "lines+markers",
        x: rows.map((r) => r.year),
        y: rows.map((r) => r.in_strength),
        line: { color: "#7c6fcd", width: 2.5 },
        marker: { size: 7, color: "#7c6fcd" },
        hovertemplate: "%{x}: $%{y:,.0f}<extra></extra>",
      },
    ];
  }

  const trajLayout = {
    margin: { t: 10, r: 16, b: 40, l: 80 },
    xaxis: { dtick: 1, tickfont: { size: 10 } },
    yaxis: { tickprefix: "$", tickfont: { size: 10 } },
  };
</script>

<div class="page-header">
  <h1 class="page-title">Node Detail</h1>
  <a href="#dashboard" class="btn btn-ghost">← Back</a>
</div>

{#if !id}
  <p class="error-message">No node ID specified. Navigate from a table row.</p>
{:else}
  {#await nodePromise}
    <LoadingSpinner />
  {:then data}
    {@const n = data.node}

    <!-- ── Top layout: profile | charts | ego ───────────────── -->
    <div class="top-layout">
      <!-- Profile card -->
      <div class="card profile-card">
        <div class="node-type badge badge-{n.node_type?.toLowerCase()}">
          {n.node_type}
        </div>
        <h2 class="node-name">{n.name}</h2>
        {#if n.specialty}
          <div class="node-meta">{n.specialty.split("|").pop()}</div>
        {/if}
        <div class="node-meta">
          {[n.city, n.state].filter(Boolean).join(", ")}
        </div>
        {#if n.credential_type}
          <div class="node-meta credential">{n.credential_type}</div>
        {/if}
        <div class="node-id">ID: {n.id}</div>

        {#await centralityPromise then cm}
          {#if cm?.rows?.[0]}
            {@const c = cm.rows[0]}
            <div class="centrality-section">
              <div class="centrality-title">Centrality ({$selectedYear})</div>
              {#each [["PageRank", c.pagerank?.toFixed(5)], ["Total Received", fmtUSD(c.in_strength)], ["Companies", c.in_degree], ["Betweenness", c.betweenness?.toFixed(4)], ["Authority", c.authority_score?.toFixed(5)]] as [k, v]}
                {#if v != null}
                  <div class="c-row">
                    <span class="c-key">{k}</span>
                    <span class="c-val">{v}</span>
                  </div>
                {/if}
              {/each}
            </div>
          {/if}
        {/await}
      </div>

      <!-- Radar + donut column -->
      {#await centralityPromise then cm}
        {#if cm?.rows?.[0]}
          {@const c = cm.rows[0]}
          <div class="charts-col">
            <div class="card mini-card">
              <div class="mini-title">Centrality Profile</div>
              <PlotlyChart
                traces={buildRadar(c)}
                layout={radarLayout}
                height={220}
              />
            </div>
            <div class="card mini-card">
              <div class="mini-title">Payment Composition</div>
              <PlotlyChart
                traces={buildDonut(c)}
                layout={donutLayout}
                height={180}
              />
            </div>
          </div>
        {/if}
      {/await}

      <!-- Ego network -->
      <div class="card ego-card">
        <div class="ego-title">Ego Network</div>
        <svg bind:this={egoEl} class="ego-svg"></svg>
      </div>
    </div>

    <!-- ── 5-year trajectory ──────────────────────────────────── -->
    {#await trajectoryPromise then trajData}
      {#if trajData?.rows?.length > 1}
        <div class="card traj-card">
          <div class="traj-title">
            5-Year Payment Trajectory (Total Received)
          </div>
          <PlotlyChart
            traces={buildTraj(trajData.rows)}
            layout={trajLayout}
            height={200}
          />
        </div>
      {/if}
    {/await}

    <!-- ── Edge tables ─────────────────────────────────────────── -->
    {#if data.incoming_edges?.rows?.length}
      <div class="card edge-card">
        <div class="edge-title">
          Incoming Payments ({data.incoming_edges.total_rows} total)
        </div>
        <DataTable
          columns={IN_COLS}
          rows={data.incoming_edges.rows}
          pageSize={15}
        />
      </div>
    {/if}

    {#if data.outgoing_edges?.rows?.length}
      <div class="card edge-card">
        <div class="edge-title">
          Outgoing Payments ({data.outgoing_edges.total_rows} total)
        </div>
        <DataTable
          columns={OUT_COLS}
          rows={data.outgoing_edges.rows}
          pageSize={15}
        />
      </div>
    {/if}
  {:catch err}
    <p class="error-message">Failed to load node: {err.message}</p>
  {/await}
{/if}

<style>
  /* Top 3-column layout */
  .top-layout {
    display: grid;
    grid-template-columns: 230px 280px 1fr;
    gap: 14px;
    margin-bottom: 16px;
  }

  /* Profile */
  .profile-card {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .node-type {
    align-self: flex-start;
    margin-bottom: 4px;
  }
  .node-name {
    font-size: 16px;
    font-weight: 700;
    line-height: 1.3;
    margin: 0;
  }
  .node-meta {
    font-size: 12px;
    color: var(--color-muted);
  }
  .credential {
    font-style: italic;
  }
  .node-id {
    font-size: 10px;
    color: var(--color-muted);
    margin-top: 4px;
    font-family: monospace;
  }

  .centrality-section {
    margin-top: 12px;
    border-top: 1px solid var(--color-border);
    padding-top: 10px;
  }
  .centrality-title {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.7px;
    color: var(--color-muted);
    margin-bottom: 8px;
  }
  .c-row {
    display: flex;
    justify-content: space-between;
    padding: 3px 0;
    font-size: 12px;
    border-bottom: 1px solid var(--color-border);
  }
  .c-row:last-child {
    border-bottom: none;
  }
  .c-key {
    color: var(--color-muted);
  }
  .c-val {
    font-weight: 600;
    color: var(--color-heading);
  }

  /* Charts column */
  .charts-col {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .mini-card {
    padding: 10px;
  }
  .mini-title {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--color-muted);
    margin-bottom: 2px;
  }

  /* Ego network */
  .ego-card {
    padding: 10px;
    min-width: 0;
  }
  .ego-title {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--color-muted);
    margin-bottom: 6px;
  }
  .ego-svg {
    width: 100%;
    height: 300px;
    display: block;
    cursor: grab;
  }
  .ego-svg:active {
    cursor: grabbing;
  }

  /* Trajectory */
  .traj-card {
    margin-bottom: 16px;
  }
  .traj-title {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--color-muted);
    margin-bottom: 4px;
  }

  /* Edge tables */
  .edge-card {
    margin-bottom: 16px;
  }
  .edge-title {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--color-muted);
    margin-bottom: 10px;
  }

  @media (max-width: 900px) {
    .top-layout {
      grid-template-columns: 1fr 1fr;
    }
    .ego-card {
      grid-column: 1 / -1;
    }
  }
  @media (max-width: 600px) {
    .top-layout {
      grid-template-columns: 1fr;
    }
  }
</style>
