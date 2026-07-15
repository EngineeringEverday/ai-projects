<script>
  /**
   * Map3D - deck.gl 3D choropleth for the USA
   *
   * Same features as the old 2D Plotly choropleth, upgraded to 3D:
   * • GeoJsonLayer  - state fills coloured by concentration metric,
   *                   extruded (height = log payment volume)
   * • ArcLayer      - cross-state payment flows, neon-green arcs
   * • TextLayer     - state abbreviation labels
   * • MapView pitch - tilted perspective out of the box
   * • Controller    - drag = pan, right-drag / ctrl-drag = rotate/tilt, scroll = zoom
   * • Click state   → emits onStateClick(abbrev)
   * • Hover         → tooltip with Gini / HHI / CR-5 / Total
   */
  import { onMount } from "svelte";
  import {
    Deck,
    MapView,
    LightingEffect,
    AmbientLight,
    DirectionalLight,
  } from "@deck.gl/core";
  import { GeoJsonLayer, ArcLayer, TextLayer } from "@deck.gl/layers";
  import * as topojson from "topojson-client";
  import usAtlas from "us-atlas/states-10m.json";

  let {
    concRows = [],
    flowRows = [],
    concMode = "gini",
    activeState = null,
    onStateClick = null,
  } = $props();

  // ── FIPS → 2-letter state abbrev ───────────────────────────────
  const FIPS = {
    "01": "AL",
    "02": "AK",
    "04": "AZ",
    "05": "AR",
    "06": "CA",
    "08": "CO",
    "09": "CT",
    "10": "DE",
    "11": "DC",
    "12": "FL",
    "13": "GA",
    "15": "HI",
    "16": "ID",
    "17": "IL",
    "18": "IN",
    "19": "IA",
    "20": "KS",
    "21": "KY",
    "22": "LA",
    "23": "ME",
    "24": "MD",
    "25": "MA",
    "26": "MI",
    "27": "MN",
    "28": "MS",
    "29": "MO",
    "30": "MT",
    "31": "NE",
    "32": "NV",
    "33": "NH",
    "34": "NJ",
    "35": "NM",
    "36": "NY",
    "37": "NC",
    "38": "ND",
    "39": "OH",
    "40": "OK",
    "41": "OR",
    "42": "PA",
    "44": "RI",
    "45": "SC",
    "46": "SD",
    "47": "TN",
    "48": "TX",
    "49": "UT",
    "50": "VT",
    "51": "VA",
    "53": "WA",
    "54": "WV",
    "55": "WI",
    "56": "WY",
  };

  // Convert topojson → GeoJSON, annotate each feature with state abbrev
  const statesGeo = topojson.feature(usAtlas, usAtlas.objects.states);
  statesGeo.features.forEach((f) => {
    f.properties.abb = FIPS[String(f.id).padStart(2, "0")] ?? null;
  });

  // State centroids for ArcLayer endpoints and TextLayer positions
  const CENTROIDS = {
    AL: [32.7, -86.7],
    AK: [64.2, -153.4],
    AZ: [34.3, -111.1],
    AR: [34.8, -92.2],
    CA: [36.8, -119.4],
    CO: [39.1, -105.4],
    CT: [41.6, -72.7],
    DE: [39.0, -75.5],
    FL: [27.8, -81.6],
    GA: [33.0, -83.6],
    HI: [20.9, -157.0],
    ID: [44.4, -114.6],
    IL: [40.0, -89.2],
    IN: [39.8, -86.1],
    IA: [42.0, -93.2],
    KS: [38.5, -98.4],
    KY: [37.6, -84.7],
    LA: [31.2, -91.8],
    ME: [44.7, -69.4],
    MD: [39.1, -76.8],
    MA: [42.2, -71.5],
    MI: [44.3, -85.4],
    MN: [46.4, -93.1],
    MS: [32.7, -89.7],
    MO: [38.5, -92.5],
    MT: [47.0, -110.5],
    NE: [41.5, -99.9],
    NV: [38.5, -117.1],
    NH: [44.0, -71.6],
    NJ: [40.2, -74.7],
    NM: [34.3, -106.0],
    NY: [42.9, -75.5],
    NC: [35.6, -79.8],
    ND: [47.5, -100.5],
    OH: [40.4, -82.8],
    OK: [35.6, -96.9],
    OR: [44.6, -122.1],
    PA: [40.6, -77.2],
    RI: [41.7, -71.5],
    SC: [33.8, -80.9],
    SD: [44.3, -100.2],
    TN: [35.9, -86.7],
    TX: [31.1, -97.6],
    UT: [40.1, -111.1],
    VT: [44.1, -72.7],
    VA: [37.8, -78.2],
    WA: [47.4, -121.5],
    WV: [38.6, -80.5],
    WI: [44.5, -89.5],
    WY: [43.1, -107.6],
    DC: [38.9, -77.0],
  };

  // ── Colour helpers ──────────────────────────────────────────────
  // Matches the old Plotly colorscale exactly: #161B22 → #1C3B6E → #2F81F7 → #F85149
  const CSTOPS = [
    { t: 0.0, r: 22, g: 27, b: 34 },
    { t: 0.4, r: 28, g: 59, b: 110 },
    { t: 0.7, r: 47, g: 129, b: 247 },
    { t: 1.0, r: 248, g: 113, b: 73 },
  ];

  function scaleRgb(t, alpha = 220) {
    t = Math.max(0, Math.min(1, t));
    for (let i = 1; i < CSTOPS.length; i++) {
      if (t <= CSTOPS[i].t) {
        const lo = CSTOPS[i - 1],
          hi = CSTOPS[i];
        const p = (t - lo.t) / (hi.t - lo.t);
        return [
          Math.round(lo.r + (hi.r - lo.r) * p),
          Math.round(lo.g + (hi.g - lo.g) * p),
          Math.round(lo.b + (hi.b - lo.b) * p),
          alpha,
        ];
      }
    }
    return [248, 113, 73, alpha];
  }

  // ── Tooltip state ───────────────────────────────────────────────
  let tooltip = $state({ x: 0, y: 0, abb: null, row: null });

  // ── deck.gl instance ────────────────────────────────────────────
  let canvasEl = $state(null);
  let deck;

  const INITIAL_VIEW = {
    longitude: -97,
    latitude: 38.5,
    zoom: 3.6,
    pitch: 45,
    bearing: 0,
  };

  // Lighting for extruded polygons
  const lighting = new LightingEffect({
    ambientLight: new AmbientLight({ color: [255, 255, 255], intensity: 0.7 }),
    directLight: new DirectionalLight({
      color: [255, 255, 255],
      intensity: 0.9,
      direction: [-3, -9, -1],
    }),
    fillLight: new DirectionalLight({
      color: [88, 166, 255],
      intensity: 0.3,
      direction: [5, 3, 5],
    }),
  });

  function fmtUSD(n) {
    if (!n) return "$0";
    if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
    if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
    if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
    return `$${(+n).toFixed(0)}`;
  }

  // ── Build deck.gl layers ────────────────────────────────────────
  function buildLayers(concRowsArg, flowRowsArg, concModeArg, activeStateArg) {
    // Index rows by state abbrev (API may give full name or abbrev)
    const byState = {};
    for (const r of concRowsArg) {
      const key =
        r.state?.length === 2 ? r.state : (STATE_ABB[r.state] ?? r.state);
      byState[key] = r;
    }

    const vals = Object.values(byState).map((r) => r[concModeArg] ?? 0);
    const mn = Math.min(...vals, 0);
    const mx = Math.max(...vals, 1);
    const maxPay = Math.max(
      ...Object.values(byState).map((r) => r.total_payment ?? 0),
      1,
    );

    // ── GeoJsonLayer: state fills + extrusion ────────────────────
    const geoLayer = new GeoJsonLayer({
      id: "states-fill",
      data: statesGeo,
      extruded: true,
      wireframe: false,
      getElevation: (f) => {
        const r = byState[f.properties.abb];
        if (!r) return 0;
        return (Math.log1p(r.total_payment ?? 0) / Math.log1p(maxPay)) * 150000;
      },
      getFillColor: (f) => {
        const abb = f.properties.abb;
        if (abb === activeStateArg) return [88, 166, 255, 240];
        const r = byState[abb];
        if (!r) return [22, 27, 34, 180];
        const t = mx > mn ? ((r[concModeArg] ?? 0) - mn) / (mx - mn) : 0;
        return scaleRgb(t, 215);
      },
      getLineColor: [48, 54, 61, 160],
      lineWidthMinPixels: 0.5,
      pickable: true,
      autoHighlight: true,
      highlightColor: [88, 166, 255, 80],
      onClick: ({ object }) => {
        if (!object?.properties?.abb) return;
        onStateClick?.(object.properties.abb);
      },
      onHover: ({ object, x, y }) => {
        if (object?.properties?.abb) {
          const abb = object.properties.abb;
          tooltip = { x, y, abb, row: byState[abb] ?? null };
        } else {
          tooltip = { ...tooltip, abb: null };
        }
      },
      updateTriggers: {
        getFillColor: [concModeArg, activeStateArg, concRowsArg],
        getElevation: [concRowsArg],
      },
    });

    // ── Borders on top to keep state lines crisp ─────────────────
    const borderLayer = new GeoJsonLayer({
      id: "states-border",
      data: statesGeo,
      stroked: true,
      filled: false,
      getLineColor: [48, 54, 61, 200],
      lineWidthMinPixels: 0.8,
      pickable: false,
    });

    // ── ArcLayer: cross-state flows ──────────────────────────────
    const topFlows = [...flowRowsArg]
      .sort((a, b) => (b.total_amount ?? 0) - (a.total_amount ?? 0))
      .slice(0, 25);
    const maxAmt = Math.max(...topFlows.map((r) => r.total_amount ?? 0), 1);

    const arcLayer = new ArcLayer({
      id: "arcs",
      data: topFlows,
      getSourcePosition: (r) => {
        const c = CENTROIDS[r.src_state];
        return c ? [c[1], c[0], 0] : [0, 0, 0];
      },
      getTargetPosition: (r) => {
        const c = CENTROIDS[r.dst_state];
        return c ? [c[1], c[0], 0] : [0, 0, 0];
      },
      getSourceColor: (r) => {
        const pct = (r.total_amount ?? 0) / maxAmt;
        return [
          30 + Math.round(pct * 200),
          230,
          20,
          Math.round(160 + pct * 80),
        ];
      },
      getTargetColor: [255, 255, 255, 200],
      getWidth: (r) => Math.max(1, 1.5 + ((r.total_amount ?? 0) / maxAmt) * 5),
      getHeight: 0.6,
      pickable: true,
      onHover: ({ object, x, y }) => {
        if (object) {
          const pct = (object.total_amount ?? 0) / maxAmt;
          tooltip = {
            x,
            y,
            abb: `${object.src_state} → ${object.dst_state}`,
            row: {
              _arc: true,
              total_payment: object.total_amount,
              _label: `${fmtUSD(object.total_amount ?? 0)} flow`,
            },
          };
        } else if (!tooltip.abb?.includes("→")) {
          // don't clear if geo hover is active
        } else {
          tooltip = { ...tooltip, abb: null };
        }
      },
    });

    // ── TextLayer: state abbrev labels ───────────────────────────
    const textData = Object.entries(CENTROIDS).map(([abb, [lat, lon]]) => ({
      abb,
      position: [
        lon,
        lat,
        (byState[abb]?.total_payment
          ? (Math.log1p(byState[abb].total_payment) / Math.log1p(maxPay)) *
            150000
          : 0) + 2000,
      ],
    }));

    const textLayer = new TextLayer({
      id: "labels",
      data: textData,
      getText: (d) => d.abb,
      getPosition: (d) => d.position,
      getSize: 11,
      getColor: [200, 210, 225, 200],
      fontFamily: "Inter, Arial, sans-serif",
      fontWeight: "600",
      billboard: true,
      getTextAnchor: "middle",
      getAlignmentBaseline: "center",
      updateTriggers: { getPosition: [concRowsArg] },
    });

    return [geoLayer, borderLayer, arcLayer, textLayer];
  }

  onMount(() => {
    deck = new Deck({
      canvas: canvasEl,
      views: new MapView({ repeat: false }),
      initialViewState: INITIAL_VIEW,
      controller: { dragRotate: true, touchRotate: true, keyboard: false },
      effects: [lighting],
      layers: buildLayers(concRows, flowRows, concMode, activeState),
      getCursor: ({ isHovering }) => (isHovering ? "pointer" : "grab"),
      style: { background: "#0D1117" },
    });

    return () => deck?.finalize();
  });

  // Rebuild layers whenever any reactive prop changes
  $effect(() => {
    const cr = concRows,
      fr = flowRows,
      cm = concMode,
      as_ = activeState;
    deck?.setProps({ layers: buildLayers(cr, fr, cm, as_) });
  });

  // ── Map abbreviation → full name (for byState key lookup) ───────
  // The API may return full state names; the old Plotly code had STATE_ABB for this
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
</script>

<!-- Canvas fills the parent flex container -->
<canvas bind:this={canvasEl} class="map-canvas"></canvas>

<!-- Tooltip overlay -->
{#if tooltip.abb}
  <div
    class="tt"
    style="left:{Math.min(tooltip.x + 14, 520)}px; top:{Math.max(
      tooltip.y - 70,
      4,
    )}px"
  >
    {#if tooltip.row?._arc}
      <div class="tt-title">{tooltip.abb}</div>
      <div class="tt-row">
        <span>Flow total</span><span>{tooltip.row._label}</span>
      </div>
    {:else}
      <div class="tt-title">{tooltip.abb}</div>
      {#if tooltip.row}
        <div class="tt-row">
          <span>Gini</span><span>{(tooltip.row.gini ?? 0).toFixed(3)}</span>
        </div>
        <div class="tt-row">
          <span>HHI</span><span>{(tooltip.row.hhi ?? 0).toFixed(0)}</span>
        </div>
        <div class="tt-row">
          <span>CR-5</span><span
            >{((tooltip.row.cr_5 ?? 0) * 100).toFixed(1)}%</span
          >
        </div>
        <div class="tt-row">
          <span>Total</span><span>{fmtUSD(tooltip.row.total_payment)}</span>
        </div>
        <div class="tt-row">
          <span># Entities</span><span>{tooltip.row.n_entities ?? "-"}</span>
        </div>
      {/if}
      <div class="tt-hint">Click to filter network →</div>
    {/if}
  </div>
{/if}

<div class="ctrl-legend">
  <div class="ctrl-legend-row">
    <kbd class="ctrl-legend-key">Drag</kbd><span>Pan</span>
  </div>
  <div class="ctrl-legend-row">
    <kbd class="ctrl-legend-key">Right-drag</kbd><span>Tilt / Rotate</span>
  </div>
  <div class="ctrl-legend-row">
    <kbd class="ctrl-legend-key">Scroll</kbd><span>Zoom</span>
  </div>
  <div class="ctrl-legend-row">
    <kbd class="ctrl-legend-key">Click state</kbd><span>Filter network</span>
  </div>
</div>

<style>
  .map-canvas {
    width: 100%;
    height: 100%;
    display: block;
    flex: 1;
    min-height: 0;
  }

  .tt {
    position: absolute;
    background: rgba(13, 17, 23, 0.96);
    border: 1px solid #30363d;
    border-radius: 7px;
    padding: 8px 12px;
    font-size: 11px;
    pointer-events: none;
    z-index: 20;
    min-width: 160px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.55);
    font-family: var(--font-sans);
  }
  .tt-title {
    font-weight: 700;
    color: #e6edf3;
    font-size: 13px;
    margin-bottom: 5px;
  }
  .tt-row {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    color: #7d8590;
    margin-bottom: 1px;
  }
  .tt-row span:last-child {
    color: #c9d1d9;
    font-weight: 600;
  }
  .tt-hint {
    font-size: 9px;
    color: var(--color-accent);
    margin-top: 5px;
  }
</style>
