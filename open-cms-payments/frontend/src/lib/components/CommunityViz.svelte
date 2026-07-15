<script>
  /**
   * CommunityViz - pre-computed UMAP embedding visualization.
   * • 2D mode: Plotly scatter with convex-hull cluster overlays
   * • 3D mode: Three.js instanced-mesh scatter, orbit controls
   */
  import * as THREE from "three";
  import { onMount } from "svelte";
  import { selectedYear, openNode } from "../stores.js";
  import { getCommunityEmbeddings } from "../api.js";
  import PlotlyChart from "./PlotlyChart.svelte";

  let { showAll = true } = $props();

  // ── View mode ─────────────────────────────────────────────────
  let viewMode = $state("3d");
  let colorBy = $state("community");

  // ── Filter state ──────────────────────────────────────────────
  let typeFilter = $state(null); // null | 'Physician' | 'Manufacturer' | 'TeachingHospital'
  let stateFilter = $state(""); // '' or 2-letter state abbrev
  let minComm = $state(0); // show communities C{minComm}+
  let maxComm = $state(19); // show communities up to C{maxComm}

  // Filtered dataset (derived from raw data + filter settings)
  function applyFilters(rows) {
    if (!rows) return [];
    return rows.filter((r) => {
      if (typeFilter && r.node_type !== typeFilter) return false;
      if (stateFilter && r.state !== stateFilter) return false;
      const cid = r.community_id ?? -1;
      if (cid >= 0 && (cid < minComm || cid > maxComm)) return false;
      return true;
    });
  }

  // ── Data ──────────────────────────────────────────────────────
  let data2d = $state(null);
  let data3d = $state(null);
  let loading = $state(false);
  let error = $state("");

  // ── Three.js refs ─────────────────────────────────────────────
  let threeEl = $state(null);
  let renderer, scene, camera, animId;
  let isDragging = false,
    lastX = 0,
    lastY = 0;
  let spherical = { theta: 0.4, phi: 0.9, r: 8 };
  let tooltip3 = $state({ x: 0, y: 0, node: null });

  // ── Color palettes ────────────────────────────────────────────
  const COM_PALETTE = [
    "#58A6FF",
    "#FF9F43",
    "#FF6B6B",
    "#55EFC4",
    "#A29BFE",
    "#FDCB6E",
    "#81ECEC",
    "#FD79A8",
    "#00B894",
    "#FAB1A0",
    "#74B9FF",
    "#FFEAA7",
    "#E056C1",
    "#F0A500",
    "#00CEC9",
    "#E17055",
    "#6C5CE7",
    "#C7ECEE",
    "#B2BEC3",
    "#636E72",
  ];
  const TYPE_COLOR = {
    Physician: "#58A6FF",
    Manufacturer: "#FF9F43",
    TeachingHospital: "#FF6B6B",
  };

  function commColor(cid) {
    if (cid < 0) return "#484F58"; // unassigned nodes
    return COM_PALETTE[cid % COM_PALETTE.length];
  }

  // ── Convex hull (Graham scan) ─────────────────────────────────
  function convexHull(pts) {
    if (pts.length < 3) return pts;
    const sorted = [...pts].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    const cross = (o, a, b) =>
      (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
    const lower = [];
    for (const p of sorted) {
      while (
        lower.length >= 2 &&
        cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0
      )
        lower.pop();
      lower.push(p);
    }
    const upper = [];
    for (const p of [...sorted].reverse()) {
      while (
        upper.length >= 2 &&
        cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0
      )
        upper.pop();
      upper.push(p);
    }
    upper.pop();
    lower.pop();
    return [...lower, ...upper];
  }

  // Expand hull outward from centroid by `pad` units
  function expandHull(hull, pad = 0.4) {
    const cx = hull.reduce((s, p) => s + p[0], 0) / hull.length;
    const cy = hull.reduce((s, p) => s + p[1], 0) / hull.length;
    return hull.map(([x, y]) => {
      const len = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2) || 0.001;
      return [x + ((x - cx) / len) * pad, y + ((y - cy) / len) * pad];
    });
  }

  // Convert hex color to rgba string
  function hexRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }

  // Sample array for hull calculation (avoid O(n²) on huge communities)
  function samplePts(pts, max = 500) {
    if (pts.length <= max) return pts;
    const step = pts.length / max;
    return Array.from({ length: max }, (_, i) => pts[Math.floor(i * step)]);
  }

  // ── Fetch data ────────────────────────────────────────────────
  async function fetchData() {
    loading = true;
    error = "";
    try {
      const [r2, r3] = await Promise.all([
        getCommunityEmbeddings($selectedYear, 2, 5000),
        getCommunityEmbeddings($selectedYear, 3, 5000),
      ]);
      const valid2 = (r2?.rows ?? []).filter(
        (r) => r.umap_x != null && r.umap_y != null,
      );
      const valid3 = (r3?.rows ?? []).filter(
        (r) => r.umap_x != null && r.umap_y != null,
      );
      data2d = valid2;
      data3d = valid3;
    } catch (e) {
      error = `Embeddings not available: ${e.message}. Run analytics/precompute_embeddings.py first.`;
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    const _y = $selectedYear;
    fetchData();
  });

  // Rebuild 3D when data, DOM, or filters change
  $effect(() => {
    const _tf = typeFilter;
    const _sf = stateFilter;
    const _cb = colorBy;
    if (viewMode === "3d" && threeEl && data3d && data3d.length > 0) {
      buildThree();
    }
  });

  $effect(() => {
    return () => {
      cancelAnimationFrame(animId);
      renderer?.dispose();
    };
  });

  // ── 2D Plotly traces ──────────────────────────────────────────
  function build2dTraces(rows) {
    if (!rows || rows.length === 0) return [];

    if (colorBy === "community") {
      const groups = {};
      rows.forEach((r) => {
        const cid = r.community_id ?? -1;
        if (!groups[cid]) groups[cid] = [];
        groups[cid].push(r);
      });

      const hullTraces = [];
      const ptTraces = [];

      // Sort communities so C0 (largest) renders first
      const cidsSorted = Object.keys(groups).sort((a, b) => +a - +b);

      for (const cid of cidsSorted) {
        const pts = groups[cid];
        const col = commColor(+cid);
        const label = +cid < 0 ? "Unassigned" : `C${cid}`;

        // Hull overlay (only for communities with 3+ points)
        if (pts.length >= 3) {
          const rawPts = samplePts(pts.map((r) => [r.umap_x, r.umap_y]));
          const hull = expandHull(convexHull(rawPts));
          if (hull.length >= 3) {
            hullTraces.push({
              type: "scatter",
              mode: "lines",
              name: label,
              showlegend: false,
              hoverinfo: "skip",
              x: [...hull.map((p) => p[0]), hull[0][0]],
              y: [...hull.map((p) => p[1]), hull[0][1]],
              fill: "toself",
              fillcolor: hexRgba(col, 0.07),
              line: { color: hexRgba(col, 0.28), width: 1 },
            });
          }
        }

        // Scatter points
        ptTraces.push({
          type: "scatter",
          mode: "markers",
          name: label,
          x: pts.map((r) => r.umap_x),
          y: pts.map((r) => r.umap_y),
          customdata: pts.map((r) => r.id),
          text: pts.map((r) => r.name ?? r.id ?? ""),
          marker: {
            color: col,
            size: pts.map((r) => (r.node_type === "Manufacturer" ? 9 : 5)),
            opacity: 0.82,
            line: { color: "rgba(0,0,0,0.25)", width: 0.5 },
          },
          hovertemplate:
            "<b>%{text}</b><br>" +
            `Community: ${label}<br>` +
            "Click to open dossier<extra></extra>",
        });
      }

      // Hull traces render first (behind points)
      return [...hullTraces, ...ptTraces];
    }

    if (colorBy === "type") {
      const groups = { Physician: [], Manufacturer: [], TeachingHospital: [] };
      rows.forEach((r) => {
        const t = r.node_type ?? "Physician";
        if (!groups[t]) groups[t] = [];
        groups[t].push(r);
      });
      return Object.entries(groups).map(([type, pts]) => ({
        type: "scatter",
        mode: "markers",
        name: type,
        x: pts.map((r) => r.umap_x),
        y: pts.map((r) => r.umap_y),
        customdata: pts.map((r) => r.id),
        text: pts.map((r) => r.name ?? r.id ?? ""),
        marker: {
          color: TYPE_COLOR[type] ?? "#B2BEC3",
          size: type === "Manufacturer" ? 9 : 5,
          opacity: 0.8,
          line: { color: "rgba(0,0,0,0.2)", width: 0.4 },
        },
        hovertemplate: "<b>%{text}</b><br>Type: " + type + "<extra></extra>",
      }));
    }

    if (colorBy === "risk") {
      return [
        {
          type: "scatter",
          mode: "markers",
          name: "Entities",
          x: rows.map((r) => r.umap_x),
          y: rows.map((r) => r.umap_y),
          customdata: rows.map((r) => r.id),
          text: rows.map((r) => r.name ?? r.id ?? ""),
          marker: {
            color: rows.map((r) => r.cash_ratio ?? 0),
            colorscale: [
              [0, "#58A6FF"],
              [0.5, "#FDCB6E"],
              [1, "#FF6B6B"],
            ],
            size: 5,
            opacity: 0.8,
            showscale: true,
            colorbar: {
              title: {
                text: "Cash Ratio",
                font: { color: "#7D8590", size: 9 },
              },
              thickness: 10,
              tickfont: { color: "#7D8590", size: 9 },
              bgcolor: "rgba(0,0,0,0)",
              bordercolor: "#30363D",
            },
          },
          hovertemplate:
            "<b>%{text}</b><br>Cash ratio: %{marker.color:.2f}<extra></extra>",
        },
      ];
    }

    // payments
    return [
      {
        type: "scatter",
        mode: "markers",
        name: "Entities",
        x: rows.map((r) => r.umap_x),
        y: rows.map((r) => r.umap_y),
        customdata: rows.map((r) => r.id),
        text: rows.map((r) => r.name ?? r.id ?? ""),
        marker: {
          color: rows.map((r) => Math.log1p(r.in_strength ?? 0)),
          colorscale: [
            [0, "#161B22"],
            [0.4, "#2F81F7"],
            [0.7, "#58A6FF"],
            [1, "#55EFC4"],
          ],
          size: rows.map((r) =>
            Math.max(3, Math.min(13, 3 + Math.log1p(r.in_strength ?? 0) * 0.6)),
          ),
          opacity: 0.82,
          showscale: true,
          colorbar: {
            title: {
              text: "log(Payments)",
              font: { color: "#7D8590", size: 9 },
            },
            thickness: 10,
            tickfont: { color: "#7D8590", size: 9 },
            bgcolor: "rgba(0,0,0,0)",
            bordercolor: "#30363D",
          },
        },
        hovertemplate:
          "<b>%{text}</b><br>Payments: $%{customdata:.0f}<extra></extra>",
      },
    ];
  }

  const layout2d = {
    margin: { t: 16, r: 100, b: 48, l: 50 },
    xaxis: {
      title: { text: "UMAP-1", font: { color: "#7D8590", size: 10 } },
      tickfont: { size: 9, color: "#7D8590" },
      gridcolor: "#21262D",
      zeroline: false,
    },
    yaxis: {
      title: { text: "UMAP-2", font: { color: "#7D8590", size: 10 } },
      tickfont: { size: 9, color: "#7D8590" },
      gridcolor: "#21262D",
      zeroline: false,
    },
    legend: {
      font: { size: 9, color: "#C9D1D9" },
      orientation: "v",
      x: 1.01,
      y: 1,
      bgcolor: "rgba(13,17,23,0.7)",
      bordercolor: "#30363D",
      borderwidth: 1,
    },
    hovermode: "closest",
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
  };

  const config2d = {
    scrollZoom: true,
    displayModeBar: false,
    responsive: true,
  };

  // ── Three.js 3D scatter ───────────────────────────────────────
  function buildThree() {
    if (!threeEl) return;
    cancelAnimationFrame(animId);
    if (renderer) {
      renderer.dispose();
      threeEl.innerHTML = "";
    }

    const rows = applyFilters(data3d ?? []);
    if (rows.length === 0) return;

    const W = threeEl.clientWidth || 600;
    const H = threeEl.clientHeight || 500;

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0d1117);

    camera = new THREE.PerspectiveCamera(55, W / H, 0.1, 1000);
    camera.position.set(8, 5, 8);
    camera.lookAt(0, 0, 0);

    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    threeEl.appendChild(renderer.domElement);

    // Grid helper (no lighting needed - PointsMaterial is unlit)
    scene.add(new THREE.GridHelper(12, 20, 0x21262d, 0x161b22));

    // Normalize coordinates
    const xs = rows.map((r) => r.umap_x ?? 0);
    const ys = rows.map((r) => r.umap_y ?? 0);
    const zs = rows.map((r) => r.umap_z ?? 0);
    const norm = (arr) => {
      const mn = Math.min(...arr),
        mx = Math.max(...arr);
      const rng = mx - mn || 1;
      return arr.map((v) => ((v - mn) / rng) * 8 - 4);
    };
    const nx = norm(xs),
      ny = norm(ys),
      nz = norm(zs);

    // Use THREE.Points with vertex colors - guaranteed visible, no lighting dependency
    const positions = new Float32Array(rows.length * 3);
    const colors = new Float32Array(rows.length * 3);
    const c = new THREE.Color();
    const cLow = new THREE.Color("#2F81F7");
    const cHigh = new THREE.Color("#55EFC4");
    const cRiskL = new THREE.Color("#58A6FF");
    const cRiskH = new THREE.Color("#FF6B6B");

    rows.forEach((r, i) => {
      positions[i * 3] = nx[i];
      positions[i * 3 + 1] = ny[i];
      positions[i * 3 + 2] = nz[i];

      if (colorBy === "community") {
        c.set(commColor(r.community_id ?? 0));
      } else if (colorBy === "type") {
        c.set(TYPE_COLOR[r.node_type] ?? "#B2BEC3");
      } else if (colorBy === "risk") {
        const ratio = Math.min(1, r.cash_ratio ?? 0);
        c.lerpColors(cRiskL, cRiskH, ratio);
      } else {
        const p = Math.min(1, Math.log1p(r.in_strength ?? 0) / 15);
        c.lerpColors(cLow, cHigh, p);
      }
      colors[i * 3] = c.r;
      colors[i * 3 + 1] = c.g;
      colors[i * 3 + 2] = c.b;
    });

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));

    const mat = new THREE.PointsMaterial({
      size: 0.15,
      vertexColors: true,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.9,
    });

    const mesh = new THREE.Points(geo, mat);
    scene.add(mesh);

    // Camera orbit controls
    function updateCamera() {
      camera.position.set(
        spherical.r * Math.sin(spherical.phi) * Math.cos(spherical.theta),
        spherical.r * Math.cos(spherical.phi),
        spherical.r * Math.sin(spherical.phi) * Math.sin(spherical.theta),
      );
      camera.lookAt(0, 0, 0);
    }

    renderer.domElement.addEventListener("mousedown", (e) => {
      isDragging = true;
      lastX = e.clientX;
      lastY = e.clientY;
    });
    renderer.domElement.addEventListener("mouseup", () => {
      isDragging = false;
    });
    renderer.domElement.addEventListener("mousemove", (e) => {
      if (!isDragging) return;
      spherical.theta -= (e.clientX - lastX) * 0.007;
      spherical.phi = Math.max(
        0.1,
        Math.min(Math.PI - 0.1, spherical.phi - (e.clientY - lastY) * 0.007),
      );
      lastX = e.clientX;
      lastY = e.clientY;
    });
    renderer.domElement.addEventListener("wheel", (e) => {
      spherical.r = Math.max(3, Math.min(20, spherical.r + e.deltaY * 0.01));
    });
    renderer.domElement.style.cursor = "grab";

    // Hover tooltip via raycaster
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    renderer.domElement.addEventListener("mousemove", (e) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / W) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / H) * 2 + 1;
      raycaster.setFromCamera(mouse, camera);
      const hits = raycaster.intersectObject(mesh);
      if (hits.length > 0) {
        const idx = hits[0].index;
        tooltip3 = {
          x: e.clientX - rect.left,
          y: e.clientY - rect.top,
          node: rows[idx],
        };
        renderer.domElement.style.cursor = "pointer";
      } else {
        tooltip3 = { ...tooltip3, node: null };
        renderer.domElement.style.cursor = isDragging ? "grabbing" : "grab";
      }
    });

    renderer.domElement.addEventListener("click", () => {
      if (tooltip3.node?.id) openNode(tooltip3.node.id);
    });

    function animate() {
      animId = requestAnimationFrame(animate);
      updateCamera();
      renderer.render(scene, camera);
    }
    animate();
  }

  function fmtUSD(n) {
    if (!n) return "$0";
    if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
    if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
    if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
    return `$${(+n).toFixed(0)}`;
  }
</script>

<!-- ── Controls ─────────────────────────────────────────────── -->
<div class="viz-controls">
  <div class="ctrl-group">
    <span class="ctrl-label">VIEW</span>
    <button
      class="ctrl-btn"
      class:active={viewMode === "2d"}
      onclick={() => (viewMode = "2d")}>2D</button
    >
    <button
      class="ctrl-btn"
      class:active={viewMode === "3d"}
      onclick={() => {
        viewMode = "3d";
      }}>3D</button
    >
  </div>
  <div class="ctrl-sep"></div>
  <div class="ctrl-group">
    <span class="ctrl-label">COLOR</span>
    <button
      class="ctrl-btn"
      class:active={colorBy === "community"}
      onclick={() => (colorBy = "community")}>Community</button
    >
    <button
      class="ctrl-btn"
      class:active={colorBy === "type"}
      onclick={() => (colorBy = "type")}>Type</button
    >
    <button
      class="ctrl-btn"
      class:active={colorBy === "risk"}
      onclick={() => (colorBy = "risk")}>Cash Risk</button
    >
    <button
      class="ctrl-btn"
      class:active={colorBy === "payments"}
      onclick={() => (colorBy = "payments")}>Payments</button
    >
  </div>
  <div class="ctrl-sep"></div>
  <!-- ── Filters ──────────────────────────────────────────────── -->
  <div class="ctrl-group">
    <span class="ctrl-label">FILTER</span>
    <button
      class="ctrl-btn"
      class:active={typeFilter === null}
      onclick={() => (typeFilter = null)}
      title="Show all types">All</button
    >
    <button
      class="ctrl-btn"
      class:active={typeFilter === "Physician"}
      onclick={() =>
        (typeFilter = typeFilter === "Physician" ? null : "Physician")}
      title="Show only physicians"
      style={typeFilter === "Physician"
        ? "border-color:#58A6FF;color:#58A6FF"
        : ""}
    >
      Physicians
    </button>
    <button
      class="ctrl-btn"
      class:active={typeFilter === "Manufacturer"}
      onclick={() =>
        (typeFilter = typeFilter === "Manufacturer" ? null : "Manufacturer")}
      title="Show only manufacturers"
      style={typeFilter === "Manufacturer"
        ? "border-color:#FF9F43;color:#FF9F43"
        : ""}
    >
      Manufacturers
    </button>
    <button
      class="ctrl-btn"
      class:active={typeFilter === "TeachingHospital"}
      onclick={() =>
        (typeFilter =
          typeFilter === "TeachingHospital" ? null : "TeachingHospital")}
      title="Show only teaching hospitals"
      style={typeFilter === "TeachingHospital"
        ? "border-color:#FF6B6B;color:#FF6B6B"
        : ""}
    >
      Hospitals
    </button>
  </div>
  <div class="ctrl-sep"></div>
  <div class="ctrl-group">
    <span class="ctrl-label">STATE</span>
    <input
      type="text"
      maxlength="2"
      placeholder="e.g. CA"
      class="state-input"
      bind:value={stateFilter}
      title="Filter by state abbreviation (2 letters)"
    />
    {#if stateFilter}
      <button
        class="ctrl-btn"
        onclick={() => (stateFilter = "")}
        title="Clear state filter">✕</button
      >
    {/if}
  </div>
  {#if data2d}
    {@const filtered = applyFilters(data2d)}
    <span class="ctrl-count"
      >{filtered.length.toLocaleString()} / {data2d.length.toLocaleString()} nodes</span
    >
  {/if}
</div>

<!-- ── Canvas area ─────────────────────────────────────────── -->
<div class="viz-area">
  {#if loading}
    <div class="overlay-center">
      <div class="spinner"></div>
      <span>Loading embeddings…</span>
    </div>
  {:else if error}
    <div
      class="overlay-center"
      style="flex-direction:column;gap:8px;max-width:360px;text-align:center"
    >
      <span style="color:var(--color-warning);font-size:12px">{error}</span>
    </div>
  {:else if viewMode === "2d" && data2d && data2d.length > 0}
    {@const filtered2d = applyFilters(data2d)}
    <PlotlyChart
      traces={build2dTraces(filtered2d)}
      layout={layout2d}
      config={config2d}
      height={520}
      onClick={(pt) => {
        if (pt.customdata) openNode(pt.customdata);
      }}
    />
  {:else if viewMode === "3d"}
    <div bind:this={threeEl} class="three-wrap">
      {#if tooltip3.node}
        <div
          class="tooltip3"
          style="left:{tooltip3.x + 14}px;top:{tooltip3.y - 10}px"
        >
          <div class="tt-name">{tooltip3.node.name ?? tooltip3.node.id}</div>
          <div
            class="tt-type"
            style="color:{TYPE_COLOR[tooltip3.node.node_type] ?? '#B2BEC3'}"
          >
            {tooltip3.node.node_type}
          </div>
          {#if tooltip3.node.community_id != null}
            <div class="tt-row">
              <span>Community</span><span
                style="color:{commColor(tooltip3.node.community_id)}"
                >C{tooltip3.node.community_id}</span
              >
            </div>
          {/if}
          <div class="tt-row">
            <span>Payments</span><span>{fmtUSD(tooltip3.node.in_strength)}</span
            >
          </div>
          <div class="tt-row">
            <span>Cash ratio</span><span
              >{((tooltip3.node.cash_ratio ?? 0) * 100).toFixed(1)}%</span
            >
          </div>
          <div class="tt-hint">Click to open dossier →</div>
        </div>
      {/if}
    </div>
  {:else if data2d && data2d.length === 0}
    <div class="overlay-center" style="flex-direction:column;gap:8px">
      <span style="font-size:32px;opacity:.2">◎</span>
      <span style="color:var(--color-muted);font-size:12px"
        >No embedding data for {$selectedYear}</span
      >
    </div>
  {/if}
</div>

<!-- ── Controls legend (2D info bar / 3D overlay) ─────────────── -->
{#if viewMode === "2d"}
  <div class="hint-bar">
    UMAP 2D - proximity = similar payment behavior · Colored hulls show Leiden
    communities · Scroll to zoom · Click to open dossier
  </div>
{:else}
  <div class="ctrl-legend ctrl-legend--3d">
    <div class="ctrl-legend-row">
      <kbd class="ctrl-legend-key">Drag</kbd><span>Orbit</span>
    </div>
    <div class="ctrl-legend-row">
      <kbd class="ctrl-legend-key">Scroll</kbd><span>Zoom</span>
    </div>
    <div class="ctrl-legend-row">
      <kbd class="ctrl-legend-key">Click</kbd><span>Open dossier</span>
    </div>
  </div>
{/if}

<style>
  :global(.viz-wrap) {
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .viz-controls {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    padding: 7px 12px;
    background: rgba(13, 17, 23, 0.95);
    border-bottom: 1px solid var(--color-border);
    flex-shrink: 0;
    font-family: var(--font-sans);
  }

  .ctrl-sep {
    width: 1px;
    height: 16px;
    background: var(--color-border);
    margin: 0 4px;
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
    transition: all 0.12s;
    font-family: var(--font-sans);
  }
  .ctrl-btn:hover {
    color: var(--color-text);
    background: var(--color-hover);
  }
  .ctrl-btn.active {
    color: var(--color-accent);
    background: var(--color-accent-dim);
    border-color: rgba(47, 129, 247, 0.3);
    font-weight: 700;
  }

  .ctrl-count {
    font-size: 10px;
    color: var(--color-muted);
    margin-left: 4px;
    font-family: var(--font-mono);
  }

  .state-input {
    width: 38px;
    padding: 3px 6px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    color: var(--color-text);
    background: var(--color-hover);
    border: 1px solid var(--color-border);
    outline: none;
    text-transform: uppercase;
    font-family: var(--font-mono);
    transition: border-color 0.12s;
  }
  .state-input:focus {
    border-color: var(--color-accent);
  }
  .state-input::placeholder {
    color: var(--color-subtle);
    font-weight: 400;
    text-transform: none;
  }

  .viz-area {
    flex: 1;
    position: relative;
    overflow: hidden;
    background: var(--color-bg);
    min-height: 520px;
  }

  .three-wrap {
    width: 100%;
    height: 100%;
    min-height: 520px;
    position: relative;
  }

  .overlay-center {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    color: var(--color-muted);
    font-size: 13px;
  }

  /* 3D tooltip */
  .tooltip3 {
    position: absolute;
    background: rgba(13, 17, 23, 0.96);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 11px;
    pointer-events: none;
    z-index: 20;
    min-width: 160px;
    max-width: 220px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
    font-family: var(--font-sans);
  }
  .tt-name {
    font-size: 12px;
    font-weight: 700;
    color: var(--color-heading);
    margin-bottom: 2px;
    word-break: break-word;
  }
  .tt-type {
    font-size: 10px;
    font-weight: 700;
    margin-bottom: 6px;
  }
  .tt-row {
    display: flex;
    justify-content: space-between;
    padding: 2px 0;
    color: var(--color-muted);
  }
  .tt-row span:last-child {
    color: var(--color-heading);
    font-weight: 700;
    font-family: var(--font-mono);
    font-size: 10px;
  }
  .tt-hint {
    font-size: 9px;
    color: var(--color-accent);
    margin-top: 6px;
  }

  .hint-bar {
    padding: 4px 12px;
    background: rgba(13, 17, 23, 0.85);
    border-top: 1px solid var(--color-border);
    font-size: 10px;
    color: var(--color-subtle);
    flex-shrink: 0;
    font-style: italic;
    font-family: var(--font-sans);
  }

  /* 3D ctrl-legend floats inside the three-wrap */
  .ctrl-legend--3d {
    position: absolute;
    bottom: 12px;
    right: 12px;
    z-index: 20;
  }

  /* Spinner */
  .spinner {
    width: 18px;
    height: 18px;
    border: 2px solid var(--color-border);
    border-top-color: var(--color-accent);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
