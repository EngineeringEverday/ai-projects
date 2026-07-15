<script>
  import { selectedYear } from "../stores.js";
  import { getNode, getNodeCentrality, getTrajectory } from "../api.js";
  import { tick } from "svelte";
  import PlotlyChart from "./PlotlyChart.svelte";
  import * as d3 from "d3";

  let { id, onClose } = $props();

  // ── Data fetches ──────────────────────────────────────────────
  let nodeData = $state(null);
  let centralityData = $state(null);
  let trajectoryRows = $state([]); // always the rows array
  let loading = $state(true);
  let error = $state("");
  let tab = $state("profile"); // 'profile' | 'network' | 'payments'

  let egoEl = $state(null);

  $effect(() => {
    if (!id) return;
    loading = true;
    error = "";
    nodeData = null;
    centralityData = null;
    trajectoryRows = [];

    Promise.all([
      getNode($selectedYear, id),
      getNodeCentrality($selectedYear, id),
      getTrajectory("in_strength", id).catch(() => null),
    ])
      .then(([nd, cd, td]) => {
        nodeData = nd;
        centralityData = cd;
        // Normalise trajectory - API may return { rows:[…] } or { data:[…] } or plain array
        const raw = td?.rows ?? td?.data ?? (Array.isArray(td) ? td : []);
        trajectoryRows = raw.filter((r) => r?.year != null);
        loading = false;
      })
      .catch((e) => {
        error = e.message;
        loading = false;
      });
  });

  // Redraw ego when tab switches to network and data is ready
  // Use tick() so egoEl is bound before drawing
  $effect(() => {
    if (tab === "network" && nodeData) {
      tick().then(() => {
        if (egoEl) drawEgo(nodeData);
      });
    }
  });

  // ── Formatters ────────────────────────────────────────────────
  function fmtUSD(n) {
    if (!n) return "$0";
    if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
    if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
    return `$${(+n).toFixed(0)}`;
  }

  function fmtPct(n) {
    return n != null ? `${(n * 100).toFixed(1)}%` : "-";
  }

  // ── Risk scoring ──────────────────────────────────────────────
  function riskLevel(c) {
    if (!c) return { label: "Unknown", cls: "badge-info" };
    const score =
      (c.cash_ratio ?? 0) +
      (c.disputed_ratio ?? 0) * 2 +
      (c.in_strength > 1e6 ? 0.3 : 0);
    if (score > 1.2) return { label: "HIGH RISK", cls: "badge-danger" };
    if (score > 0.6) return { label: "WATCHLIST", cls: "badge-warning" };
    return { label: "Normal", cls: "badge-info" };
  }

  // ── Insight text generator ────────────────────────────────────
  function makeInsight(n, c, rows) {
    if (!n || !c) return null;
    const parts = [];
    const pct = c.cash_ratio != null ? Math.round(c.cash_ratio * 100) : 0;
    if (pct > 50)
      parts.push(
        `<strong>${pct}%</strong> of payments are in cash - a pattern associated with undisclosed financial ties`,
      );
    if (c.in_strength > 5e5)
      parts.push(
        `received <strong>${fmtUSD(c.in_strength)}</strong> in ${$selectedYear}`,
      );
    if (c.betweenness > 0.01)
      parts.push(
        `high betweenness centrality indicates a <strong>bridge position</strong> between manufacturer clusters`,
      );

    if (rows.length >= 2) {
      const first = rows[0]?.in_strength ?? 0;
      const last = rows[rows.length - 1]?.in_strength ?? 0;
      if (first > 0) {
        const growth = Math.round(((last - first) / first) * 100);
        if (Math.abs(growth) > 50)
          parts.push(
            `payments ${growth > 0 ? "grew" : "fell"} <strong>${Math.abs(growth)}%</strong> from ${rows[0].year} to ${rows[rows.length - 1].year}`,
          );
      }
    }
    return parts.length > 0 ? parts.join(" · ") : null;
  }

  // ── Radar chart ───────────────────────────────────────────────
  function buildRadar(c) {
    const dims = [
      { key: "pagerank", label: "PageRank", max: 0.002 },
      { key: "in_strength", label: "Payments", max: 2e6 },
      { key: "betweenness", label: "Betweenness", max: 0.05 },
      { key: "authority_score", label: "Authority", max: 0.002 },
      { key: "payment_diversity", label: "Diversity", max: 20 },
    ];
    const vals = dims.map((d) => Math.min(1, (c[d.key] ?? 0) / d.max));
    const labels = dims.map((d) => d.label);
    return [
      {
        type: "scatterpolar",
        r: [...vals, vals[0]],
        theta: [...labels, labels[0]],
        fill: "toself",
        fillcolor: "rgba(124,111,205,0.15)",
        line: { color: "#7c6fcd", width: 2 },
        name: "Centrality",
      },
    ];
  }

  const radarLayout = {
    polar: {
      bgcolor: "transparent",
      angularaxis: {
        tickfont: { color: "#5e6578", size: 10 },
        linecolor: "#222538",
        gridcolor: "#222538",
      },
      radialaxis: {
        visible: true,
        range: [0, 1],
        tickfont: { color: "#5e6578", size: 8 },
        gridcolor: "#222538",
        linecolor: "#222538",
      },
    },
    showlegend: false,
    margin: { t: 16, r: 20, b: 16, l: 20 },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
  };

  // ── Payment composition donut ─────────────────────────────────
  function buildDonut(c) {
    const cash = Math.max(0, c.cash_ratio ?? 0);
    const disputed = Math.max(0, c.disputed_ratio ?? 0);
    const third = Math.max(0, c.third_party_ratio ?? 0);
    const other = Math.max(0, 1 - cash - disputed - third);
    return [
      {
        type: "pie",
        hole: 0.58,
        labels: ["Cash", "Disputed", "Third-party", "Other"],
        values: [cash, disputed, third, other],
        marker: { colors: ["#f87171", "#f59e0b", "#4e79a7", "#4ade80"] },
        textinfo: "percent",
        textfont: { size: 10, color: "#c8d0e0" },
        hovertemplate: "<b>%{label}</b><br>%{percent}<extra></extra>",
      },
    ];
  }

  const donutLayout = {
    margin: { t: 4, r: 4, b: 4, l: 4 },
    showlegend: true,
    legend: { font: { size: 9, color: "#5e6578" }, orientation: "h", y: -0.12 },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
  };

  // ── Trajectory line ───────────────────────────────────────────
  function buildTraj(rows) {
    return [
      {
        type: "scatter",
        mode: "lines+markers",
        x: rows.map((r) => r.year),
        y: rows.map((r) => r.in_strength),
        line: { color: "#7c6fcd", width: 2.5 },
        marker: { size: 7, color: "#7c6fcd" },
        fill: "tozeroy",
        fillcolor: "rgba(124,111,205,0.08)",
        hovertemplate: "<b>%{x}</b><br>$%{y:,.0f}<extra></extra>",
      },
    ];
  }

  const trajLayout = {
    margin: { t: 8, r: 10, b: 36, l: 68 },
    xaxis: {
      dtick: 1,
      tickfont: { size: 10, color: "#5e6578" },
      gridcolor: "#222538",
      linecolor: "#222538",
    },
    yaxis: {
      tickprefix: "$",
      tickfont: { size: 10, color: "#5e6578" },
      gridcolor: "#222538",
      linecolor: "#222538",
    },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
  };

  // ── Ego network (D3 force) ────────────────────────────────────
  function drawEgo(data) {
    if (!egoEl) return;
    const center = data.node;
    const incoming = data.incoming_edges?.rows ?? [];
    const outgoing = data.outgoing_edges?.rows ?? [];

    const nodes = [
      {
        id: center.id,
        name: center.name,
        type: center.node_type,
        isCenter: true,
      },
      ...incoming
        .slice(0, 20)
        .map((e) => ({
          id: e.src_id,
          name: e.src_name ?? e.src_id,
          type: e.src_type ?? "Manufacturer",
        })),
      ...outgoing
        .slice(0, 20)
        .map((e) => ({
          id: e.dst_id,
          name: e.dst_name ?? e.dst_id,
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
        .slice(0, 20)
        .map((e) => ({
          source: e.src_id,
          target: center.id,
          w: e.total_amount ?? 1,
        })),
      ...outgoing
        .slice(0, 20)
        .map((e) => ({
          source: center.id,
          target: e.dst_id,
          w: e.total_amount ?? 1,
        })),
    ];

    const W = egoEl.clientWidth || 460,
      H = 320;
    d3.select(egoEl).selectAll("*").remove();
    const svg = d3.select(egoEl).attr("viewBox", [0, 0, W, H]);
    const g = svg.append("g");

    const colorMap = {
      Physician: "#4e79a7",
      Manufacturer: "#f28e2b",
      TeachingHospital: "#e15759",
    };
    const nc = (d) => (d.isCenter ? "#7c6fcd" : (colorMap[d.type] ?? "#888"));
    const nr = (d) => (d.isCenter ? 9 : 5);

    const sim = d3
      .forceSimulation(uniqueNodes)
      .force(
        "link",
        d3
          .forceLink(links)
          .id((d) => d.id)
          .distance(55),
      )
      .force("charge", d3.forceManyBody().strength(-70))
      .force("center", d3.forceCenter(W / 2, H / 2))
      .force("collision", d3.forceCollide(8));

    const link = g
      .append("g")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", "rgba(255,255,255,.08)")
      .attr("stroke-width", (d) => Math.max(0.4, Math.log1p(d.w) / 10));

    const node = g
      .append("g")
      .selectAll("circle")
      .data(uniqueNodes)
      .join("circle")
      .attr("r", nr)
      .attr("fill", nc)
      .attr("fill-opacity", 0.85);

    node.append("title").text((d) => d.name ?? d.id);
    node.style("cursor", (d) => (d.isCenter ? "default" : "pointer"));
    node.on("click", (_, d) => {
      if (!d.isCenter && d.id !== id) {
        import("../stores.js").then((m) => m.openNode(d.id));
      }
    });

    // Labels for center + high-degree
    const degMap = {};
    links.forEach((l) => {
      const s = typeof l.source === "object" ? l.source.id : l.source;
      const t = typeof l.target === "object" ? l.target.id : l.target;
      degMap[s] = (degMap[s] ?? 0) + 1;
      degMap[t] = (degMap[t] ?? 0) + 1;
    });

    const label = g
      .append("g")
      .selectAll("text")
      .data(uniqueNodes.filter((n) => n.isCenter || (degMap[n.id] ?? 0) > 2))
      .join("text")
      .attr("font-size", (d) => (d.isCenter ? 11 : 9))
      .attr("fill", (d) => (d.isCenter ? "#f0f4ff" : "#5e6578"))
      .attr("text-anchor", "middle")
      .attr("dy", (d) => -nr(d) - 2)
      .text((d) => (d.name ?? d.id).slice(0, 18));

    sim.on("tick", () => {
      link
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);
      node.attr("cx", (d) => d.x).attr("cy", (d) => d.y);
      label.attr("x", (d) => d.x).attr("y", (d) => d.y);
    });

    svg.call(
      d3
        .zoom()
        .scaleExtent([0.3, 5])
        .on("zoom", (e) => g.attr("transform", e.transform)),
    );
  }
</script>

<!-- Panel header -->
<div class="panel-header">
  <button class="close-btn" onclick={onClose}>✕</button>
  <div class="panel-title">Entity Dossier</div>
  <span class="panel-year">{$selectedYear}</span>
</div>

{#if loading}
  <div class="loading-center">
    <div class="spinner"></div>
    <span>Loading dossier…</span>
  </div>
{:else if error}
  <div class="p-4"><div class="error-msg">{error}</div></div>
{:else if nodeData}
  {@const n = nodeData.node}
  {@const c = centralityData?.rows?.[0] ?? null}
  {@const traj = trajectoryRows}
  {@const risk = riskLevel(c)}
  {@const insight = makeInsight(n, c, trajectoryRows)}

  <!-- Identity -->
  <div class="identity-block">
    <div class="flex items-start justify-between gap-3 mb-3">
      <div>
        <span
          class="badge badge-{(n.node_type ?? '').toLowerCase()} mb-2"
          style="display:inline-block">{n.node_type}</span
        >
        <h2 class="entity-name">{n.name}</h2>
        {#if n.specialty}
          <div class="entity-sub">{n.specialty.split("|").pop()}</div>
        {/if}
        <div class="entity-sub">
          {[n.city, n.state].filter(Boolean).join(", ")}
        </div>
      </div>
      <span class="badge {risk.cls}" style="white-space:nowrap"
        >{risk.label}</span
      >
    </div>

    <!-- Key stats row -->
    {#if c}
      <div class="kpi-row">
        <div class="kpi-box">
          <div class="kpi-label">Total Received</div>
          <div class="kpi-val">{fmtUSD(c.in_strength)}</div>
        </div>
        <div class="kpi-box">
          <div class="kpi-label">Paying Companies</div>
          <div class="kpi-val">{c.in_degree ?? "-"}</div>
        </div>
        <div class="kpi-box">
          <div class="kpi-label">Cash Ratio</div>
          <div
            class="kpi-val"
            style="color:{(c.cash_ratio ?? 0) > 0.5
              ? 'var(--color-danger)'
              : 'var(--color-text)'}"
          >
            {fmtPct(c.cash_ratio)}
          </div>
        </div>
        <div class="kpi-box">
          <div class="kpi-label">PageRank</div>
          <div class="kpi-val">{c.pagerank?.toFixed(5) ?? "-"}</div>
        </div>
      </div>
    {/if}

    <!-- Insight block -->
    {#if insight}
      <div class="insight-block" style="margin-top:10px;margin-bottom:0">
        {@html insight}
      </div>
    {/if}
  </div>

  <!-- Tabs -->
  <div class="tab-row" style="padding: 0 16px; margin-bottom: 0;">
    {#each [["profile", "Profile"], ["network", "Ego Network"], ["payments", "Payments"]] as [t, lbl]}
      <button class="tab-btn" class:active={tab === t} onclick={() => (tab = t)}
        >{lbl}</button
      >
    {/each}
  </div>

  <!-- Tab: Profile -->
  {#if tab === "profile"}
    <div class="panel-body">
      <!-- Charts row: radar + donut -->
      {#if c}
        <div class="charts-row">
          <div class="chart-half">
            <div class="section-label">Centrality Fingerprint</div>
            <PlotlyChart
              traces={buildRadar(c)}
              layout={radarLayout}
              height={200}
            />
          </div>
          <div class="chart-half">
            <div class="section-label">Payment Mix</div>
            <PlotlyChart
              traces={buildDonut(c)}
              layout={donutLayout}
              height={200}
            />
          </div>
        </div>
      {/if}

      <!-- Trajectory -->
      {#if traj.length > 1}
        <div class="section-label" style="margin-bottom:6px">
          5-Year Payment Trajectory
        </div>
        <PlotlyChart
          traces={buildTraj(traj)}
          layout={trajLayout}
          height={180}
        />
      {/if}

      <!-- Full metrics list -->
      {#if c}
        <div class="metrics-grid">
          {#each [["PageRank", c.pagerank?.toFixed(6)], ["Betweenness", c.betweenness?.toFixed(5)], ["Authority", c.authority_score?.toFixed(5)], ["In-degree", c.in_degree], ["Out-degree", c.out_degree], ["Diversity", c.payment_diversity], ["Disputed ratio", fmtPct(c.disputed_ratio)], ["3rd-party ratio", fmtPct(c.third_party_ratio)]] as [k, v]}
            {#if v != null && v !== "-"}
              <div class="metric-row">
                <span class="metric-key">{k}</span>
                <span class="metric-val">{v}</span>
              </div>
            {/if}
          {/each}
        </div>
      {/if}
    </div>

    <!-- Tab: Ego Network -->
  {:else if tab === "network"}
    <div class="ego-wrap">
      <div class="ego-hint">
        Drag to pan · Scroll to zoom · Click node for dossier
      </div>
      <svg bind:this={egoEl} class="ego-svg"></svg>
    </div>

    <!-- Tab: Payments -->
  {:else}
    <div class="panel-body">
      {#if nodeData.incoming_edges?.rows?.length}
        <div class="section-label" style="margin-bottom:8px">
          Incoming Payments ({nodeData.incoming_edges.total_rows} total)
        </div>
        <div
          class="table-wrap"
          style="max-height:260px;overflow-y:auto;margin-bottom:16px"
        >
          <table class="data-table">
            <thead
              ><tr>
                {#each ["From", "Amount", "Count", "Nature"] as h}
                  <th>{h}</th>
                {/each}
              </tr></thead
            >
            <tbody>
              {#each nodeData.incoming_edges.rows as r}
                <tr
                  onclick={() => (window.location.hash = `node/${r.src_id}`)}
                  style="cursor:pointer"
                >
                  <td class="truncate" style="max-width:140px">{r.src_id}</td>
                  <td>{fmtUSD(r.total_amount)}</td>
                  <td>{r.payment_count}</td>
                  <td class="truncate" style="max-width:120px"
                    >{r.natures ?? "-"}</td
                  >
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}

      {#if nodeData.outgoing_edges?.rows?.length}
        <div class="section-label" style="margin-bottom:8px">
          Outgoing Payments ({nodeData.outgoing_edges.total_rows} total)
        </div>
        <div class="table-wrap" style="max-height:260px;overflow-y:auto">
          <table class="data-table">
            <thead
              ><tr>
                {#each ["To", "Type", "Amount", "Count"] as h}
                  <th>{h}</th>
                {/each}
              </tr></thead
            >
            <tbody>
              {#each nodeData.outgoing_edges.rows as r}
                <tr
                  onclick={() => (window.location.hash = `node/${r.dst_id}`)}
                  style="cursor:pointer"
                >
                  <td class="truncate" style="max-width:140px">{r.dst_id}</td>
                  <td>{r.dst_type ?? "-"}</td>
                  <td>{fmtUSD(r.total_amount)}</td>
                  <td>{r.payment_count}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  {/if}
{/if}

<style>
  .panel-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 16px;
    border-bottom: 1px solid var(--color-border);
    flex-shrink: 0;
  }
  .close-btn {
    background: none;
    border: none;
    color: var(--color-muted);
    font-size: 14px;
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 4px;
    transition: color 0.1s;
    font-family: var(--font-sans);
  }
  .close-btn:hover {
    color: var(--color-heading);
  }
  .panel-title {
    flex: 1;
    font-size: 13px;
    font-weight: 600;
    color: var(--color-heading);
  }
  .panel-year {
    font-size: 11px;
    color: var(--color-accent);
    background: var(--color-accent-dim);
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
  }

  .identity-block {
    padding: 16px;
    border-bottom: 1px solid var(--color-border);
  }
  .entity-name {
    font-size: 16px;
    font-weight: 700;
    color: var(--color-heading);
    line-height: 1.25;
    margin-bottom: 3px;
  }
  .entity-sub {
    font-size: 11px;
    color: var(--color-muted);
    margin-bottom: 2px;
  }

  .kpi-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    margin-top: 12px;
  }
  .kpi-box {
    background: var(--color-bg);
    border: 1px solid var(--color-border);
    border-radius: 7px;
    padding: 8px;
    text-align: center;
  }
  .kpi-label {
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--color-muted);
    margin-bottom: 4px;
  }
  .kpi-val {
    font-size: 14px;
    font-weight: 700;
    color: var(--color-heading);
    line-height: 1;
  }

  .panel-body {
    padding: 16px;
    flex: 1;
  }

  .charts-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 16px;
  }
  .chart-half {
    min-width: 0;
  }

  .metrics-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0;
    margin-top: 14px;
    border: 1px solid var(--color-border);
    border-radius: 7px;
    overflow: hidden;
  }
  .metric-row {
    display: flex;
    justify-content: space-between;
    padding: 7px 10px;
    border-bottom: 1px solid var(--color-border);
    font-size: 11px;
  }
  .metric-row:last-child,
  .metric-row:nth-last-child(2):nth-child(odd) {
    border-bottom: none;
  }
  .metric-key {
    color: var(--color-muted);
  }
  .metric-val {
    font-weight: 600;
    color: var(--color-heading);
    font-family: var(--font-mono);
    font-size: 10px;
  }

  .ego-wrap {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 8px;
  }
  .ego-hint {
    font-size: 10px;
    color: var(--color-muted);
    text-align: center;
    margin-bottom: 4px;
    font-style: italic;
  }
  .ego-svg {
    flex: 1;
    width: 100%;
    min-height: 320px;
    cursor: grab;
    display: block;
  }
  .ego-svg:active {
    cursor: grabbing;
  }
</style>
