<script>
  import { selectedYear } from "../stores.js";
  import { getGraphData, getCommunityAssignments } from "../api.js";
  import LoadingSpinner from "../components/LoadingSpinner.svelte";
  import * as d3 from "d3";

  // ── Config state ──────────────────────────────────────────────
  let nodeLimit = $state(300);
  let edgeLimit = $state(600);
  let loading = $state(false);
  let error = $state("");
  let loaded = $state(false);
  let svgEl = $state(null);

  // Filter / display state
  let colorMode = $state("type"); // 'type' | 'community'
  let showPhysician = $state(true);
  let showManufacturer = $state(true);
  let showHospital = $state(true);
  let searchQuery = $state("");
  let sizeBy = $state("fixed"); // 'fixed' | 'degree'
  let minEdgeWeight = $state(0); // USD filter (0 = no filter)

  // Community assignment map: nodeId → communityId
  let communityMap = $state({});
  let communityColors = $state({});

  // Raw loaded data (kept so filters re-draw without re-fetch)
  let rawNodes = $state([]);
  let rawLinks = $state([]);

  // D3 sim reference for re-draw
  let sim;

  // ── Type colours ──────────────────────────────────────────────
  const TYPE_COLOR = {
    Physician: "#4e79a7",
    Manufacturer: "#f28e2b",
    TeachingHospital: "#e15759",
  };

  // ── Community colour scale (up to 20 distinct communities) ───
  const COM_PALETTE = d3.schemeTableau10.concat([
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
    "#aec7e8",
    "#ffbb78",
    "#98df8a",
    "#ff9896",
  ]);

  function communityColor(cid) {
    if (communityColors[cid]) return communityColors[cid];
    const keys = Object.keys(communityColors);
    const c = COM_PALETTE[keys.length % COM_PALETTE.length];
    communityColors[cid] = c;
    return c;
  }

  function nodeColor(d) {
    if (colorMode === "community") {
      const cid = communityMap[d.id];
      return cid != null ? communityColor(cid) : "#888";
    }
    return TYPE_COLOR[d.type] ?? "#999";
  }

  // ── Load community assignments when colorMode = community ────
  async function loadCommunities() {
    try {
      const data = await getCommunityAssignments($selectedYear, "bipartite");
      const map = {};
      for (const r of data.rows ?? []) map[r.id] = r.community_id;
      communityMap = map;
    } catch {
      communityMap = {};
    }
  }

  $effect(() => {
    if (colorMode === "community" && Object.keys(communityMap).length === 0) {
      loadCommunities();
    }
  });

  // ── Derived filtered sets ─────────────────────────────────────
  function applyFilters(nodes, links) {
    const allowedTypes = new Set([
      ...(showPhysician ? ["Physician"] : []),
      ...(showManufacturer ? ["Manufacturer"] : []),
      ...(showHospital ? ["TeachingHospital"] : []),
    ]);
    const q = searchQuery.trim().toLowerCase();

    const filteredNodes = nodes.filter((n) => allowedTypes.has(n.type));
    const filteredIds = new Set(filteredNodes.map((n) => n.id));
    const filteredLinks = links.filter((l) => {
      const sid = typeof l.source === "object" ? l.source.id : l.source;
      const tid = typeof l.target === "object" ? l.target.id : l.target;
      return (
        filteredIds.has(sid) &&
        filteredIds.has(tid) &&
        (l.weight ?? 0) >= minEdgeWeight
      );
    });

    return { nodes: filteredNodes, links: filteredLinks, highlight: q };
  }

  // ── Main graph draw ───────────────────────────────────────────
  async function loadGraph() {
    loading = true;
    error = "";
    try {
      const data = await getGraphData($selectedYear, nodeLimit, edgeLimit);
      rawNodes = data.nodes.rows.map((r) => ({
        id: r.id,
        name: r.name ?? r.id,
        type: r.node_type ?? "Unknown",
        state: r.state,
      }));
      const nodeSet = new Set(rawNodes.map((n) => n.id));
      rawLinks = data.edges.rows
        .filter((r) => nodeSet.has(r.src_id) && nodeSet.has(r.dst_id))
        .map((r) => ({
          source: r.src_id,
          target: r.dst_id,
          weight: r.total_amount ?? 1,
        }));

      drawGraph();
      loaded = true;
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function drawGraph() {
    if (!svgEl || !rawNodes.length) return;

    const { nodes, links, highlight } = applyFilters(
      rawNodes.map((n) => ({ ...n })),
      rawLinks.map((l) => ({ ...l })),
    );

    const w = svgEl.clientWidth || 900;
    const h = svgEl.clientHeight || 580;

    d3.select(svgEl).selectAll("*").remove();

    const root = d3.select(svgEl).attr("viewBox", [0, 0, w, h]);
    const g = root.append("g");

    // Compute degree for size-by-degree
    const degreeMap = {};
    for (const l of links) {
      const s = typeof l.source === "object" ? l.source.id : l.source;
      const t = typeof l.target === "object" ? l.target.id : l.target;
      degreeMap[s] = (degreeMap[s] ?? 0) + 1;
      degreeMap[t] = (degreeMap[t] ?? 0) + 1;
    }
    const maxDeg = Math.max(1, ...Object.values(degreeMap));

    const nodeR = (d) => {
      if (sizeBy === "degree")
        return Math.max(
          3,
          Math.min(14, 3 + ((degreeMap[d.id] ?? 0) / maxDeg) * 11),
        );
      return d.type === "Manufacturer" ? 7 : 5;
    };

    if (sim) sim.stop();

    sim = d3
      .forceSimulation(nodes)
      .force(
        "link",
        d3
          .forceLink(links)
          .id((d) => d.id)
          .distance(50),
      )
      .force("charge", d3.forceManyBody().strength(-60))
      .force("center", d3.forceCenter(w / 2, h / 2))
      .force("collision", d3.forceCollide(7));

    const link = g
      .append("g")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", "rgba(255,255,255,.07)")
      .attr("stroke-width", (d) => Math.max(0.4, Math.log1p(d.weight) / 10));

    const node = g
      .append("g")
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("r", nodeR)
      .attr("fill", (d) => nodeColor(d))
      .attr("fill-opacity", (d) => {
        if (!highlight) return 0.85;
        return (d.name ?? "").toLowerCase().includes(highlight) ? 1 : 0.15;
      })
      .attr("stroke", (d) => {
        if (highlight && (d.name ?? "").toLowerCase().includes(highlight))
          return "#fff";
        return "none";
      })
      .attr("stroke-width", 1.5)
      .call(
        d3
          .drag()
          .on("start", (e, d) => {
            if (!e.active) sim.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (e, d) => {
            d.fx = e.x;
            d.fy = e.y;
          })
          .on("end", (e, d) => {
            if (!e.active) sim.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          }),
      );

    node
      .append("title")
      .text((d) => `${d.name} (${d.type})${d.state ? " · " + d.state : ""}`);
    node.on("click", (_, d) => {
      window.location.hash = `node/${d.id}`;
    });

    sim.on("tick", () => {
      link
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);
      node.attr("cx", (d) => d.x).attr("cy", (d) => d.y);
    });

    root.call(
      d3
        .zoom()
        .scaleExtent([0.2, 8])
        .on("zoom", (e) => g.attr("transform", e.transform)),
    );
  }

  // Re-draw when filters change (only if graph is already loaded)
  $effect(() => {
    // touch all filter deps
    const _ = [
      showPhysician,
      showManufacturer,
      showHospital,
      searchQuery,
      sizeBy,
      minEdgeWeight,
      colorMode,
      communityMap,
    ];
    if (loaded) drawGraph();
  });
</script>

<!-- ── Header ────────────────────────────────────────────────────── -->
<div class="page-header">
  <h1 class="page-title">Network Graph</h1>
  <div class="controls">
    <label class="range-label"
      >Nodes <strong>{nodeLimit}</strong>
      <input
        type="range"
        min="50"
        max="1000"
        step="50"
        bind:value={nodeLimit}
      />
    </label>
    <label class="range-label"
      >Edges <strong>{edgeLimit}</strong>
      <input
        type="range"
        min="100"
        max="3000"
        step="100"
        bind:value={edgeLimit}
      />
    </label>
    <button class="btn btn-primary" onclick={loadGraph} disabled={loading}>
      {loading ? "Loading…" : loaded ? "Reload" : "Load Graph"}
    </button>
  </div>
</div>

<!-- ── Filter / display panel ────────────────────────────────────── -->
<div class="panel card">
  <!-- Node type filters -->
  <div class="panel-group">
    <div class="panel-label">Node types</div>
    <label class="check-label"
      ><input type="checkbox" bind:checked={showPhysician} />
      <span class="dot" style="background:#4e79a7"></span> Physician</label
    >
    <label class="check-label"
      ><input type="checkbox" bind:checked={showManufacturer} />
      <span class="dot" style="background:#f28e2b"></span> Manufacturer</label
    >
    <label class="check-label"
      ><input type="checkbox" bind:checked={showHospital} />
      <span class="dot" style="background:#e15759"></span> Hospital</label
    >
  </div>

  <!-- Colour mode -->
  <div class="panel-group">
    <div class="panel-label">Colour by</div>
    <button
      class="btn"
      class:btn-active={colorMode === "type"}
      class:btn-ghost={colorMode !== "type"}
      onclick={() => (colorMode = "type")}>Type</button
    >
    <button
      class="btn"
      class:btn-active={colorMode === "community"}
      class:btn-ghost={colorMode !== "community"}
      onclick={() => (colorMode = "community")}>Community</button
    >
  </div>

  <!-- Node size -->
  <div class="panel-group">
    <div class="panel-label">Size by</div>
    <button
      class="btn"
      class:btn-active={sizeBy === "fixed"}
      class:btn-ghost={sizeBy !== "fixed"}
      onclick={() => (sizeBy = "fixed")}>Fixed</button
    >
    <button
      class="btn"
      class:btn-active={sizeBy === "degree"}
      class:btn-ghost={sizeBy !== "degree"}
      onclick={() => (sizeBy = "degree")}>Degree</button
    >
  </div>

  <!-- Search highlight -->
  <div class="panel-group panel-search">
    <div class="panel-label">Highlight</div>
    <input
      type="text"
      placeholder="Node name…"
      bind:value={searchQuery}
      class="search-input"
    />
  </div>

  <!-- Min edge weight -->
  <div class="panel-group">
    <div class="panel-label">Min edge $</div>
    <label class="range-label">
      <strong
        >{minEdgeWeight >= 1e6
          ? `$${(minEdgeWeight / 1e6).toFixed(1)}M`
          : minEdgeWeight >= 1e3
            ? `$${(minEdgeWeight / 1e3).toFixed(0)}K`
            : "$0"}</strong
      >
      <input
        type="range"
        min="0"
        max="500000"
        step="5000"
        bind:value={minEdgeWeight}
      />
    </label>
  </div>

  <!-- Legend -->
  <div class="panel-group panel-hint">
    <span class="hint"
      >Scroll to zoom · Drag to pan · Click node for detail</span
    >
  </div>
</div>

{#if error}
  <p class="error-message">{error}</p>
{/if}

<div class="graph-card card">
  {#if loading}
    <LoadingSpinner />
  {:else if !loaded}
    <div class="chart-placeholder" style="height:560px;">
      Configure limits above and click <strong>Load Graph</strong> to render the payment
      network.
    </div>
  {/if}
  <svg
    bind:this={svgEl}
    class="graph-svg"
    style="display:{loaded ? 'block' : 'none'}"
  ></svg>
</div>

<style>
  .controls {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }
  .controls label {
    font-size: 12px;
    color: var(--color-muted);
    white-space: nowrap;
  }
  .controls input[type="range"] {
    width: 100px;
  }

  /* Filter panel */
  .panel {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    align-items: center;
    padding: 10px 14px;
    margin-bottom: 12px;
  }

  .panel-group {
    display: flex;
    align-items: center;
    gap: 6px;
    border-right: 1px solid var(--color-border);
    padding-right: 16px;
  }
  .panel-group:last-child {
    border-right: none;
    padding-right: 0;
  }

  .panel-label {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--color-muted);
    white-space: nowrap;
    margin-right: 4px;
  }

  .check-label {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 12px;
    color: var(--color-text);
    cursor: pointer;
    white-space: nowrap;
  }
  .check-label input {
    accent-color: var(--color-accent);
    cursor: pointer;
  }

  .dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  .panel-search .search-input {
    background: var(--color-bg);
    border: 1px solid var(--color-border);
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 12px;
    color: var(--color-text);
    outline: none;
    width: 140px;
  }
  .panel-search .search-input:focus {
    border-color: var(--color-accent);
  }

  .panel-hint .hint {
    font-size: 11px;
    color: var(--color-muted);
    font-style: italic;
  }

  .range-label {
    font-size: 12px;
    color: var(--color-muted);
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .range-label input[type="range"] {
    width: 100px;
  }

  /* Graph canvas */
  .graph-card {
    padding: 0;
    overflow: hidden;
  }
  .graph-svg {
    width: 100%;
    height: 560px;
    cursor: grab;
    display: block;
  }
  .graph-svg:active {
    cursor: grabbing;
  }
</style>
