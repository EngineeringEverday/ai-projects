# GraphLens: Frontend Analytics Features

All analytics are scoped to the year selected in the global year picker (top-right of every page). Data is fetched from the FastAPI backend and cached client-side for 5 minutes (30 minutes for year-agnostic data).

---

## Explore

Three sub-views accessible via top tabs.

### Network (default)

| Panel | What it shows |
|-------|---------------|
| **3D Network Globe** | Force-directed graph rendered with Three.js/3d-force-graph. Nodes are physicians, companies, and hospitals; edges are payments. Color modes: by node type or by Louvain community (community data loads on demand when "Community" is clicked). |
| **Map 3D** | Geographic view of payments overlaid on a US map. Node positions driven by state lat/lon. |
| **Overview KPIs** | Node count, edge count, total payments, top specialty, top company which are drawn from the graph summary endpoint. |

### Products *(lazy loads on tab click)*

| Chart | Details |
|-------|---------|
| **Top Drugs Treemap** | Top 50 drug products by total payment, sized by payment volume. |
| **Top Devices Treemap** | Same for device products. |
| **Physician Diversity Scatter** | Each point is a physician. X = number of distinct products received payments for, Y = total payment. Helps spot physicians with unusually broad or deep product relationships. |

### Temporal *(lazy loads on tab click)*

| Chart | Details |
|-------|---------|
| **Year-over-Year Evolution** | Line chart of graph-level metrics (node count, edge count, total payments, density) across all available years. |
| **Emerging Entities** | Bar chart of entities with the steepest upward trajectory in in-strength (payment inflow) over recent years. |
| **Payment Form Trends** | Stacked area showing how payment forms (cash, stock, in-kind, etc.) shift over time globally. |
| **Sudden Jumps** | Table of entities that had the largest year-over-year absolute spikes in a chosen metric. |

---

## Investigate

Split into three sub-views via top tabs.

### Centrality

Ranks nodes by influence within the payment network.

| Control | Options |
|---------|---------|
| **Metric** | PageRank · In-strength · In-degree · Betweenness · Authority score · Payment diversity |
| **Top-K** | 25 / 50 / 100 / 200 nodes |
| **View** | Scatter (rank vs metric value) or Table |

The scatter view lets you spot the long-tail drop-off. Hovering a point shows the node name, type, specialty (if physician), and metric value.

### Communities

Shows the result of Louvain community detection run on different graph projections.

**Summaries tab**

- **Treemap**: top 60 communities sized by total payment volume, colored by cash-share (blue = low, red = high).
- **Bubble chart**: each bubble is a community; X = physician count, Y = company count, bubble size = total payments, color = cash share.
- **Table**: all communities with columns: size, n_companies, n_physicians, n_hospitals, total_payment_usd, cash_share, top_specialties.

**Assignments tab** *(load-gated ~9 MB, click "Load Assignments" to fetch)*

Table mapping every node to its community ID. Supports three projection modes:

| Mode | Graph used for community detection |
|------|-----------------------------------|
| `bipartite` | Full physician–company bipartite graph |
| `physician_projection` | Physician-physician co-payment graph (shared payers) |
| `company_projection` | Company–company co-payment graph (shared recipients) |

### Concentration

Measures how unevenly payments are distributed across specialties, states, or credential types.

| Tab | Content |
|-----|---------|
| **By Specialty / State / Credential** | Bar chart of Gini coefficient, HHI, CR-5, and entropy for the selected scope. Picker switches scope. |
| **Multi-year Heatmap** | Heatmap of concentration scores across all available years, one row per top entity, one column per year. Shows which entities have consistently dominated. |
| **Seasonality** | Monthly payment totals for the selected year, reveals Q4 surges and slow periods. |
| **Payment Forms** | Pie / bar breakdown of payment form categories (cash, stock, ownership, in-kind travel, etc.) for the selected year. |

---

## Risk

Dashboard surfacing potential conflict-of-interest signals. Four accordion sections.

### Anomalies

4-quadrant scatter: X = Z-score (statistical deviation from peers), Y = composite anomaly score (0–1). Nodes in the top-right are both statistically extreme and flagged by multiple heuristics.

- **Score threshold slider**: filters the scatter and table to nodes above a minimum composite score.
- **Table**: anomaly details: node name, type, specialty, state, z-score, composite score, and contributing factors.

### Capture Analysis *(load-gated click "Load Capture Analysis")*

Identifies physicians whose payments are dominated by a single company (high "capture ratio"). Shows:

- Table of physicians with capture ratio ≥ 0.5 (configurable), sorted by ratio descending.
- Useful for spotting exclusive relationships that may indicate undue influence.

### Concentration Snapshot

Multi-specialty concentration bar chart for the selected year, same data as the Investigate → Concentration view, surfaced here for quick cross-reference alongside anomaly data.

### Community Visualization

Interactive 3D (default) or 2D UMAP embedding of all communities, colored by community ID.

- Toggle between **3D** and **2D** with the view switcher.
- Hover a point to see the community ID, size, total payments, and top specialty.
- Useful for visually assessing how tightly clustered communities are and whether large communities fragment in lower-dimensional space.

---

## Graph Explorer

Standalone full-screen graph view (accessible via sidebar).

| Feature | Details |
|---------|---------|
| **2D force layout** | D3-force simulation; nodes repel, edges attract. |
| **Color modes** | By node type (physician / company / hospital) or by Louvain community (fetched on demand). |
| **Node search** | Type-ahead search; matching node is highlighted and centered. |
| **Edge weight filter** | Slider to hide edges below a minimum payment threshold — reduces clutter in dense areas. |
| **Node dossier** | Click any node to open a side panel with full node details: name, type, specialty, state, top payment partners, centrality scores. |

---

## Node Dossier (NodeDetail)

Accessible by clicking any node in the Graph Explorer or from search results.

- Identity card: name, type, NPI/company ID, specialty, state.
- Payment summary: total received/paid, number of unique partners.
- Centrality panel: PageRank, in-strength, betweenness, authority score, payment diversity with percentile ranks.
- Top partners table: ranked list of entities this node transacts with most.
- Community membership: which community the node belongs to across each projection mode.

---

## Dashboard

Landing page shown on first load.

| Widget | Source |
|--------|--------|
| KPI cards | Node count, edge count, total payments, avg payment, top company, top specialty |
| Evolution chart | Year-over-year line of total payments and node count |
| State concentration map | Choropleth of total payments by state for the selected year |
| Top-10 tables | Top physicians and top companies by total payment received |

---
