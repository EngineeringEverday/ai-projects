/**
 * MappingMoney: Graph Lens API layer - all backend calls go through here.
 * Vite proxies /api → http://localhost:8000 during dev.
 */

const API_ROOT = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const BASE = API_ROOT ? `${API_ROOT}/api/v1` : "/api/v1";
const HEALTH_URL = API_ROOT ? `${API_ROOT}/health` : "/health";

// ── In-memory GET cache with tiered TTLs ─────────────────────────────────────
const _cache = new Map();
const CACHE_TTL = 5 * 60 * 1000;         // default: 5 min
const CACHE_TTL_LONG = 30 * 60 * 1000;   // year-agnostic data: 30 min
// Paths whose data never changes within a session
const LONG_TTL_PREFIXES = ["/analytics/temporal/evolution", "/analytics/temporal/payment-form-trends", "/analytics/temporal/jumps", "/analytics/temporal/emerging"];

// ── Concurrency limiter (max 3 in-flight requests) ───────────────────────────
const MAX_CONCURRENT = 3;
let _running = 0;
const _queue = [];

function _enqueue(fn) {
  return new Promise((resolve, reject) => {
    const run = () => {
      _running++;
      fn()
        .then(resolve)
        .catch(reject)
        .finally(() => {
          _running--;
          if (_queue.length > 0) _queue.shift()();
        });
    };
    if (_running < MAX_CONCURRENT) run();
    else _queue.push(run);
  });
}

async function get(path) {
  const now = Date.now();
  const cached = _cache.get(path);
  const ttl = LONG_TTL_PREFIXES.some((p) => path.startsWith(p)) ? CACHE_TTL_LONG : CACHE_TTL;
  if (cached && now - cached.ts < ttl) return cached.data;

  const data = await _enqueue(async () => {
    const res = await fetch(`${BASE}${path}`);
    if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
    return res.json();
  });
  _cache.set(path, { data, ts: now });
  return data;
}

/** Manually invalidate a cached path (e.g. after a mutation). */
export function invalidateCache(path) {
  _cache.delete(path);
}

/** Empty TableResponse — use as a fallback when a fetch should be skipped. */
export const EMPTY_TABLE = { rows: [], columns: [], total_rows: 0, limit: 0, offset: 0 };
export const emptyTable = () => Promise.resolve(EMPTY_TABLE);

// ── System ────────────────────────────────────────────────────────────────
export const getHealth = () => fetch(HEALTH_URL).then((r) => r.json());
export const getMeta = () => get("/meta").catch(() => get("/../meta"));
export const getYears = () => get("/graph/years");

// ── Graph ─────────────────────────────────────────────────────────────────
export const getGraphSummary = (year) => get(`/graph/summary/${year}`);

export const getGraphData = (year, nodeLimit = 300, edgeLimit = 600) =>
  get(`/graph/${year}?node_limit=${nodeLimit}&edge_limit=${edgeLimit}`);

export const getGraphSnapshot = (year, edgeLimit = 2000) =>
  get(`/dashboard/${year}/graph-snapshot?edge_limit=${edgeLimit}`);

// ── Nodes ─────────────────────────────────────────────────────────────────
export const searchNodes = (q, year, limit = 20) =>
  get(`/nodes/?q=${encodeURIComponent(q)}&year=${year}&limit=${limit}`);

export const getNodesByType = (year, nodeType, limit = 200, offset = 0) =>
  get(
    `/nodes/?year=${year}&node_type=${nodeType}&limit=${limit}&offset=${offset}`,
  );

export const getNode = (year, id) => get(`/nodes/${year}/${id}`);

// ── Centrality ────────────────────────────────────────────────────────────
export const getCentrality = (
  year,
  metric = "pagerank",
  topK = 100,
  fields = "",
) => {
  const f = fields ? `&fields=${fields}` : "";
  return get(
    `/analytics/centrality/${year}?metric=${metric}&top_k=${topK}${f}`,
  );
};

export const getNodeCentrality = (year, nodeId) =>
  get(`/analytics/centrality/${year}/node/${nodeId}`);

// ── Anomalies ─────────────────────────────────────────────────────────────
export const getAnomalies = (year, minScore = 0.5, limit = 200) =>
  get(`/analytics/anomalies/${year}?min_score=${minScore}&limit=${limit}`);

export const getCapture = (year, minRatio = 0.7, limit = 200) =>
  get(
    `/analytics/anomalies/${year}/capture?min_capture_ratio=${minRatio}&limit=${limit}`,
  );

// ── Communities ───────────────────────────────────────────────────────────
export const getCommunityAssignments = (year, mode = "bipartite") =>
  get(`/analytics/communities/${year}/assignments?mode=${mode}`);

export const getCommunitySummaries = (year) =>
  get(`/analytics/communities/${year}/summaries`);

export const getCommunityEmbeddings = (year, dims = 2, limit = 5000) =>
  get(`/analytics/communities/${year}/embeddings?dims=${dims}&limit=${limit}`);

export const getStateFlows = (year, limit = 100) =>
  get(`/analytics/communities/${year}/state-flows?limit=${limit}`);

// ── Concentration ─────────────────────────────────────────────────────────
export const getConcentration = (year, scope = "specialty", limit = 30) =>
  get(`/analytics/concentration/${scope}/${year}?limit=${limit}`);

export const getConcentrationDistribution = (year, scope = "global") =>
  get(`/analytics/concentration/distribution/${scope}/${year}`);

export const getTopEntities = (year, scope = "specialty", limit = 100) =>
  get(`/analytics/concentration/top-entities/${scope}/${year}?limit=${limit}`);

export const getSeasonality = (year) =>
  get(`/analytics/concentration/seasonality/${year}`);

export const getPaymentForms = (year) =>
  get(`/analytics/concentration/payment-forms/${year}`);

// ── Temporal ──────────────────────────────────────────────────────────────
export const getEvolution = () => get("/analytics/temporal/evolution");

export const getEmerging = (metric = "in_strength", limit = 30) =>
  get(`/analytics/temporal/emerging?metric=${metric}&limit=${limit}`);

export const getTrajectory = (metric = "in_strength", entityId = null) => {
  const q = entityId
    ? `?metric=${metric}&entity_id=${entityId}`
    : `?metric=${metric}`;
  return get(`/analytics/temporal/trajectory${q}`);
};

export const getJumps = (metric = "in_strength", limit = 200) =>
  get(`/analytics/temporal/jumps?metric=${metric}&limit=${limit}`);

export const getFlows = (scope = "specialty", limit = 500) =>
  get(`/analytics/temporal/flows/${scope}?limit=${limit}`);

export const getPaymentFormTrends = (scope = "global") =>
  get(`/analytics/temporal/payment-form-trends/${scope}`);

export const getRelationshipPersistence = (limit = 200) =>
  get(`/analytics/temporal/relationship-persistence?limit=${limit}`);

// ── Products ──────────────────────────────────────────────────────────────
export const getTopProducts = (year, type = "drug", limit = 50) =>
  get(`/analytics/products/${year}/top?product_type=${type}&limit=${limit}`);

export const getProductDiversity = (year, minPayment = 0, limit = 100) =>
  get(
    `/analytics/products/${year}/diversity?min_total_payment=${minPayment}&limit=${limit}`,
  );

// ── Dashboard ─────────────────────────────────────────────────────────────
export const getDashboardOverview = (year, topK = 10) =>
  get(`/dashboard/${year}/overview?top_k=${topK}`);
