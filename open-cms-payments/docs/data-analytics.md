# Data & Analytics

GraphLens analyzes CMS Open Payments data which is a public records of financial transfers from pharmaceutical manufacturers and medical device companies to physicians and teaching hospitals across the US, covering program years 2020–2024.

---

## Data Source

**CMS Open Payments** (openpaymentsdata.cms.gov) publishes three payment categories:

| Category | Description |
|---|---|
| General Payments | Consulting fees, food, travel, gifts, speaking fees |
| Research Payments | Payments tied to clinical trials and research studies |
| Ownership Interest | Physician equity stakes in healthcare companies |

Raw data is downloaded as CSV files per year and payment type. Combined, these span millions of individual payment records.

---

## ETL Pipeline (`graphlens/etl.py`)

The ETL transforms raw CMS CSVs into a set of compressed Parquet files using **Polars** (lazy evaluation with column-pruning at scan time).

**Output files written to `processed/`:**

| File | Contents |
|---|---|
| `nodes.parquet` | All unique entities: physicians, manufacturers, teaching hospitals |
| `edges_general.parquet` | Aggregated general payment edges (src→dst per year) |
| `edges_research.parquet` | Research payment edges |
| `edges_ownership.parquet` | Physician ownership interest edges |
| `node_products.parquet` | Drug/device product associations per edge record |
| `record_ids_general.parquet` | Record ID dedup table for incremental loads |

**Node schema:** `id`, `node_type`, `name`, `credential_type`, `specialty`, `specialties` (pipe-joined slots 1–6), `state`, `city`, `zip_code`

**Edge schema:** `src_id`, `dst_id`, `year`, `total_amount`, `payment_count`, `natures`, `payment_forms`, `disputed_count`, `products`

Key ETL decisions:

- UNCHANGED rows are dropped at read time (CMS re-publishes prior years in later files)
- Specialty slots 1–6 are pipe-joined; the first non-null becomes the primary `specialty`
- Drug/device slots 1–5 are unpivoted into `node_products.parquet`
- All type-casting is `strict=False` to tolerate CMS data quirks

Run: `uv run python -m graphlens.etl` or `--year 2023` for a single year.

---

## Graph Model (`graphlens/graph.py`)

The core abstraction is `GraphLensGraph` which is an `igraph`-backed directed weighted graph paired with Polars DataFrames for node and edge metadata.

**Structure:** Directed bipartite graph : manufacturers (source) -> physicians/hospitals (target). Edge weight = total USD paid in a program year.

**Key operations:**
- `load_graph(year, specialty, state, min_amount)` — builds a filtered graph from Parquet
- `load_temporal_snapshots()`: loads one graph per year as `dict[year → GraphLensGraph]`
- `induced_subgraph()`, `specialty_subgraph()`, `state_subgraph()`: filtered views
- `project_physicians()` / `project_companies()`: unipartite projections for community analysis

---

## Analytics Modules (`analytics/`)

All analytics are precomputed via `analytics/precompute.py` and exported to `processed/analytics_json/` as JSON files. The API serves these directly without re-computing at request time.

### Centrality (`analytics/centrality.py`)

Computes node-level influence and structural metrics per year:

| Metric | Description |
|---|---|
| PageRank | Weighted (damping=0.85): structural influence |
| In-degree / Out-degree | Unique payer/recipient counts |
| In-strength / Out-strength | Total USD received / paid |
| Betweenness | Normalized edge-weighted betweenness (sampled for large graphs) |
| HITS Hub & Authority | Hub = company funding many influential physicians; Authority = physician funded by many influential companies |
| Payment Diversity | Count of distinct counterparties |

### Community Detection (`analytics/community.py`)

Two complementary modes using the **Leiden algorithm** (via `leidenalg`):

- **Bipartite Leiden** — run directly on the undirected bipartite graph. Communities are mixed payment ecosystems (companies + physicians together).
- **Projection-based** — project onto the physician node set first (two physicians linked if they share ≥1 payer), then run Leiden. Communities represent physician clusters with similar funding profiles.

UMAP embeddings (2D) are precomputed per community for visualization in the frontend.

### Anomaly Detection (`analytics/anomaly.py`)

Two complementary signals combined into a composite `anomaly_score ∈ [0, 1]`:

**Financial outliers (statistical):**

- Log-transform `total_amount` and z-score within peer group (specialty × state)
- Flag physicians in the top 2.5% of z-score within their peer group

**Structural anomalies (graph-based):**

- *Captured physician*: high PageRank but low payment diversity (one company dominates)
- *Emerging star*: high PageRank combined with a sudden year-over-year payment jump
- *Structural broker*: top betweenness centrality but neither the largest payer nor receiver

Scores are continuous, not binary, to avoid misuse as hard classifications.

**Company-physician capture analysis:** identifies company→physician pairs where one company accounts for a disproportionate share of a physician's total payments.

### Concentration (`analytics/concentration.py`)

Market inequality metrics computed per specialty, state, or globally:

| Metric | Range | Interpretation |
|---|---|---|
| Gini coefficient | [0, 1] | 0 = equal distribution; 1 = one entity gets all |
| HHI | [0, 10000] | Herfindahl-Hirschman Index (standard economic measure) |
| CR-k | [0, 1] | Share held by top-k entities |
| Theil T | [0, ∞) | Entropy-based; sensitive to top-end concentration |
| Normalized entropy | [0, 1] | Diversity of payers; 1 = all equally funded |

Answers questions like: "Is oncology funding dominated by a few companies?" and "Has concentration increased year-over-year?"

### Temporal Analytics (`analytics/temporal.py`)

Cross-year analysis operating on `dict[year → GraphLensGraph]`:

- **Network evolution**: year-over-year changes in node count, edge count, total payments, density, Gini, and HHI
- **Entity trajectory**: payment and centrality time series for specific physicians or companies
- **Emerging entities**: fastest-rising nodes by in-strength or PageRank delta
- **Relationship persistence**: fraction of edges that recur across consecutive years
- **Payment flow shifts**: specialty- or state-level payment volume trends over time

### Products (`analytics/products.py`)

Drug and device product-level analysis using `node_products.parquet`:

- Top products by total payments per year
- Product payment diversity (how many physicians receive payments for a given drug/device)
- Node-to-product associations for the graph explorer

---
