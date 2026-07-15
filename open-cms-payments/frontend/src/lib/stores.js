import { writable, derived } from "svelte/store";

// ── Persistent selections ──────────────────────────────────────────
export const selectedYear = writable(2023);
export const comparedYears = writable([2022, 2023]);

// ── App mode (3-mode nav) ─────────────────────────────────────────
// 'explore' | 'investigate' | 'risk'
export const activeMode = writable("explore");

// ── Node panel (slide-in dossier) ─────────────────────────────────
// null = closed, string = open with this node ID
export const panelNodeId = writable(null);

// Helper: open a node in the slide-in panel
export function openNode(id) {
  panelNodeId.set(id);
}

// ── Explore sub-tab ───────────────────────────────────────────────
// 'network' | 'products' | 'temporal'
export const exploreTab = writable("network");

// ── Map filter (clicking a state filters the network) ─────────────
export const activeState = writable(null); // e.g. 'CA', null = all

// ── Risk accordion state ──────────────────────────────────────────
export const riskSection = writable("anomalies"); // which accordion is expanded

// ── Global search state ───────────────────────────────────────────
export const searchOpen = writable(false);

// ── Cross-chart highlighted entity ────────────────────────────────
// null = none; string = nodeId being hovered in any view
export const highlightedNodeId = writable(null);

// ── Network graph display settings ───────────────────────────────
export const networkSettings = writable({
  colorMode: "type", // 'type' | 'community'
  sizeBy: "degree", // 'fixed' | 'degree' | 'payments'
  showLabels: true,
  nodeLimit: 50, // manufacturers; physicians added automatically from edges
  edgeLimit: 600,
  minEdgeWeight: 0,
  showTypes: {
    Physician: true,
    Manufacturer: true,
    TeachingHospital: true,
  },
});
