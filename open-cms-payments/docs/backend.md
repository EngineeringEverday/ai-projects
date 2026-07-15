# Backend

The GraphLens backend is a **FastAPI** REST API serving precomputed graph analytics and on-demand graph data to the frontend. It is deployed on **Render** as a Docker container.

**Live URL:** Temp: `https://mappingmoney-graphlens.onrender.com`

---

## Stack

| Component | Technology |
|---|---|
| Framework | FastAPI + Uvicorn |
| Data processing | Polars (DataFrames), igraph (graph operations) |
| Serialization | Pydantic v2 |
| Package manager | uv |
| Container | Docker (python3.13-bookworm-slim via uv base image) |
| Hosting | Render (free tier) |

---

## Project Structure

```
api/
  main.py          # App factory, CORS, middleware, router mounts
  schemas.py       # Pydantic response models
  utils.py         # Parquet/JSON loader, in-memory analytics cache
  routers/
    graph.py       # /graph -> years, summary, payload
    nodes.py       # /nodes -> search and detail
    centrality.py  # /analytics/centrality
    communities.py # /analytics/communities
    anomalies.py   # /analytics/anomalies
    concentration.py
    temporal.py
    products.py
    dashboard.py   # /dashboard -> aggregated overview per year

graphlens/
  config.py        # DATA_DIR, PROCESSED_DIR, env vars
  graph.py         # GraphLensGraph, load_graph(), available_years()
  etl.py           # CSV -> Parquet pipeline

analytics/         # Precompute modules (run offline, not at request time)
```

---

## API Reference

Base path: `/api/v1`

### System

| Endpoint | Description |
|---|---|
| `GET /health` | Health check; returns status and available years |
| `GET /` | Service info and links |
| `GET /api/meta` | API version, available years, cache stats |

### Graph

| Endpoint | Description |
|---|---|
| `GET /api/v1/graph/years` | List available program years |
| `GET /api/v1/graph/{year}` | Full graph payload — nodes + edges (paginated via `node_limit`, `edge_limit`) |
| `GET /api/v1/graph/summary/{year}` | Summary stats — node count, edge count, total USD, node type breakdown |

Graph endpoints load from `edges_general.parquet` via `load_graph()` and build an igraph object in memory per request.

### Nodes

| Endpoint | Description |
|---|---|
| `GET /api/v1/nodes/` | Search nodes by name (`q`), filter by `year`, `node_type`, with pagination |
| `GET /api/v1/nodes/{year}/{id}` | Single node detail with all attributes |

### Analytics

All analytics endpoints serve from **precomputed JSON files** in `processed/analytics_json/`. Requests never re-run the analytics algorithms.

| Endpoint | Description |
|---|---|
| `GET /api/v1/analytics/centrality/{year}` | Top-k nodes by metric (pagerank, betweenness, in_strength, etc.) |
| `GET /api/v1/analytics/centrality/{year}/node/{id}` | All centrality metrics for a specific node |
| `GET /api/v1/analytics/communities/{year}/assignments` | Community membership per node (`bipartite` or `projection` mode) |
| `GET /api/v1/analytics/communities/{year}/summaries` | Per-community stats (size, total payments, top members) |
| `GET /api/v1/analytics/communities/{year}/embeddings` | UMAP 2D embeddings per node for scatterplot viz |
| `GET /api/v1/analytics/anomalies/{year}` | Nodes ranked by anomaly score |
| `GET /api/v1/analytics/anomalies/{year}/capture` | Company→physician capture analysis |
| `GET /api/v1/analytics/concentration/{scope}/{year}` | Payment concentration by specialty, state, or globally |
| `GET /api/v1/analytics/temporal/evolution` | Year-over-year network metrics |
| `GET /api/v1/analytics/temporal/emerging` | Fastest-rising entities by metric |
| `GET /api/v1/analytics/temporal/trajectory` | Payment/centrality time series for an entity |
| `GET /api/v1/analytics/temporal/jumps` | Entities with sudden year-over-year spikes |
| `GET /api/v1/analytics/products/{year}/top` | Top drugs/devices by payment volume |
| `GET /api/v1/analytics/products/{year}/diversity` | Product payment diversity per physician |
| `GET /api/v1/dashboard/{year}/overview` | Aggregated dashboard summary (KPIs, top payers, top recipients) |
| `GET /api/v1/dashboard/{year}/graph-snapshot` | Lightweight graph snapshot for the dashboard map |

All analytics routers also mount at `/api/*` (legacy path for backward compatibility).

---

## Data Loading Strategy

**Two-tier loading** in `api/utils.py`:

1. **JSON first**: looks for `processed/analytics_json/{stem}_{year}.json`. If found, reads directly into a Polars DataFrame. This is the path taken on Render (JSON files are committed via Git LFS).
2. **Parquet fallback**: looks for `processed/analytics/{stem}_{year}.parquet`. Used in local development where precomputed Parquets exist.

**In-memory cache**: loaded DataFrames are cached by `(stem, year)` key with mtime-based invalidation. Maximum 64 entries (configurable via `ANALYTICS_CACHE_MAX_ENTRIES`).

**`available_years()`** first tries to read `edges_general.parquet` (local dev). If the file is missing (production), it falls back to scanning `processed/analytics_json/` for files matching `*_{year}.json` and extracting the year numbers.

---

## Configuration

All configuration is via environment variables (`.env` file locally, Render dashboard in production):

| Variable | Default | Description |
|---|---|---|
| `PROCESSED_DIR` | `./processed` | Path to precomputed Parquet/JSON files |
| `DATA_DIR` | `./data` | Path to raw CMS CSV downloads |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `ANALYTICS_JSON_DIR` | `{PROCESSED_DIR}/analytics_json` | Override JSON file location |
| `ANALYTICS_CACHE_MAX_ENTRIES` | `64` | In-memory analytics cache size |
| `API_HOST` | `0.0.0.0` | Uvicorn bind host |
| `API_PORT` | `8000` | Uvicorn port |

**CORS:** Set `CORS_ORIGINS=your-origin-base` on Render to allow the GitHub Pages frontend. The default `*` is used when the variable is absent.

---

## Deployment

### Docker

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY graphlens ./graphlens
COPY api ./api
COPY analytics ./analytics
COPY processed ./processed      # includes analytics_json/ and .parquet files
RUN uv sync --frozen --no-dev
CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Render

Render builds the Docker image directly from the GitHub repository on every push to `main`/`master`. The `processed/` directory (Parquet files + analytics JSON via Git LFS) is baked into the image at build time.

**Required Render environment variable:**

- `CORS_ORIGINS=*` (or set to the specific origin of your GitHub Pages deployment for tighter security)

### Local Development

```bash
uv sync
uvicorn api.main:app --reload --port 8000
```

Interactive API docs available at `http://localhost:8000/docs`.
