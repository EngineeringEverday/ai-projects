<script>
  import { onMount, tick } from "svelte";
  import * as THREE from "three";
  import * as d3 from "d3";
  import { selectedYear, openNode } from "../stores.js";
  import {
    getGraphData,
    getCommunityAssignments,
    searchNodes,
  } from "../api.js";
  import ForceGraph3D from "3d-force-graph";

  let { stateFilter = null } = $props();

  let containerEl = $state(null);
  let g = null;
  let graphReady = $state(false);

  let loading = $state(false);
  let loaded = $state(false);
  let error = $state("");
  let nodeCount = $state(0);
  let edgeCount = $state(0);

  // ── View mode ─────────────────────────────────────────────────
  let viewMode = $state("3d"); // '3d' | '2d'
  let svgEl = $state(null); // 2D SVG element
  let rawGraphData = null; // { nodes, links } - snapshot at load, shared by 2D

  // ── UI state ─────────────────────────────────────────────────
  let colorMode = $state("type"); // 'type' | 'community'
  let typeFilter = $state(null);
  let nodeLimit = $state(60);
  let autoRot = $state(true);
  let pathMode = $state(false);

  // ── Node search ───────────────────────────────────────────────
  let nodeQuery = $state("");
  let nodeResults = $state([]);
  let nodeSearchOpen = $state(false);
  let nodeSearchTimer;

  function onNodeQueryInput() {
    clearTimeout(nodeSearchTimer);
    if (nodeQuery.trim().length < 2) {
      nodeResults = [];
      nodeSearchOpen = false;
      return;
    }
    nodeSearchTimer = setTimeout(async () => {
      try {
        const d = await searchNodes(nodeQuery.trim(), $selectedYear, 8);
        nodeResults = d.rows ?? [];
        nodeSearchOpen = nodeResults.length > 0;
      } catch {
        nodeResults = [];
        nodeSearchOpen = false;
      }
    }, 220);
  }

  function pickSearchNode(r) {
    nodeQuery = "";
    nodeResults = [];
    nodeSearchOpen = false;
    if (pathMode) {
      if (!pathStart) {
        pathStart = r.id;
      } else if (r.id !== pathStart && !pathEnd) {
        pathEnd = r.id;
        const data = viewMode === "3d" ? g?.graphData() : rawGraphData;
        if (data)
          pathResult = findPathFromData(
            pathStart,
            pathEnd,
            data.nodes,
            data.links,
          );
        applyColors();
        if (pathResult) {
          if (viewMode === "3d") {
            const pathNodes = g
              .graphData()
              .nodes.filter((n) => pathResult.path.includes(n.id));
            setTimeout(() => fitCamera(pathNodes, 700, true), 50);
          }
          tick().then(() => drawPathChain(pathResult.info));
        }
      }
    } else {
      // Highlight in graph, open dossier
      highlightedNodeId = r.id;
      openNode(r.id);
      if (viewMode === "3d" && g) {
        const node = g.graphData().nodes.find((n) => n.id === r.id);
        if (node?.x != null) {
          const { x = 0, y = 0, z = 0 } = node;
          const len = Math.hypot(x, y, z) || 1;
          g.cameraPosition(
            {
              x: (x * (len + 60)) / len,
              y: (y * (len + 60)) / len,
              z: (z * (len + 60)) / len,
            },
            node,
            700,
          );
        }
      }
      if (viewMode === "2d") recolor2D();
      setTimeout(() => {
        highlightedNodeId = null;
        applyColors();
      }, 2500);
    }
  }

  // ── Shortest-path state ───────────────────────────────────────
  let pathStart = $state(null);
  let pathEnd = $state(null);
  let pathResult = $state(null);

  // ── Highlighted node (from search) ───────────────────────────
  let highlightedNodeId = $state(null);

  // ── Onboarding overlay ────────────────────────────────────────
  let showHint = $state(true);
  let hintTimer = null;

  function dismissHint() {
    if (!showHint) return;
    showHint = false;
    if (hintTimer) clearTimeout(hintTimer);
  }

  // ── Path chain D3 viz ─────────────────────────────────────────
  let pathChainEl = $state(null);

  let communityMap = {};
  let comColorCache = {};

  const TYPE_COLOR = {
    Manufacturer: "#FF9F43",
    Physician: "#74B9FF",
    TeachingHospital: "#FF6B6B",
  };

  const COM_PALETTE = [
    "#FF9F43",
    "#74B9FF",
    "#55EFC4",
    "#FD79A8",
    "#A29BFE",
    "#FDCB6E",
    "#00CEC9",
    "#E17055",
    "#6C5CE7",
    "#00B894",
    "#FAB1A0",
    "#81ECEC",
    "#FFEAA7",
    "#B2BEC3",
    "#636E72",
  ];

  function getComColor(cid) {
    if (comColorCache[cid] == null) {
      const idx = Object.keys(comColorCache).length;
      comColorCache[cid] = COM_PALETTE[idx % COM_PALETTE.length];
    }
    return comColorCache[cid];
  }

  // ── Color functions ───────────────────────────────────────────
  function nodeColorFn(n) {
    // Search highlight
    if (highlightedNodeId && n.id === highlightedNodeId) return "#FFFFFF";
    // Shortest-path highlight
    if (pathResult) {
      if (n.id === pathStart) return "#FDCB6E";
      if (n.id === pathEnd) return "#55EFC4";
      if (pathResult.path.includes(n.id)) return "#FF9F43";
      return "#1C2430";
    }
    // Type filter: dim non-matching
    if (typeFilter && n.node_type !== typeFilter) return "#1C2430";
    // State filter: dim out-of-state
    if (stateFilter && n.state && n.state !== stateFilter) return "#1C2430";
    // Community coloring - use String key so numeric/string IDs match
    if (colorMode === "community") {
      const cid = n.community ?? n.community_id;
      if (cid != null) return getComColor(String(cid));
    }
    return TYPE_COLOR[n.node_type] ?? "#B2BEC3";
  }

  function linkColorFn(link) {
    // Shortest-path: bright green on path edges, invisible otherwise
    if (pathResult) {
      const sk = edgeKey(link.source, link.target);
      if (pathResult.edges.has(sk)) return "#55EFC4";
      return "#151B22";
    }
    // Type / state filter: near-invisible for dimmed edges
    const sType =
      typeof link.source === "object" ? link.source?.node_type : null;
    const tType =
      typeof link.target === "object" ? link.target?.node_type : null;
    if (
      typeFilter &&
      sType &&
      tType &&
      sType !== typeFilter &&
      tType !== typeFilter
    )
      return "#151B22";
    const sState = typeof link.source === "object" ? link.source?.state : null;
    const tState = typeof link.target === "object" ? link.target?.state : null;
    if (
      stateFilter &&
      sState &&
      sState !== stateFilter &&
      tState &&
      tState !== stateFilter
    )
      return "#151B22";
    // Active edge → solid near-white
    return "#C8D4E2";
  }

  function particleColorFn(link) {
    if (pathResult) {
      const sk = edgeKey(link.source, link.target);
      return pathResult.edges.has(sk) ? "#55EFC4" : "rgba(0,0,0,0)";
    }
    if (typeFilter || stateFilter) {
      const sType =
        typeof link.source === "object" ? link.source?.node_type : null;
      const tType =
        typeof link.target === "object" ? link.target?.node_type : null;
      const sState =
        typeof link.source === "object" ? link.source?.state : null;
      const tState =
        typeof link.target === "object" ? link.target?.state : null;
      if (
        typeFilter &&
        sType &&
        tType &&
        sType !== typeFilter &&
        tType !== typeFilter
      )
        return "rgba(0,0,0,0)";
      if (
        stateFilter &&
        sState &&
        sState !== stateFilter &&
        tState &&
        tState !== stateFilter
      )
        return "rgba(0,0,0,0)";
    }
    return "#FF9F43";
  }

  function edgeKey(a, b) {
    const ai = typeof a === "object" ? a.id : a;
    const bi = typeof b === "object" ? b.id : b;
    return `${ai}__${bi}`;
  }

  // ── Text-sprite label above a node ────────────────────────────
  function makeNodeLabel(text, hexColor = "#E6EDF3") {
    const short = text.length > 22 ? text.slice(0, 20) + "…" : text;
    const W = 320,
      H = 72;
    const canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");

    // Background pill
    ctx.fillStyle = "rgba(13,17,23,0.82)";
    const r = 10;
    ctx.beginPath();
    ctx.moveTo(r, 4);
    ctx.lineTo(W - r, 4);
    ctx.arcTo(W - 4, 4, W - 4, H - 4, r);
    ctx.lineTo(W - 4, H - r);
    ctx.arcTo(W - 4, H - 4, 4, H - 4, r);
    ctx.lineTo(r, H - 4);
    ctx.arcTo(4, H - 4, 4, 4, r);
    ctx.lineTo(4, r);
    ctx.arcTo(4, 4, W - 4, 4, r);
    ctx.closePath();
    ctx.fill();

    // Left accent bar
    ctx.fillStyle = hexColor;
    ctx.fillRect(4, 4, 4, H - 8);

    // Text
    ctx.font = "bold 22px Inter, Arial, sans-serif";
    ctx.fillStyle = "#E6EDF3";
    ctx.textAlign = "left";
    ctx.fillText(short, 18, 44);

    const tex = new THREE.CanvasTexture(canvas);
    const mat = new THREE.SpriteMaterial({
      map: tex,
      transparent: true,
      depthWrite: false,
    });
    const sprite = new THREE.Sprite(mat);
    sprite.scale.set(28, 6.5, 1); // world-space units; ~label dimensions
    sprite.position.set(0, 7, 0); // float above node sphere
    return sprite;
  }

  // Build nodeThreeObject fn depending on current filter state
  function makeLabelFn(filterState, filterType) {
    if (!filterState && !filterType) return undefined; // use default spheres
    return (n) => {
      const highlight =
        (filterState && n.state === filterState) ||
        (filterType && n.node_type === filterType);
      if (!highlight) return new THREE.Object3D(); // empty - hides nothing, no label
      return makeNodeLabel(
        n.name ?? n.id,
        TYPE_COLOR[n.node_type] ?? "#E6EDF3",
      );
    };
  }

  // ── Apply colors to 3D graph ──────────────────────────────────
  function applyColors() {
    if (!g || !loaded) return;
    g.nodeColor(nodeColorFn);
    g.linkColor(linkColorFn);
    g.linkDirectionalParticleColor(particleColorFn);
    if (viewMode === "2d") recolor2D();
  }

  // ── Shortest path (BFS on undirected graph) ───────────────────
  function findPathFromData(srcId, dstId, nodes, links) {
    const nodeMap = {};
    nodes.forEach((n) => {
      nodeMap[n.id] = n;
    });

    const adj = {};
    links.forEach((l) => {
      const s = typeof l.source === "object" ? l.source.id : l.source;
      const t = typeof l.target === "object" ? l.target.id : l.target;
      (adj[s] ??= []).push(t);
      (adj[t] ??= []).push(s);
    });

    if (!adj[srcId] || !adj[dstId]) return null;
    const prev = { [srcId]: null };
    const q = [srcId];
    while (q.length) {
      const cur = q.shift();
      if (cur === dstId) break;
      for (const nb of adj[cur] ?? []) {
        if (!(nb in prev)) {
          prev[nb] = cur;
          q.push(nb);
        }
      }
    }
    if (!(dstId in prev)) return null;

    const path = [];
    let cur = dstId;
    while (cur !== null) {
      path.unshift(cur);
      cur = prev[cur];
    }

    const edgeSet = new Set();
    for (let i = 0; i < path.length - 1; i++) {
      edgeSet.add(`${path[i]}__${path[i + 1]}`);
      edgeSet.add(`${path[i + 1]}__${path[i]}`);
    }

    const info = path.map((id) => {
      const n = nodeMap[id];
      return {
        id,
        name: n?.name ?? id,
        type: n?.node_type ?? "?",
        payment: n?.payment ?? 0,
        state: n?.state ?? "-",
      };
    });
    return { path, edges: edgeSet, info };
  }

  function findPath(srcId, dstId) {
    const all = g?.graphData();
    if (!all) return null;
    return findPathFromData(srcId, dstId, all.nodes, all.links);
  }

  function clearPath() {
    pathStart = null;
    pathEnd = null;
    pathResult = null;
    applyColors();
    if (viewMode === "2d") recolor2D();
    if (pathChainEl) drawPathChain(null);
  }

  // ── 2D view (D3 force + SVG) ──────────────────────────────────
  let sim2d = null;
  let d2NodeSel = null;
  let d2LinkSel = null;

  function init2D() {
    if (!svgEl || !rawGraphData) return;
    if (sim2d) {
      sim2d.stop();
      sim2d = null;
    }

    const { nodes: rawNodes, links: rawLinks } = rawGraphData;
    const nodes = rawNodes.map((n) => ({ ...n }));
    const links = rawLinks.map((l) => ({
      source: l.source,
      target: l.target,
      amount: l.amount,
    }));

    const W = svgEl.clientWidth || 600;
    const H = svgEl.clientHeight || 480;
    svgEl.setAttribute("viewBox", `0 0 ${W} ${H}`);

    const sel = d3.select(svgEl);
    sel.selectAll("*").remove();

    const root = sel.append("g");
    const zoom = d3
      .zoom()
      .scaleExtent([0.05, 8])
      .on("zoom", (e) => root.attr("transform", e.transform));
    sel.call(zoom);

    // Links
    d2LinkSel = root
      .append("g")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke-opacity", 0.45)
      .attr("stroke-width", (l) =>
        Math.max(0.3, Math.log1p(l.amount ?? 1) / 3e4),
      );

    // Nodes
    d2NodeSel = root
      .append("g")
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("r", (d) => Math.sqrt(d.val ?? 1) * 2.2 + 3)
      .attr("stroke-width", 1.2)
      .style("cursor", "pointer")
      .on("click", (event, d) => {
        event.stopPropagation();
        dismissHint();
        if (pathMode) {
          if (!pathStart) {
            pathStart = d.id;
          } else if (d.id !== pathStart) {
            if (pathEnd) {
              clearPath();
              pathStart = d.id;
              return;
            }
            pathEnd = d.id;
            pathResult = findPathFromData(pathStart, pathEnd, nodes, links);
            recolor2D();
            if (pathResult) tick().then(() => drawPathChain(pathResult.info));
          }
        } else {
          openNode(d.id);
        }
      });

    // Node name tooltips (title)
    d2NodeSel.append("title").text((d) => d.name ?? d.id);

    // Labels for manufacturer/hospital nodes
    root
      .append("g")
      .selectAll("text")
      .data(
        nodes.filter(
          (n) =>
            n.node_type === "Manufacturer" ||
            n.node_type === "TeachingHospital",
        ),
      )
      .join("text")
      .attr("font-size", "8px")
      .attr("fill", "rgba(200,212,227,0.6)")
      .attr("font-family", "Inter, sans-serif")
      .attr("pointer-events", "none")
      .attr("text-anchor", "middle")
      .text((d) => (d.name ?? d.id).slice(0, 18))
      .each(function (d) {
        d._labelEl = this;
      });

    const labelSel = root.selectAll("text");

    recolor2D();

    sim2d = d3
      .forceSimulation(nodes)
      .force(
        "link",
        d3
          .forceLink(links)
          .id((d) => d.id)
          .distance(55),
      )
      .force("charge", d3.forceManyBody().strength(-160))
      .force("center", d3.forceCenter(W / 2, H / 2))
      .force(
        "collision",
        d3.forceCollide((d) => Math.sqrt(d.val ?? 1) * 2.2 + 5),
      )
      .alphaDecay(0.018)
      .on("tick", () => {
        d2LinkSel
          .attr("x1", (l) => l.source.x ?? 0)
          .attr("y1", (l) => l.source.y ?? 0)
          .attr("x2", (l) => l.target.x ?? 0)
          .attr("y2", (l) => l.target.y ?? 0);
        d2NodeSel.attr("cx", (d) => d.x ?? 0).attr("cy", (d) => d.y ?? 0);
        labelSel
          .attr("x", (d) => d.x ?? 0)
          .attr("y", (d) => (d.y ?? 0) - (Math.sqrt(d.val ?? 1) * 2.2 + 7));
      });
  }

  function recolor2D() {
    if (!d2NodeSel || !d2LinkSel) return;
    d2NodeSel
      .attr("fill", (d) => nodeColorFn(d))
      .attr("stroke", (d) => {
        if (highlightedNodeId && d.id === highlightedNodeId) return "#FFFFFF";
        return nodeColorFn(d);
      });
    d2LinkSel.attr("stroke", (l) => {
      if (pathResult) {
        const sk = edgeKey(l.source, l.target);
        return pathResult.edges.has(sk) ? "#55EFC4" : "#1A2030";
      }
      return "rgba(200,212,227,0.22)";
    });
  }

  // Switch to 2D: init when SVG is ready
  $effect(() => {
    if (viewMode === "2d" && loaded) {
      tick().then(() => init2D());
    }
    if (viewMode === "3d" && sim2d) {
      sim2d.stop();
      sim2d = null;
      d2NodeSel = null;
      d2LinkSel = null;
    }
  });

  // ── Draw path chain in the dedicated SVG pane ─────────────────
  function drawPathChain(info) {
    if (!pathChainEl) return;
    const W = pathChainEl.clientWidth || 480;
    const H = 120;
    pathChainEl.setAttribute("viewBox", `0 0 ${W} ${H}`);

    const sel = d3.select(pathChainEl);
    sel.selectAll("*").remove();
    if (!info?.length) return;

    const n = info.length;
    const nodeR = 14;
    const stepX = Math.max(48, (W - 40) / Math.max(n - 1, 1));
    const startX = n === 1 ? W / 2 : (W - stepX * (n - 1)) / 2;
    const cy = H / 2;

    const positions = info.map((node, i) => ({
      ...node,
      px: startX + i * stepX,
      py: cy,
    }));

    // Connector lines
    sel
      .append("g")
      .selectAll("line")
      .data(positions.slice(0, -1))
      .join("line")
      .attr("x1", (d) => d.px + nodeR)
      .attr("y1", (d) => d.py)
      .attr("x2", (_d, i) => positions[i + 1].px - nodeR)
      .attr("y2", cy)
      .attr("stroke", "rgba(85,239,196,0.35)")
      .attr("stroke-width", 1.5)
      .attr("stroke-dasharray", "4 3");

    // Node groups
    const typeCol = {
      Manufacturer: "#FF9F43",
      Physician: "#74B9FF",
      TeachingHospital: "#FF6B6B",
    };
    const grp = sel
      .append("g")
      .selectAll("g")
      .data(positions)
      .join("g")
      .attr("transform", (d) => `translate(${d.px},${d.py})`);

    grp
      .append("circle")
      .attr("r", nodeR)
      .attr("fill", (d, i) =>
        i === 0
          ? "#FDCB6E"
          : i === n - 1
            ? "#55EFC4"
            : (typeCol[d.type] ?? "#A29BFE"),
      )
      .attr("fill-opacity", 0.88)
      .attr("stroke", (d, i) =>
        i === 0
          ? "rgba(253,203,110,0.6)"
          : i === n - 1
            ? "rgba(85,239,196,0.6)"
            : "rgba(255,255,255,0.12)",
      )
      .attr("stroke-width", 1.5);

    grp
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dy", "0.35em")
      .attr("font-size", 9)
      .attr("font-weight", "700")
      .attr("fill", "#0D1117")
      .text((_d, i) => i + 1);

    grp
      .append("text")
      .attr("text-anchor", "middle")
      .attr("y", nodeR + 11)
      .attr("font-size", 7.5)
      .attr("fill", "rgba(200,212,227,0.65)")
      .attr("font-family", "Inter, sans-serif")
      .text((d) => (d.name.length > 13 ? d.name.slice(0, 12) + "…" : d.name));
  }

  // ── Helpers ───────────────────────────────────────────────────
  function fmtUSD(n) {
    if (!n) return "$0";
    if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
    if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
    if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
    return `$${(+n).toFixed(0)}`;
  }

  function buildLabel(n) {
    const c = TYPE_COLOR[n.node_type] ?? "#B2BEC3";
    return `<div style="font-family:Inter,sans-serif;background:#161B22;border:1px solid #30363D;border-left:3px solid ${c};border-radius:7px;padding:10px 14px;font-size:11px;line-height:1.7;max-width:220px;box-shadow:0 8px 32px rgba(0,0,0,0.6);pointer-events:none">
      <div style="font-weight:700;color:#E6EDF3;font-size:12px;margin-bottom:2px">${n.name}</div>
      <div style="color:${c};font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;margin-bottom:5px">${n.node_type}</div>
      ${n.state ? `<div style="color:#7D8590;font-size:10px">📍 ${n.state}</div>` : ""}
      <div style="color:#7D8590;font-size:10px">Payments <b style="color:#E6EDF3">${fmtUSD(n.payment)}</b></div>
      ${n.community != null ? `<div style="color:#7D8590;font-size:10px">Community <b style="color:#E6EDF3">C${n.community}</b></div>` : ""}
      <div style="color:#74B9FF;font-size:9px;margin-top:5px">${pathMode ? (pathStart ? "Click to set end →" : "Click to set start →") : "Click to open dossier →"}</div>
    </div>`;
  }

  // ── Camera: fit to a node subset ─────────────────────────────
  function fitCamera(nodes, dur = 900, tight = false) {
    if (!g) return;
    if (!nodes?.length) {
      g.zoomToFit(dur, 40);
      return;
    }
    const v = nodes.filter((n) => n.x != null);
    if (!v.length) {
      setTimeout(() => g.zoomToFit(dur, 40), 200);
      return;
    }

    const cx = v.reduce((s, n) => s + n.x, 0) / v.length;
    const cy = v.reduce((s, n) => s + n.y, 0) / v.length;
    const cz = v.reduce((s, n) => s + n.z, 0) / v.length;
    const maxR = Math.max(
      ...v.map((n) => Math.hypot(n.x - cx, n.y - cy, n.z - cz)),
      1,
    );
    const dist = Math.max(maxR * (tight ? 1.8 : 2.6), tight ? 60 : 100);

    g.cameraPosition(
      { x: cx, y: cy + dist * 0.15, z: cz + dist },
      { x: cx, y: cy, z: cz },
      dur,
    );
    try {
      const ctrl = g.controls();
      const tgt = ctrl.target;
      const sx = tgt.x,
        sy = tgt.y,
        sz = tgt.z;
      const t0 = performance.now();
      function anim() {
        const p = Math.min((performance.now() - t0) / dur, 1);
        const e = 1 - Math.pow(1 - p, 3);
        tgt.set(sx + (cx - sx) * e, sy + (cy - sy) * e, sz + (cz - sz) * e);
        if (p < 1) requestAnimationFrame(anim);
      }
      requestAnimationFrame(anim);
    } catch {}
  }

  // ── Load graph data ───────────────────────────────────────────
  async function loadGraph() {
    if (!containerEl || !g) return;
    loading = true;
    loaded = false;
    error = "";
    pathResult = null;
    try {
      // Community assignments are large (9MB+) — only fetch when needed
      const graphData = await getGraphData($selectedYear, nodeLimit, nodeLimit * 8);
      communityMap = {};
      comColorCache = {};

      const apiNodes = graphData.nodes?.rows ?? [];
      const apiEdges = graphData.edges?.rows ?? [];
      const nodeById = {};
      apiNodes.forEach((r) => {
        nodeById[r.id] = r;
      });

      const stubIds = new Set();
      apiEdges.forEach((e) => {
        if (!nodeById[e.dst_id]) stubIds.add(e.dst_id);
      });
      const stubs = [...stubIds].slice(0, nodeLimit * 2).map((id) => ({
        id,
        name: id,
        node_type: "Physician",
        state: null,
        stub: true,
      }));

      const allNodes = [...apiNodes, ...stubs];
      const nodeIds = new Set(allNodes.map((n) => n.id));
      const validEdges = apiEdges.filter(
        (e) => nodeIds.has(e.src_id) && nodeIds.has(e.dst_id),
      );

      const payMap = {};
      validEdges.forEach((e) => {
        payMap[e.src_id] = (payMap[e.src_id] ?? 0) + (e.total_amount ?? 0);
        payMap[e.dst_id] = (payMap[e.dst_id] ?? 0) + (e.total_amount ?? 0);
      });
      const maxPay = Math.max(1, ...Object.values(payMap));

      const gNodes = allNodes.map((n) => ({
        id: n.id,
        name: n.name ?? n.id,
        node_type: n.node_type ?? "Physician",
        state: n.state ?? null,
        payment: payMap[n.id] ?? 0,
        community:
          communityMap[n.id] != null ? String(communityMap[n.id]) : null,
        val:
          n.node_type === "Manufacturer"
            ? Math.max(
                5,
                5 + (Math.log1p(payMap[n.id] ?? 0) / Math.log1p(maxPay)) * 22,
              )
            : n.node_type === "TeachingHospital"
              ? Math.max(
                  3,
                  3 + (Math.log1p(payMap[n.id] ?? 0) / Math.log1p(maxPay)) * 8,
                )
              : Math.max(
                  1,
                  1 + (Math.log1p(payMap[n.id] ?? 0) / Math.log1p(maxPay)) * 3,
                ),
      }));
      const gLinks = validEdges.map((e) => ({
        source: e.src_id,
        target: e.dst_id,
        amount: e.total_amount ?? 0,
      }));

      nodeCount = gNodes.length;
      edgeCount = gLinks.length;
      rawGraphData = { nodes: gNodes, links: gLinks };
      g.graphData({ nodes: gNodes, links: gLinks });
      loaded = true;

      // Initial camera: fit to all nodes after simulation settles
      // State filter focus is handled by the recolor $effect separately
      setTimeout(() => {
        if (!g) return;
        const all = g.graphData().nodes;
        fitCamera(all, 900, false);
      }, 2000);
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  }

  // ── Mount ─────────────────────────────────────────────────────
  onMount(() => {
    g = ForceGraph3D({ controlType: "orbit" })(containerEl)
      .backgroundColor("#0D1117")
      .showNavInfo(false)
      .nodeLabel(buildLabel)
      .nodeColor(nodeColorFn)
      .nodeVal((n) => n.val ?? 1)
      .nodeOpacity(0.95)
      .nodeResolution(14)
      .nodeThreeObjectExtend(true) // sprite adds ON TOP of sphere
      .linkColor(linkColorFn)
      .linkWidth((link) => Math.max(0.5, Math.log1p(link.amount ?? 1) / 2e4))
      .linkOpacity(0.65)
      .linkDirectionalParticles(3)
      .linkDirectionalParticleWidth(0.9)
      .linkDirectionalParticleSpeed((link) =>
        Math.min(0.003 + Math.log1p(link.amount ?? 0) / 3.5e7, 0.018),
      )
      .linkDirectionalParticleColor(particleColorFn)
      .d3AlphaDecay(0.018)
      .d3VelocityDecay(0.35)
      .onNodeClick((node) => {
        dismissHint();
        if (pathMode) {
          if (!pathStart) {
            pathStart = node.id;
          } else if (node.id !== pathStart) {
            // If we already have a complete path, reset start
            if (pathEnd) {
              clearPath();
              pathStart = node.id;
              return;
            }
            pathEnd = node.id;
            pathResult = findPath(pathStart, pathEnd);
            applyColors();
            if (pathResult) {
              const pathNodes = g
                .graphData()
                .nodes.filter((n) => pathResult.path.includes(n.id));
              setTimeout(() => fitCamera(pathNodes, 700, true), 50);
              // Draw chain in the dedicated SVG pane (tick ensures SVG is rendered)
              tick().then(() => drawPathChain(pathResult.info));
            }
          }
        } else {
          openNode(node.id);
          const { x = 0, y = 0, z = 0 } = node;
          const len = Math.hypot(x, y, z) || 1;
          g.cameraPosition(
            {
              x: (x * (len + 60)) / len,
              y: (y * (len + 60)) / len,
              z: (z * (len + 60)) / len,
            },
            node,
            700,
          );
        }
      })
      .onBackgroundClick(() => dismissHint());

    try {
      g.d3Force("charge").strength(-180);
    } catch {}
    try {
      g.d3Force("center").strength(0.06);
    } catch {}

    if (containerEl)
      g.width(containerEl.clientWidth).height(containerEl.clientHeight);

    try {
      const ctrl = g.controls();
      ctrl.autoRotate = autoRot;
      ctrl.autoRotateSpeed = 0.28; // slower, less dizzying
      ctrl.enableDamping = true;
      ctrl.dampingFactor = 0.1;
      ctrl.minDistance = 30;
      ctrl.maxDistance = 800;

      // Dismiss onboarding hint on first manual interaction
      ctrl.addEventListener("start", () => dismissHint());
      // Stop auto-rotate permanently once user manually orbits
      ctrl.addEventListener("end", () => {
        if (!autoRot) return; // already off
        // only kill it if user actually dragged (not just a click)
        if (ctrl.sphericalDelta?.theta || ctrl.sphericalDelta?.phi) {
          autoRot = false;
          ctrl.autoRotate = false;
        }
      });
    } catch {}

    const ro = new ResizeObserver(() => {
      if (containerEl && g)
        g.width(containerEl.clientWidth).height(containerEl.clientHeight);
    });
    ro.observe(containerEl);
    graphReady = true;

    return () => {
      ro.disconnect();
      try {
        g._destructor?.();
      } catch {}
    };
  });

  // Load only on year change - stateFilter just recolors/refocuses (no data change)
  $effect(() => {
    const _y = $selectedYear;
    if (!graphReady) return;
    loadGraph();
  });

  // Recolor + re-focus + re-label on filter / colorMode / pathMode changes
  $effect(() => {
    if (!loaded) return;
    const f = stateFilter;
    const tf = typeFilter;
    const cm = colorMode; // tracked for reactivity
    const pm = pathMode;
    const hl = highlightedNodeId;

    if (g) {
      g.nodeColor(nodeColorFn);
      g.linkColor(linkColorFn);
      g.linkDirectionalParticleColor(particleColorFn);
    }
    if (viewMode === "2d") recolor2D();

    // Rebuild in-graph text labels
    const labelFn = makeLabelFn(f, tf);
    if (labelFn) {
      g.nodeThreeObject(labelFn).nodeThreeObjectExtend(true);
    } else {
      g.nodeThreeObject(null).nodeThreeObjectExtend(false);
    }

    if (!pm && !pathResult) {
      setTimeout(() => {
        if (!g) return;
        const all = g.graphData().nodes;
        let targets = all;
        if (tf) targets = all.filter((n) => n.node_type === tf);
        else if (f) targets = all.filter((n) => n.state === f);
        fitCamera(targets, 800, !!(f || tf));
      }, 120);
    }
  });

  $effect(() => {
    if (g)
      try {
        g.controls().autoRotate = autoRot;
      } catch {}
  });

  function reCenter() {
    if (!g || !loaded) return;
    const all = g.graphData().nodes;
    let targets = all;
    if (typeFilter) targets = all.filter((n) => n.node_type === typeFilter);
    else if (stateFilter) targets = all.filter((n) => n.state === stateFilter);
    fitCamera(targets, 700, !!(typeFilter || stateFilter));
  }

  // Auto-dismiss hint after 5 s
  $effect(() => {
    if (loaded && showHint) {
      hintTimer = setTimeout(() => {
        showHint = false;
      }, 5000);
      return () => clearTimeout(hintTimer);
    }
  });
</script>

<div class="net-wrap">
  <!-- ── Controls ─────────────────────────────────────────────── -->
  <div class="net-controls">
    <!-- View toggle -->
    <div class="ctrl-group">
      <button
        class="ctrl-btn"
        class:active={viewMode === "3d"}
        onclick={() => (viewMode = "3d")}
        title="3D force graph">⬡ 3D</button
      >
      <button
        class="ctrl-btn"
        class:active={viewMode === "2d"}
        onclick={() => (viewMode = "2d")}
        title="2D force graph">◫ 2D</button
      >
    </div>
    <div class="ctrl-sep"></div>

    <!-- Color mode -->
    <div class="ctrl-group">
      <span class="ctrl-label">COLOR</span>
      <button
        class="ctrl-btn"
        class:active={colorMode === "type"}
        onclick={() => (colorMode = "type")}>Type</button
      >
      <button
        class="ctrl-btn"
        class:active={colorMode === "community"}
        onclick={async () => {
          colorMode = "community";
          if (Object.keys(communityMap).length === 0) {
            const d = await getCommunityAssignments($selectedYear, "bipartite").catch(() => ({ rows: [] }));
            for (const r of d.rows ?? []) {
              const cid = r.community_id ?? r.community ?? r.cid;
              const nid = r.id ?? r.node_id;
              if (nid != null && cid != null) communityMap[nid] = String(cid);
            }
            applyColors();
          }
        }}>Community</button
      >
    </div>
    <div class="ctrl-sep"></div>

    <!-- Node limit -->
    <div class="ctrl-group">
      <span class="ctrl-label">NODES</span>
      <input type="range" min="20" max="150" step="10" bind:value={nodeLimit} />
      <span class="ctrl-val">{nodeLimit}</span>
    </div>
    <div class="ctrl-sep"></div>

    {#if viewMode === "3d"}
      <button
        class="ctrl-btn"
        class:active={autoRot}
        onclick={() => (autoRot = !autoRot)}>↻ Auto</button
      >
      <button class="ctrl-btn" onclick={reCenter} disabled={!loaded}
        >⊙ Center</button
      >
      <div class="ctrl-sep"></div>
    {/if}

    <button
      class="ctrl-btn path-btn"
      class:active={pathMode}
      onclick={() => {
        pathMode = !pathMode;
        clearPath();
      }}
      title="Find shortest path between two nodes">⇢ Path</button
    >

    <button class="reload-btn" onclick={loadGraph} disabled={loading}>
      {loading ? "⟳ …" : "⟳ Reload"}
    </button>
    {#if loaded}
      <span class="stat-pill">{nodeCount}n · {edgeCount}e</span>
    {/if}

    <!-- Node search -->
    <div class="node-search-wrap" style="margin-left:auto">
      <span class="node-search-icon">⌕</span>
      <input
        type="text"
        class="node-search-input"
        placeholder={pathMode ? "Search to set path node…" : "Find node…"}
        bind:value={nodeQuery}
        oninput={onNodeQueryInput}
        onkeydown={(e) => {
          if (e.key === "Escape") {
            nodeQuery = "";
            nodeResults = [];
            nodeSearchOpen = false;
          }
        }}
        onblur={() =>
          setTimeout(() => {
            nodeSearchOpen = false;
          }, 180)}
      />
      {#if nodeSearchOpen && nodeResults.length}
        <div class="node-search-drop" role="listbox">
          {#each nodeResults as r}
            {@const col =
              {
                Physician: "#74B9FF",
                Manufacturer: "#FF9F43",
                TeachingHospital: "#FF6B6B",
              }[r.node_type] ?? "#888"}
            <!-- svelte-ignore a11y_interactive_supports_focus -->
            <div
              class="node-search-result"
              role="option"
              aria-selected="false"
              onmousedown={() => pickSearchNode(r)}
            >
              <span class="nsr-dot" style="background:{col}"></span>
              <span class="nsr-name">{r.name ?? r.id}</span>
              <span class="nsr-type" style="color:{col}">{r.node_type}</span>
              <span class="nsr-state">{r.state ?? ""}</span>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>

  <!-- ── Graph area ─────────────────────────────────────────────── -->
  <div class="graph-area">
    <!-- 2D SVG view -->
    {#if viewMode === "2d" && loaded}
      <div class="canvas-wrap canvas-2d">
        <svg
          bind:this={svgEl}
          class="svg-2d"
          style="background:#0D1117;width:100%;height:100%"
        ></svg>
        {#if stateFilter && !pathMode}
          <div class="state-pill">
            <span class="state-pill-dot"></span>Focused:
            <strong>{stateFilter}</strong>
          </div>
        {/if}
        {#if pathMode}
          <div class="path-banner">
            {#if !pathStart}Click a node or search to set <strong>start</strong>
            {:else if !pathEnd}<span class="path-node" style="color:#FDCB6E"
                >Start set</span
              >
              · click or search for <strong>end</strong>
            {:else}Path: <strong
                >{pathResult
                  ? pathResult.path.length + " hops"
                  : "No connection"}</strong
              ><button class="path-clear" onclick={clearPath}>✕</button>{/if}
          </div>
        {/if}
        <div class="ctrl-legend ctrl-legend--net">
          <div class="ctrl-legend-row">
            <kbd class="ctrl-legend-key">Drag</kbd><span>Pan</span>
          </div>
          <div class="ctrl-legend-row">
            <kbd class="ctrl-legend-key">Scroll</kbd><span>Zoom</span>
          </div>
          <div class="ctrl-legend-row">
            <kbd class="ctrl-legend-key">Click</kbd><span>Node dossier</span>
          </div>
        </div>
      </div>
    {/if}

    <!-- 3D canvas (always mounted so ForceGraph3D keeps its state; hidden in 2D mode) -->
    <div
      class="canvas-wrap"
      style={viewMode === "2d" ? "display:none" : ""}
      bind:this={containerEl}
    >
      {#if loading}
        <div class="overlay-center">
          <div class="spinner"></div>
          <span>Building 3D network…</span>
        </div>
      {:else if error}
        <div class="overlay-center"><span class="error-msg">{error}</span></div>
      {:else if !loaded}
        <div
          class="overlay-center"
          style="flex-direction:column;gap:16px;text-align:center"
        >
          <svg
            width="52"
            height="52"
            viewBox="0 0 60 60"
            fill="none"
            opacity=".25"
          >
            <circle cx="30" cy="30" r="5.5" fill="#FF9F43" />
            <circle cx="9" cy="16" r="3" fill="#FF9F43" />
            <circle cx="51" cy="16" r="3" fill="#FF9F43" />
            <circle cx="9" cy="44" r="2" fill="#74B9FF" />
            <circle cx="30" cy="7" r="2" fill="#74B9FF" />
            <circle cx="51" cy="44" r="2" fill="#FF6B6B" />
            <line
              x1="30"
              y1="25"
              x2="9"
              y2="16"
              stroke="#3D444D"
              stroke-width="1.2"
            />
            <line
              x1="30"
              y1="25"
              x2="51"
              y2="16"
              stroke="#3D444D"
              stroke-width="1.2"
            />
            <line
              x1="30"
              y1="35"
              x2="9"
              y2="44"
              stroke="#3D444D"
              stroke-width="1.2"
            />
            <line
              x1="30"
              y1="35"
              x2="51"
              y2="44"
              stroke="#3D444D"
              stroke-width="1.2"
            />
            <line
              x1="30"
              y1="25"
              x2="30"
              y2="7"
              stroke="#3D444D"
              stroke-width="1.2"
            />
          </svg>
          <div>
            <div
              style="font-weight:600;color:var(--color-heading);margin-bottom:4px"
            >
              3D Pharma Payment Network
            </div>
            <div
              style="font-size:11px;color:var(--color-muted);line-height:1.6"
            >
              Force-directed · Particles show payment flow<br />
              Click a state on the map to filter
            </div>
          </div>
          <button class="reload-btn" onclick={loadGraph}>Load Graph</button>
        </div>
      {:else}
        {#if stateFilter && !pathMode}
          <div class="state-pill">
            <span class="state-pill-dot"></span>
            Focused: <strong>{stateFilter}</strong>
            <span class="state-pill-hint">· click map to change</span>
          </div>
        {/if}
        {#if pathMode}
          <div class="path-banner">
            {#if !pathStart}
              Click a node to set <strong>start</strong>
            {:else if !pathEnd}
              <span class="path-node" style="color:#FDCB6E">Start set</span>
              · now click the <strong>end</strong> node
            {:else}
              Path found: <strong
                >{pathResult
                  ? pathResult.path.length + " hops"
                  : "No path"}</strong
              >
              <button class="path-clear" onclick={clearPath}>✕ Clear</button>
            {/if}
          </div>
        {/if}
      {/if}

      <!-- ── Onboarding hint overlay ───────────────────────────── -->
      {#if showHint && loaded}
        <div class="nav-hint" onclick={dismissHint}>
          <div class="nav-hint-row">
            <span class="nav-hint-key">Drag</span><span>Orbit the graph</span>
          </div>
          <div class="nav-hint-row">
            <span class="nav-hint-key">Scroll</span><span>Zoom in / out</span>
          </div>
          <div class="nav-hint-row">
            <span class="nav-hint-key">Click node</span><span>Open dossier</span
            >
          </div>
          <div class="nav-hint-dismiss">Click anywhere to dismiss</div>
        </div>
      {/if}
    </div>

    <!-- ── Shortest path side panel ──────────────────────────────── -->
    {#if pathMode}
      <div class="path-panel">
        <div class="path-panel-title">
          {#if !pathStart}
            <span
              style="color:var(--color-muted);font-weight:500;font-size:11px"
              >Click a node to set start</span
            >
          {:else if !pathEnd}
            <span style="color:#FDCB6E">Start set</span>
            <span
              style="color:var(--color-muted);font-size:10px;font-weight:400"
            >
              · click end node</span
            >
          {:else}
            Shortest Path
            <span class="path-hops"
              >{pathResult
                ? pathResult.path.length - 1 + " hops"
                : "No path"}</span
            >
          {/if}
          <button class="path-clear" onclick={clearPath} title="Reset path"
            >✕</button
          >
        </div>

        {#if pathResult}
          <!-- Chain viz -->
          <div class="path-chain-wrap">
            <svg bind:this={pathChainEl} class="path-chain-svg"></svg>
          </div>

          <!-- Node list -->
          <div class="path-list">
            {#each pathResult.info as node, i}
              <div
                class="path-node-row"
                class:path-start={i === 0}
                class:path-end={i === pathResult.info.length - 1}
              >
                <div class="path-step">
                  <span
                    class="path-idx"
                    style="background:{i === 0
                      ? 'rgba(253,203,110,.18)'
                      : i === pathResult.info.length - 1
                        ? 'rgba(85,239,196,.18)'
                        : ''}; color:{i === 0
                      ? '#FDCB6E'
                      : i === pathResult.info.length - 1
                        ? '#55EFC4'
                        : 'var(--color-muted)'}">{i + 1}</span
                  >
                  {#if i < pathResult.info.length - 1}
                    <span class="path-connector"></span>
                  {/if}
                </div>
                <div class="path-info">
                  <div class="path-name">{node.name.slice(0, 28)}</div>
                  <div class="path-meta">
                    <span
                      class="path-type"
                      style="color:{TYPE_COLOR[node.type] ?? '#888'}"
                      >{node.type}</span
                    >
                    {#if node.state !== "-"}<span class="path-state"
                        >· {node.state}</span
                      >{/if}
                  </div>
                  <div class="path-pay">{fmtUSD(node.payment)}</div>
                </div>
              </div>
            {/each}
          </div>
          <div class="path-hint">
            {pathResult.path.length - 1} payment hop{pathResult.path.length > 2
              ? "s"
              : ""} between these entities
          </div>
        {:else if pathEnd}
          <!-- No path found -->
          <div class="path-no-result">
            <div class="path-no-icon">⊘</div>
            <div class="path-no-text">No path found in visible subgraph</div>
            <div class="path-no-sub">
              Try increasing the node limit or reload with more data
            </div>
          </div>
        {/if}
      </div>
    {/if}
  </div>

  <!-- ── Legend (clickable type filter) ───────────────────────── -->
  {#if loaded && colorMode === "type"}
    <div class="legend">
      {#each [["Manufacturer", "#FF9F43"], ["Physician", "#74B9FF"], ["Hospital", "#FF6B6B", "TeachingHospital"]] as [label, color, typeKey]}
        {@const key = typeKey ?? label}
        <button
          class="legend-btn"
          class:legend-active={typeFilter === key}
          onclick={() => (typeFilter = typeFilter === key ? null : key)}
          title="Click to show only {label}s"
        >
          <span
            class="legend-dot"
            style="background:{color};{typeFilter === key
              ? `box-shadow:0 0 6px ${color}`
              : ''}"
          ></span>
          <span>{label}</span>
        </button>
      {/each}
      <div class="legend-particle">
        <span class="particle-dot"></span>
        Payment flow →
      </div>
    </div>
  {/if}

  <!-- ── Controls legend ───────────────────────────────────────── -->
  {#if pathMode}
    <div class="path-mode-bar">
      Path mode - click two nodes to find shortest connection · Press Path
      button to exit
    </div>
  {:else}
    <div class="ctrl-legend ctrl-legend--net">
      <div class="ctrl-legend-row">
        <kbd class="ctrl-legend-key">Drag</kbd><span>Orbit</span>
      </div>
      <div class="ctrl-legend-row">
        <kbd class="ctrl-legend-key">Scroll</kbd><span>Zoom</span>
      </div>
      <div class="ctrl-legend-row">
        <kbd class="ctrl-legend-key">Click</kbd><span>Node dossier</span>
      </div>
    </div>
  {/if}
</div>

<style>
  .net-wrap {
    display: flex;
    flex-direction: column;
    height: 100%;
    position: relative;
    background: #0d1117;
    overflow: hidden;
  }

  /* Controls */
  .net-controls {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    padding: 6px 12px;
    background: #161b22;
    border-bottom: 1px solid var(--color-border);
    flex-shrink: 0;
    font-family: var(--font-sans);
  }
  .ctrl-title {
    font-size: 10px;
    font-weight: 700;
    color: var(--color-muted);
    letter-spacing: 0.8px;
    text-transform: uppercase;
    flex-shrink: 0;
  }
  .ctrl-sep {
    width: 1px;
    height: 16px;
    background: var(--color-border);
    margin: 0 3px;
    flex-shrink: 0;
  }
  .ctrl-group {
    display: flex;
    align-items: center;
    gap: 3px;
  }
  .ctrl-label {
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.8px;
    color: var(--color-subtle);
    margin-right: 3px;
    text-transform: uppercase;
  }
  .ctrl-btn {
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
    color: var(--color-muted);
    background: transparent;
    border: 1px solid transparent;
    cursor: pointer;
    transition: all 0.1s;
    font-family: var(--font-sans);
    white-space: nowrap;
  }
  .ctrl-btn:hover {
    color: var(--color-text);
    background: var(--color-hover);
  }
  .ctrl-btn.active {
    color: var(--color-accent);
    background: var(--color-accent-dim);
    border-color: rgba(47, 129, 247, 0.3);
    font-weight: 600;
  }
  .ctrl-val {
    font-size: 10px;
    color: var(--color-muted);
    min-width: 28px;
    font-family: var(--font-mono);
  }
  .reload-btn {
    padding: 4px 12px;
    border-radius: 5px;
    font-size: 11px;
    font-weight: 600;
    color: var(--color-accent);
    background: var(--color-accent-dim);
    border: 1px solid rgba(47, 129, 247, 0.3);
    cursor: pointer;
    transition: background 0.12s;
    font-family: var(--font-sans);
    margin-left: 2px;
  }
  .reload-btn:hover {
    background: rgba(47, 129, 247, 0.18);
  }
  .reload-btn:disabled {
    opacity: 0.35;
    cursor: default;
  }
  .stat-pill {
    font-size: 10px;
    color: var(--color-muted);
    font-family: var(--font-mono);
  }

  /* Graph area: row layout for side panel */
  .graph-area {
    flex: 1;
    display: flex;
    min-height: 0;
    overflow: hidden;
  }

  .canvas-wrap {
    flex: 1;
    position: relative;
    overflow: hidden;
    background: #0d1117;
    min-height: 0;
  }
  .canvas-wrap :global(canvas) {
    display: block !important;
  }

  /* Overlays */
  .overlay-center {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    color: var(--color-muted);
    font-size: 13px;
    font-family: var(--font-sans);
    z-index: 10;
    pointer-events: none;
  }
  .overlay-center button {
    pointer-events: all;
  }

  /* State filter pill */
  .state-pill {
    position: absolute;
    top: 12px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(22, 27, 34, 0.94);
    border: 1px solid rgba(116, 185, 255, 0.35);
    border-radius: 999px;
    padding: 5px 14px;
    font-size: 11px;
    font-family: var(--font-sans);
    color: var(--color-text);
    white-space: nowrap;
    z-index: 10;
    pointer-events: none;
    backdrop-filter: blur(4px);
  }
  .state-pill strong {
    color: #74b9ff;
  }
  .state-pill-hint {
    color: var(--color-subtle);
    font-size: 10px;
  }
  .state-pill-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #74b9ff;
    flex-shrink: 0;
    box-shadow: 0 0 6px #74b9ff;
  }

  /* Path mode banner */
  .path-banner {
    position: absolute;
    top: 12px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(22, 27, 34, 0.94);
    border: 1px solid rgba(253, 203, 110, 0.4);
    border-radius: 999px;
    padding: 5px 16px;
    font-size: 11px;
    font-family: var(--font-sans);
    color: var(--color-text);
    white-space: nowrap;
    z-index: 10;
    backdrop-filter: blur(4px);
  }
  .path-banner strong {
    color: #fdcb6e;
  }
  .path-node {
    font-weight: 700;
  }
  .path-clear {
    background: none;
    border: none;
    color: var(--color-muted);
    cursor: pointer;
    padding: 0 4px;
    font-size: 12px;
    line-height: 1;
    transition: color 0.1s;
  }
  .path-clear:hover {
    color: var(--color-danger);
  }

  /* Shortest path side panel */
  .path-panel {
    width: 220px;
    flex-shrink: 0;
    background: #161b22;
    border-left: 1px solid var(--color-border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    font-family: var(--font-sans);
  }
  .path-panel-title {
    padding: 8px 10px 8px 12px;
    font-size: 11px;
    font-weight: 700;
    color: var(--color-heading);
    border-bottom: 1px solid var(--color-border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
    flex-shrink: 0;
    min-height: 36px;
  }
  .path-hops {
    font-size: 10px;
    font-weight: 600;
    color: #55efc4;
    background: rgba(85, 239, 196, 0.12);
    border: 1px solid rgba(85, 239, 196, 0.25);
    border-radius: 4px;
    padding: 1px 7px;
  }
  .path-list {
    flex: 1;
    overflow-y: auto;
    padding: 6px 0;
  }
  .path-node-row {
    display: flex;
    gap: 8px;
    padding: 6px 12px;
    border-bottom: 1px solid rgba(48, 54, 61, 0.5);
  }
  .path-node-row:last-child {
    border-bottom: none;
  }
  .path-node-row.path-start {
    background: rgba(253, 203, 110, 0.06);
  }
  .path-node-row.path-end {
    background: rgba(85, 239, 196, 0.06);
  }
  .path-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0;
    flex-shrink: 0;
  }
  .path-idx {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--color-card-2);
    border: 1px solid var(--color-border);
    font-size: 9px;
    font-weight: 700;
    color: var(--color-muted);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .path-connector {
    flex: 1;
    width: 1px;
    background: var(--color-border);
    min-height: 6px;
    margin: 2px 0;
  }
  .path-info {
    flex: 1;
    min-width: 0;
  }
  .path-name {
    font-size: 11px;
    font-weight: 600;
    color: var(--color-heading);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .path-meta {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-top: 1px;
  }
  .path-type {
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.4px;
  }
  .path-state {
    font-size: 9px;
    color: var(--color-muted);
  }
  .path-pay {
    font-size: 10px;
    color: var(--color-muted);
    font-family: var(--font-mono);
    margin-top: 1px;
  }
  .path-hint {
    padding: 8px 12px;
    font-size: 10px;
    color: var(--color-muted);
    border-top: 1px solid var(--color-border);
    line-height: 1.5;
    flex-shrink: 0;
  }

  /* Path chain SVG pane */
  .path-chain-wrap {
    border-bottom: 1px solid var(--color-border);
    background: rgba(13, 17, 23, 0.6);
    flex-shrink: 0;
    padding: 4px 0;
  }
  .path-chain-svg {
    display: block;
    width: 100%;
    height: 120px;
  }

  /* No path found state */
  .path-no-result {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 24px 16px;
    text-align: center;
  }
  .path-no-icon {
    font-size: 28px;
    opacity: 0.25;
  }
  .path-no-text {
    font-size: 12px;
    font-weight: 600;
    color: var(--color-muted);
  }
  .path-no-sub {
    font-size: 10px;
    color: var(--color-subtle);
    line-height: 1.5;
  }

  /* Onboarding nav hint */
  .nav-hint {
    position: absolute;
    bottom: 44px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(13, 17, 23, 0.92);
    border: 1px solid var(--color-border);
    border-radius: 10px;
    padding: 10px 16px;
    display: flex;
    flex-direction: column;
    gap: 5px;
    z-index: 30;
    cursor: pointer;
    backdrop-filter: blur(8px);
    animation: hint-fade-in 0.4s ease;
  }
  @keyframes hint-fade-in {
    from {
      opacity: 0;
      transform: translateX(-50%) translateY(8px);
    }
    to {
      opacity: 1;
      transform: translateX(-50%) translateY(0);
    }
  }
  .nav-hint-row {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 11px;
    color: var(--color-muted);
    font-family: var(--font-sans);
  }
  .nav-hint-key {
    font-size: 9px;
    font-weight: 700;
    background: var(--color-hover);
    border: 1px solid var(--color-border);
    border-radius: 4px;
    padding: 2px 7px;
    color: var(--color-text);
    min-width: 60px;
    text-align: center;
    flex-shrink: 0;
  }
  .nav-hint-dismiss {
    font-size: 9px;
    color: var(--color-subtle);
    text-align: center;
    margin-top: 4px;
  }

  /* Path btn variant */
  .path-btn.active {
    color: #fdcb6e;
    background: rgba(253, 203, 110, 0.1);
    border-color: rgba(253, 203, 110, 0.3);
  }

  /* Legend */
  .legend {
    position: absolute;
    bottom: 28px;
    left: 10px;
    display: flex;
    flex-direction: column;
    gap: 3px;
    background: rgba(22, 27, 34, 0.9);
    padding: 8px 10px;
    border-radius: 7px;
    border: 1px solid var(--color-border);
    z-index: 10;
    backdrop-filter: blur(4px);
  }
  .legend-btn {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 10px;
    color: var(--color-text);
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 3px 6px;
    cursor: pointer;
    font-family: var(--font-sans);
    transition: all 0.12s;
    text-align: left;
    white-space: nowrap;
  }
  .legend-btn:hover {
    background: var(--color-hover);
    color: var(--color-heading);
  }
  .legend-btn.legend-active {
    background: var(--color-hover);
    border-color: var(--color-border);
    color: var(--color-heading);
    font-weight: 600;
  }
  .legend-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .legend-particle {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 10px;
    color: var(--color-muted);
    font-family: var(--font-sans);
    margin-top: 3px;
    padding-top: 5px;
    border-top: 1px solid var(--color-border);
  }
  .particle-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #ff9f43;
    flex-shrink: 0;
    box-shadow: 0 0 5px rgba(255, 159, 67, 0.7);
  }

  /* Hint bar */
  .path-mode-bar {
    padding: 4px 12px;
    background: rgba(245, 158, 11, 0.08);
    border-top: 1px solid rgba(245, 158, 11, 0.2);
    font-size: 10px;
    color: var(--color-accent-2, #f59e0b);
    flex-shrink: 0;
    font-family: var(--font-sans);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .ctrl-legend--net {
    position: absolute;
    bottom: 12px;
    right: 12px;
    z-index: 20;
  }

  input[type="range"] {
    width: 70px;
    accent-color: var(--color-accent);
    cursor: pointer;
  }

  /* 2D canvas */
  .canvas-2d {
    background: #0d1117;
  }
  .svg-2d {
    display: block;
  }

  /* Node search */
  .node-search-wrap {
    position: relative;
    display: flex;
    align-items: center;
    flex-shrink: 0;
  }
  .node-search-icon {
    position: absolute;
    left: 8px;
    font-size: 13px;
    color: var(--color-muted);
    pointer-events: none;
    line-height: 1;
  }
  .node-search-input {
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: 6px;
    padding: 4px 10px 4px 26px;
    font-size: 11px;
    color: var(--color-text);
    width: 180px;
    outline: none;
    font-family: var(--font-sans);
    transition:
      border-color 0.15s,
      width 0.2s;
  }
  .node-search-input::placeholder {
    color: var(--color-subtle);
  }
  .node-search-input:focus {
    border-color: var(--color-accent);
    box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.12);
    width: 220px;
  }
  .node-search-drop {
    position: absolute;
    top: calc(100% + 4px);
    right: 0;
    min-width: 260px;
    background: var(--color-card-2);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.6);
    z-index: 200;
    overflow: hidden;
    animation: slide-in-bottom 0.13s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .node-search-result {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 8px 12px;
    cursor: pointer;
    border-bottom: 1px solid var(--color-border);
    font-family: var(--font-sans);
    transition: background 0.1s;
  }
  .node-search-result:last-child {
    border-bottom: none;
  }
  .node-search-result:hover {
    background: var(--color-hover);
  }
  .nsr-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .nsr-name {
    flex: 1;
    font-size: 11px;
    font-weight: 500;
    color: var(--color-heading);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .nsr-type {
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    flex-shrink: 0;
  }
  .nsr-state {
    font-size: 9px;
    color: var(--color-muted);
    background: var(--color-hover);
    padding: 1px 5px;
    border-radius: 3px;
    flex-shrink: 0;
  }
</style>
