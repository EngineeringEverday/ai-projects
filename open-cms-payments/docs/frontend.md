# Frontend

The GraphLens frontend is a **Svelte 5** single-page application built with **Vite**. It provides interactive visualizations of the CMS Open Payments graph analytics served by the backend API.

**Live URL:** `https://aaryesh-ad.github.io/graphlens/`

---

## Stack

| Component | Technology |
|---|---|
| Framework | Svelte 5 (runes syntax) |
| Build tool | Vite 8 |
| Styling | Tailwind CSS v4 |
| Network graph | Sigma.js + Graphology, Three.js (3D force graph) |
| Geo visualization | Deck.gl |
| Charts | Plotly.js, D3.js |
| Icons | Lucide Svelte |
| Hosting | GitHub Pages |
| CI/CD | GitHub Actions |

---

## Project Structure

```
frontend/
  index.html
  vite.config.js
  svelte.config.js
  src/
    main.js              # App entry point
    App.svelte           # Shell: splash screen, hash router, particle background
    app.css              # Global styles
    lib/
      api.js             # All backend calls (fetch + in-memory TTL cache)
      stores.js          # Svelte writable stores (global state)
      components/        # Reusable UI components
      routes/            # Page-level views
```

---

## Routing

The app uses a **hash-based router** built directly in `App.svelte`. Routes are loaded lazily via dynamic `import()` with a module cache to avoid re-fetching.

| Hash | Route Component | Description |
|---|---|---|
| `#explore` (default) | `Explore.svelte` | Network graph, products, temporal sub-tabs |
| `#investigate` | `Investigate.svelte` | Centrality, communities, concentration deep-dives |
| `#risk` | `Risk.svelte` | Anomaly detection and capture analysis |
| `#about` | `About.svelte` | Project info |

The `explore`, `investigate`, and `risk` routes are preloaded 2 seconds after initial mount.

---

## Global State (`lib/stores.js`)

All cross-component state lives in Svelte writable stores:

| Store | Default | Description |
|---|---|---|
| `selectedYear` | `2023` | Active program year for all data fetches |
| `comparedYears` | `[2022, 2023]` | Year pair for temporal comparisons |
| `activeMode` | `explore` | Current top-level route |
| `panelNodeId` | `null` | ID of the node open in the slide-in dossier panel |
| `exploreTab` | `network` | Active sub-tab within Explore |
| `activeState` | `null` | State filter (2-letter code) applied from the map |
| `networkSettings` | see below | Graph display options (color mode, node limit, filters) |
| `highlightedNodeId` | `null` | Node being hovered — synced across charts |
| `searchOpen` | `false` | Global search bar visibility |

`networkSettings` controls the graph renderer: color mode (`type` or `community`), size mode (`degree`, `payments`, or `fixed`), node/edge limits, label visibility, and node type filters.

---

## API Layer (`lib/api.js`)

All backend calls go through `api.js`. The API base URL is injected at **build time** from the `VITE_API_BASE_URL` environment variable:

```js
const API_ROOT = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const BASE = API_ROOT ? `${API_ROOT}/api/v1` : "/api/v1";
```

In development, Vite proxies `/api` and `/health` to `http://localhost:8000`.

**In-memory GET cache** with a 5-minute TTL prevents redundant fetches when navigating between views that share the same data. Cache is keyed by URL path; `invalidateCache(path)` can clear a specific entry.

Key API calls:

| Function | Endpoint |
|---|---|
| `getYears()` | `/graph/years` |
| `getGraphData(year, nodeLimit, edgeLimit)` | `/graph/{year}` |
| `getDashboardOverview(year)` | `/dashboard/{year}/overview` |
| `getCentrality(year, metric, topK)` | `/analytics/centrality/{year}` |
| `getCommunityAssignments(year, mode)` | `/analytics/communities/{year}/assignments` |
| `getCommunityEmbeddings(year, dims)` | `/analytics/communities/{year}/embeddings` |
| `getAnomalies(year, minScore)` | `/analytics/anomalies/{year}` |
| `getConcentration(year, scope)` | `/analytics/concentration/{scope}/{year}` |
| `getEvolution()` | `/analytics/temporal/evolution` |
| `getEmerging(metric)` | `/analytics/temporal/emerging` |
| `getTopProducts(year, type)` | `/analytics/products/{year}/top` |
| `searchNodes(q, year)` | `/nodes/` |
| `getNode(year, id)` | `/nodes/{year}/{id}` |

---

## Views & Components

### Routes

**Explore**: Three sub-tabs selectable via `exploreTab` store:

- *Network*: interactive 2D graph using Sigma.js + Graphology. Nodes colored by type or community, sized by degree or payment volume. Clicking a node opens the dossier panel.
- *Products*:drug/device product rankings and diversity charts via Plotly.
- *Temporal*: year-over-year evolution charts, emerging entities, relationship persistence.

**Investigate**: Deep analytical views:

- *Centrality*: ranked leaderboard with metric selector (PageRank, betweenness, in-strength, etc.), sparkline trends.
- *Communities*: UMAP scatterplot of physician/company clusters, community summary table, state-flow Sankey.
- *Concentration*: Gini/HHI bar charts by specialty or state, payment form breakdown.

**Risk**:Anomaly-focused:

- Ranked anomaly score table with score breakdown (financial vs. structural signal).
- Company capture analysis: heatmap of company -> physician payment dominance.

**Node Dossier Panel**: Slide-in overlay (`NodePanel.svelte`) showing full node detail: payment history, centrality metrics, connected companies/physicians. Triggered by clicking any node in the graph or selecting from a table.

### Key Components

| Component | Description |
|---|---|
| `TopBar.svelte` | Navigation bar with mode switcher, year selector, search |
| `YearSelector.svelte` | Dropdown that writes to `selectedYear` store |
| `NetworkGraph.svelte` | Sigma.js graph renderer with controls |
| `CommunityViz.svelte` | UMAP scatterplot using Plotly |
| `Map3D.svelte` | Deck.gl choropleth map for geographic concentration |
| `PlotlyChart.svelte` | Generic Plotly wrapper for bar, line, scatter charts |
| `DataTable.svelte` | Sortable, paginated table used across all views |
| `Sparkline.svelte` | Inline mini time-series chart |
| `StatCard.svelte` | KPI card with value and trend indicator |
| `LoadingSpinner.svelte` | Async loading state |
| `SplashScreen.svelte` | Entry animation gate before the main app renders |

---

## Build & Deployment

### Environment Variables

| Variable | Description |
|---|---|
| `VITE_API_BASE_URL` | Backend URL baked into the bundle at build time (e.g. `set_backend_api.com`) |
| `VITE_BASE_PATH` | Vite `base` option for GitHub Pages routing (e.g. `/graphlens/`) |

`VITE_API_BASE_URL` must be set as a **GitHub Actions repository secret** (`VITE_API_BASE_URL`). It is injected during `npm run build` and hardcoded into the output bundle — changing the secret requires a new build to take effect.

### Local Development

```bash
cd frontend
npm install
npm run dev     # Vite dev server at http://localhost:5173
                # Proxies /api and /health → http://localhost:8000
```

### CI/CD (GitHub Actions)

Workflow file: `.github/workflows/deploy-frontend-pages.yml`

Triggers on:
- Push to `main`/`master` when files in `frontend/**` or the workflow file change
- Manual `workflow_dispatch`

Steps:
1. Checkout (with `lfs: true` to fetch analytics JSON files if needed)
2. Setup Node 22 with npm cache
3. `npm ci`: install from lockfile
4. `npm run build`: Vite build with `VITE_API_BASE_URL` and `VITE_BASE_PATH` injected
5. Upload `frontend/dist` as Pages artifact
6. Deploy to GitHub Pages

Output is published to `https://aaryesh-ad.github.io/graphlens/`.
