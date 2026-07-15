#! usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GraphLens Graph Loader
======================
Core graph construction layer.  Loads processed Parquet files into
igraph-backed GraphLensGraph objects.  All heavy analytics live in
the analytics/ package; this module is responsible only for:

  - Building and filtering graphs from Parquet
  - Temporal snapshot generation
  - Bipartite projections (physician↔physician, company↔company)
  - Induced subgraph extraction

Public surface
--------------
  load_graph(...) -> GraphLensGraph  (filtered single graph)
  load_temporal_snapshots()  -> dict[int, GraphLensGraph]
  load_nodes()  -> pl.DataFrame
  load_edges(...)  -> pl.DataFrame
  available_years()  -> list[int]
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import polars as pl  # type: ignore[import-not-found]
import igraph as ig  # type: ignore[import-not-found]

from graphlens.config import (
    nodes_path, edges_path,
    research_path, ownership_path,
)


# GraphLensGraph wrapper
@dataclass
class GraphLensGraph:
    """
    Wraps an igraph.Graph with Polars DataFrames and string↔int id mapping.

    Attributes
    ----------
    ig       : igraph.Graph  - C-backed directed weighted graph
    nodes    : pl.DataFrame  - vertex metadata (one row per node)
    edges    : pl.DataFrame  - edge metadata (one row per edge)
    _id_map  : dict[str,int] - string node id -> igraph vertex index
    _idx_map : list[str]     - igraph vertex index -> string node id
    year     : int | None    - program year this graph was built for
    """

    ig: ig.Graph
    nodes: pl.DataFrame
    edges: pl.DataFrame
    year: int | None = None
    _id_map: dict[str, int] = field(default_factory=dict, repr=False)
    _idx_map: list[str] = field(default_factory=list, repr=False)

    # ID / vertex lookups

    def vid(self, string_id: str) -> int:
        """String node id -> igraph vertex index.  Raises KeyError if absent."""
        return self._id_map[str(string_id)]

    def nid(self, vertex_index: int) -> str:
        """igraph vertex index -> string node id."""
        return self._idx_map[vertex_index]

    def get_vertex(self, string_id: str) -> ig.Vertex:
        return self.ig.vs[self.vid(string_id)]

    # Node-type helpers
    def manufacturer_ids(self) -> list[int]:
        return [v.index for v in self.ig.vs if v["node_type"] == "Manufacturer"]

    def physician_ids(self) -> list[int]:
        return [v.index for v in self.ig.vs if v["node_type"] == "Physician"]

    def hospital_ids(self) -> list[int]:
        return [v.index for v in self.ig.vs if v["node_type"] == "TeachingHospital"]

    # Summary
    def summary(self) -> dict:
        weights = self.ig.es["weight"] if self.ig.ecount() > 0 else [0.0]
        type_counts: dict[str, int] = {}
        cred_counts: dict[str, int] = {}
        for v in self.ig.vs:
            t = v["node_type"] or "Unknown"
            type_counts[t] = type_counts.get(t, 0) + 1
            c = v["credential_type"] or ""
            if c:
                cred_counts[c] = cred_counts.get(c, 0) + 1
        total_usd = sum(weights)
        n_edges = self.ig.ecount()

        # Cash payment share (if payment_forms stored on edges)
        cash_usd = 0.0
        if n_edges > 0 and "payment_forms" in self.ig.es.attribute_names():
            for e in self.ig.es:
                if "cash" in (e["payment_forms"] or "").lower():
                    cash_usd += e["weight"]

        return {
            "nodes": self.ig.vcount(),
            "edges": n_edges,
            "node_types": type_counts,
            "credential_types": cred_counts,
            "total_payment_usd": round(total_usd, 2),
            "cash_payment_usd": round(cash_usd, 2),
            "avg_edge_weight_usd": round(total_usd / max(n_edges, 1), 2),
            "is_directed": self.ig.is_directed(),
            "year": self.year,
        }

    def __repr__(self) -> str:
        s = self.summary()
        yr = f"year={s['year']}  " if s["year"] else ""
        return (
            f"GraphLensGraph({yr}"
            f"{s['nodes']:,} nodes  {s['edges']:,} edges  "
            f"${s['total_payment_usd']:,.0f} total USD)"
        )

    # Subgraph extraction
    def induced_subgraph(self, vertex_ids: Iterable[int]) -> "GraphLensGraph":
        """
        Return a new GraphLensGraph containing only the given igraph vertex indices.
        Node and edge DataFrames are filtered to match.
        """
        vids = list(vertex_ids)
        sub_ig = self.ig.induced_subgraph(vids)

        # Rebuild id maps
        new_idx_map = [self._idx_map[v] for v in vids]
        new_id_map = {nid: i for i, nid in enumerate(new_idx_map)}

        # Filter node DataFrame
        sub_nodes = self.nodes.filter(
            pl.col("id").cast(pl.Utf8).is_in(new_idx_map)
        )

        # Filter edge DataFrame: keep edges where both endpoints are in subgraph
        sub_nodes_set = set(new_idx_map)
        sub_edges = self.edges.filter(
            pl.col("src_id").cast(pl.Utf8).is_in(sub_nodes_set) & pl.col("dst_id").cast(pl.Utf8).is_in(sub_nodes_set)
        )

        return GraphLensGraph(
            ig=sub_ig,
            nodes=sub_nodes,
            edges=sub_edges,
            year=self.year,
            _id_map=new_id_map,
            _idx_map=new_idx_map,
        )

    def specialty_subgraph(self, specialty: str) -> "GraphLensGraph":
        """
        Induced subgraph for a given specialty (case-insensitive contains).
        Checks both the primary `specialty` attribute AND the pipe-joined
        `specialties` field (all 6 slots), so multi-specialty providers are
        correctly included.
        """
        spec_lower = specialty.strip().lower()
        phys_ids = {
            v.index for v in self.ig.vs
            if v["node_type"] == "Physician" and (
                spec_lower in (v["specialty"] or "").lower() or spec_lower in (v["specialties"] or "").lower()
            )
        }
        if not phys_ids:
            raise ValueError(f"No physicians found for specialty '{specialty}'")
        mfr_ids: set[int] = set()
        for e in self.ig.es:
            if e.target in phys_ids:
                mfr_ids.add(e.source)
        return self.induced_subgraph(phys_ids | mfr_ids)

    def state_subgraph(self, state: str) -> "GraphLensGraph":
        """Induced subgraph for recipients in a given state (2-letter)."""
        state_up = state.upper()
        target_ids = {
            v.index for v in self.ig.vs
            if (v["state"] or "").upper() == state_up
        }
        if not target_ids:
            raise ValueError(f"No nodes found for state '{state}'")
        src_ids: set[int] = set()
        for e in self.ig.es:
            if e.target in target_ids:
                src_ids.add(e.source)
        return self.induced_subgraph(target_ids | src_ids)

    def credential_type_subgraph(self, credential: str) -> "GraphLensGraph":
        """
        Induced subgraph for providers with a given credential type
        (MD, DO, PA, NP, CRNA, etc.).  Case-insensitive contains match.

        Useful for separating physician vs. non-physician practitioner (NPP)
        payment ecosystems, which CMS began tracking separately in PY2021.
        """
        cred_lower = credential.strip().lower()
        target_ids = {
            v.index for v in self.ig.vs
            if cred_lower in (v["credential_type"] or "").lower()
        }
        if not target_ids:
            raise ValueError(f"No providers found for credential type '{credential}'")
        src_ids: set[int] = set()
        for e in self.ig.es:
            if e.target in target_ids:
                src_ids.add(e.source)
        return self.induced_subgraph(target_ids | src_ids)

    def payment_form_subgraph(self, form: str) -> "GraphLensGraph":
        """
        Induced subgraph containing only edges whose payment_forms field
        contains the given form string (e.g. 'Cash', 'Stock', 'In-kind').
        Retains all nodes that have at least one matching edge.
        """
        form_lower = form.strip().lower()
        keep_src: set[str] = set()
        keep_dst: set[str] = set()
        keep_edge_mask: list[bool] = []
        for e in self.ig.es:
            match = form_lower in (e["payment_forms"] or "").lower()
            keep_edge_mask.append(match)
            if match:
                keep_src.add(self.ig.vs[e.source]["id"])
                keep_dst.add(self.ig.vs[e.target]["id"])

        if not keep_src:
            raise ValueError(f"No edges found for payment form '{form}'")

        keep_node_ids = {
            v.index for v in self.ig.vs
            if v["id"] in keep_src or v["id"] in keep_dst
        }
        sub = self.induced_subgraph(keep_node_ids)
        # Further filter edges within subgraph
        sub_edge_mask = [
            form_lower in (e["payment_forms"] or "").lower()
            for e in sub.ig.es
        ]
        sub.edges = sub.edges.filter(pl.Series("keep", sub_edge_mask))
        return sub

    # Bipartite projections
    def project_physicians(
        self,
        weight_mode: str = "shared_companies",
        max_neighbors_per_source: int | None = 250,
        max_pair_updates: int | None = 2_000_000,
    ) -> "GraphLensGraph":
        """
        Project the bipartite graph onto the physician node set.

        Two physicians are connected if they share ≥1 paying company.
        Edge weight = number of shared companies (default) or total shared
        payment amount when weight_mode='shared_amount'.

        Returns a new undirected GraphLensGraph over physician nodes only.
        """
        return _bipartite_project(
            self,
            source_type="Manufacturer",
            target_type="Physician",
            weight_mode=weight_mode,
            max_neighbors_per_source=max_neighbors_per_source,
            max_pair_updates=max_pair_updates,
        )

    def project_companies(
        self,
        weight_mode: str = "shared_recipients",
        max_neighbors_per_source: int | None = 500,
        max_pair_updates: int | None = 2_000_000,
    ) -> "GraphLensGraph":
        """
        Project onto the company node set.

        Two companies are connected if they share ≥1 common recipient.
        """
        return _bipartite_project(
            self,
            source_type="Physician",
            target_type="Manufacturer",
            weight_mode=weight_mode,
            max_neighbors_per_source=max_neighbors_per_source,
            max_pair_updates=max_pair_updates,
        )

    def to_undirected_weighted(self) -> "GraphLensGraph":
        """
        Collapse directed edges to undirected by summing weights.
        Useful for community detection on the full bipartite graph.
        """
        und_ig = self.ig.as_undirected(combine_edges={"weight": "sum"})
        und_ig.es["weight"] = [max(w, 0.0) for w in und_ig.es["weight"]]
        return GraphLensGraph(
            ig=und_ig,
            nodes=self.nodes,
            edges=self.edges,
            year=self.year,
            _id_map=self._id_map.copy(),
            _idx_map=self._idx_map.copy(),
        )

    # Year filtering (for use on all-years graphs)
    def year_slice(self, year: int) -> "GraphLensGraph":
        """
        Filter this graph to edges from a specific year.
        Returns a new GraphLensGraph.
        """
        if "year" not in self.edges.columns:
            raise ValueError("Edge DataFrame has no 'year' column")
        year_edges = self.edges.filter(pl.col("year") == year)
        if year_edges.is_empty():
            raise ValueError(f"No edges found for year {year}")
        return _build_graph_from_dataframes(
            nodes_df=self.nodes,
            edges_df=year_edges,
            year=year,
        )


# Core loader
def load_graph(
    year: int | None = None,
    specialty: str | None = None,
    state: str | None = None,
    credential_type: str | None = None,
    min_amount: float = 0.0,
    include_research: bool = False,
    include_ownership: bool = False,
    processed_dir: str | Path | None = None,
) -> GraphLensGraph:
    """
    Build a GraphLensGraph from processed Parquet files.

    Parameters
    ----------
    year             : Filter to a single program year (None = all years).
    specialty        : Keep physicians whose specialty (any slot) contains
                       this string (case-insensitive), e.g. "Cardiology".
    state            : Keep recipients in this 2-letter state, e.g. "CA".
    credential_type  : Keep providers with this credential (MD, DO, PA, NP…).
    min_amount       : Drop edges with total_amount < this value.
    include_research : Add PAID_RESEARCH edges.
    include_ownership: Add OWNS_INTEREST edges (physician -> manufacturer).
    processed_dir    : Override default Parquet directory.
    """
    paths = _resolve_parquet_paths(processed_dir)
    _check_processed(paths["nodes"], paths["general"])

    nodes_df = pl.read_parquet(paths["nodes"])
    edges_df = pl.read_parquet(paths["general"])

    # edge filters: year, amount
    if year is not None:
        edges_df = edges_df.filter(pl.col("year") == year)
    if min_amount > 0:
        edges_df = edges_df.filter(pl.col("total_amount") >= min_amount)

    # node filters: specialty (checks both specialty and specialties cols)
    if specialty:
        spec_lower = specialty.strip().lower()
        phys_ids = (
            nodes_df
            .filter(
                (pl.col("node_type") == "Physician") & (
                    pl.col("specialty").fill_null("").str.to_lowercase()
                      .str.contains(spec_lower, literal=True) | pl.col("specialties").fill_null("").str.to_lowercase()
                      .str.contains(spec_lower, literal=True)
                )
                if "specialties" in nodes_df.columns
                else (pl.col("node_type") == "Physician") & pl.col("specialty").fill_null("").str.to_lowercase().str.contains(spec_lower, literal=True)
            )["id"].cast(pl.Utf8)
        )
        edges_df = edges_df.filter(pl.col("dst_id").is_in(phys_ids))

    if state:
        state_ids = (
            nodes_df
            .filter(pl.col("state") == state.upper())["id"].cast(pl.Utf8)
        )
        edges_df = edges_df.filter(pl.col("dst_id").is_in(state_ids))

    if credential_type:
        cred_lower = credential_type.strip().lower()
        cred_ids = (
            nodes_df
            .filter(
                pl.col("credential_type").fill_null("").str.to_lowercase()
                  .str.contains(cred_lower, literal=True)
            )["id"].cast(pl.Utf8)
            if "credential_type" in nodes_df.columns
            else pl.Series([], dtype=pl.Utf8)
        )
        edges_df = edges_df.filter(pl.col("dst_id").is_in(cred_ids))

    # optional edge types
    extra_edges: list[pl.DataFrame] = []

    if include_research and paths["research"].exists():
        res = pl.read_parquet(paths["research"])
        if year is not None:
            res = res.filter(pl.col("year") == year)
        res = res.rename({"edge_subtype": "natures"}).with_columns(
            pl.lit(0).alias("disputed_count"),
            pl.lit(False).alias("ownership_flag"),
        )
        extra_edges.append(res)

    if include_ownership and paths["ownership"].exists():
        own = pl.read_parquet(paths["ownership"])
        if year is not None:
            own = own.filter(pl.col("year") == year)
        own = own.rename({"total_value": "total_amount"}).with_columns(
            pl.lit(0, dtype=pl.UInt32).alias("payment_count"),
            pl.lit(0).alias("disputed_count"),
            pl.lit(True).alias("ownership_flag"),
            pl.lit("Manufacturer").alias("dst_type"),
            pl.lit("ownership").alias("natures"),
        )
        extra_edges.append(own)

    if extra_edges:
        edges_df = pl.concat([edges_df] + extra_edges, how="diagonal")

    # Re-aggregate across merged edge frames - must handle all new columns
    _sum_cols = ["total_amount", "payment_count", "disputed_count",
                 "delay_count", "third_party_count"]
    _any_cols = ["ownership_flag", "charity_flag"]
    _concat_cols = ["natures", "payment_forms", "active_months", "products"]

    agg_exprs = []
    for c in _sum_cols:
        if c in edges_df.columns:
            agg_exprs.append(pl.col(c).sum())
    for c in _any_cols:
        if c in edges_df.columns:
            agg_exprs.append(pl.col(c).any())
    for c in _concat_cols:
        if c in edges_df.columns:
            agg_exprs.append(
                pl.col(c).drop_nulls().str.concat("|").alias(c)
            )

    edges_df = (
        edges_df
        .group_by(["src_id", "dst_id", "year"])
        .agg(agg_exprs)
    )

    return _build_graph_from_dataframes(nodes_df, edges_df, year=year)


def load_temporal_snapshots(
    years: list[int] | None = None,
    processed_dir: str | Path | None = None,
    **load_kwargs,
) -> dict[int, GraphLensGraph]:
    """
    Load one GraphLensGraph per program year.

    Parameters
    ----------
    years         : Subset of years to load.  Defaults to all available years.
    processed_dir : Override default Parquet directory.
    **load_kwargs : Forwarded to load_graph() (specialty, state, min_amount …).

    Returns
    -------
    dict[year -> GraphLensGraph], ordered by year ascending.
    """
    target_years = years or available_years(processed_dir)
    snapshots: dict[int, GraphLensGraph] = {}
    for yr in sorted(target_years):
        try:
            snapshots[yr] = load_graph(year=yr, processed_dir=processed_dir, **load_kwargs)
        except Exception as exc:
            print(f"  WARNING: could not load year {yr}: {exc}")
    return snapshots


# Public raw-data loaders
def load_nodes(processed_dir: str | Path | None = None) -> pl.DataFrame:
    """Raw nodes Parquet as a Polars DataFrame."""
    return pl.read_parquet(_resolve_parquet_paths(processed_dir)["nodes"])


def load_edges(
    payment_type: str = "general",
    processed_dir: str | Path | None = None,
) -> pl.DataFrame:
    """Raw edges Parquet.  payment_type: 'general' | 'research' | 'ownership'."""
    paths = _resolve_parquet_paths(processed_dir)
    key_map = {"general": "general", "research": "research", "ownership": "ownership"}
    if payment_type not in key_map:
        raise ValueError(f"payment_type must be one of {list(key_map)}")
    return pl.read_parquet(paths[key_map[payment_type]])


def available_years(processed_dir: str | Path | None = None) -> list[int]:
    """Which program years have been processed and written to Parquet."""
    import re
    try:
        fp = _resolve_parquet_paths(processed_dir)["general"]
        return sorted(pl.read_parquet(fp)["year"].unique().drop_nulls().to_list())
    except FileNotFoundError:
        pass

    # Fall back: infer years from analytics_json filenames (e.g. anomaly_scores_2023.json)
    from graphlens.config import PROCESSED_DIR
    base = Path(processed_dir) if processed_dir else PROCESSED_DIR
    json_dir = base / "analytics_json"
    if json_dir.is_dir():
        years = {
            int(m.group(1))
            for f in json_dir.iterdir()
            if (m := re.search(r"_(\d{4})\.json$", f.name))
        }
        if years:
            return sorted(years)

    return []


# Internal helpers
def _build_graph_from_dataframes(
    nodes_df: pl.DataFrame,
    edges_df: pl.DataFrame,
    year: int | None = None,
) -> GraphLensGraph:
    """
    Core routine: given node and edge DataFrames (already filtered), build
    an igraph-backed GraphLensGraph.  Only nodes that appear in the edge
    list are included (orphan nodes are dropped).
    """
    if edges_df.is_empty():
        raise ValueError("Filtered edge set is empty - relax your filters.")

    # Restrict nodes to those that appear in the edge list
    edge_node_ids = pl.concat([
        edges_df["src_id"].cast(pl.Utf8).rename("id"),
        edges_df["dst_id"].cast(pl.Utf8).rename("id"),
    ]).unique()

    relevant_nodes = nodes_df.filter(
        pl.col("id").cast(pl.Utf8).is_in(edge_node_ids)
    )

    idx_map: list[str] = relevant_nodes["id"].cast(pl.Utf8).to_list()
    id_map: dict[str, int] = {v: i for i, v in enumerate(idx_map)}
    n_vertices = len(idx_map)

    G = ig.Graph(n=n_vertices, directed=True)
    G.vs["id"] = idx_map
    G.vs["node_type"] = _safe_attr(relevant_nodes, "node_type", idx_map)
    G.vs["name"] = _safe_attr(relevant_nodes, "name", idx_map)
    G.vs["state"] = _safe_attr(relevant_nodes, "state", idx_map)
    G.vs["specialty"] = _safe_attr(relevant_nodes, "specialty", idx_map)
    G.vs["specialties"] = _safe_attr(relevant_nodes, "specialties", idx_map)
    G.vs["city"] = _safe_attr(relevant_nodes, "city", idx_map)
    G.vs["zip_code"] = _safe_attr(relevant_nodes, "zip_code", idx_map)
    G.vs["country"] = _safe_attr(relevant_nodes, "country", idx_map)
    G.vs["credential_type"] = _safe_attr(relevant_nodes, "credential_type", idx_map)
    G.vs["profile_id"] = _safe_attr(relevant_nodes, "profile_id", idx_map)
    G.vs["recipient_type"] = _safe_attr(relevant_nodes, "recipient_type", idx_map)

    src_list = edges_df["src_id"].cast(pl.Utf8).to_list()
    dst_list = edges_df["dst_id"].cast(pl.Utf8).to_list()

    edge_tuples: list[tuple[int, int]] = []
    keep_mask: list[bool] = []
    for s, d in zip(src_list, dst_list):
        if s in id_map and d in id_map:
            edge_tuples.append((id_map[s], id_map[d]))
            keep_mask.append(True)
        else:
            keep_mask.append(False)

    G.add_edges(edge_tuples)
    kept = edges_df.filter(pl.Series("keep", keep_mask))

    G.es["weight"] = kept["total_amount"].to_list()
    G.es["year"] = kept["year"].cast(pl.Int32).to_list()
    G.es["payment_count"] = _safe_edge_attr(kept, "payment_count", 0, pl.Int32)
    G.es["disputed_count"] = _safe_edge_attr(kept, "disputed_count", 0, pl.Int32)
    G.es["ownership_flag"] = _safe_edge_attr(kept, "ownership_flag", False, None)
    G.es["delay_count"] = _safe_edge_attr(kept, "delay_count", 0, pl.Int32)
    G.es["third_party_count"] = _safe_edge_attr(kept, "third_party_count", 0, pl.Int32)
    G.es["charity_flag"] = _safe_edge_attr(kept, "charity_flag", False, None)
    G.es["payment_forms"] = _safe_edge_attr(kept, "payment_forms", "", None)
    G.es["products"] = _safe_edge_attr(kept, "products", "", None)
    G.es["active_months"] = _safe_edge_attr(kept, "active_months", "", None)
    G.es["natures"] = _safe_edge_attr(kept, "natures", "", None)

    return GraphLensGraph(
        ig=G,
        nodes=relevant_nodes,
        edges=kept,
        year=year,
        _id_map=id_map,
        _idx_map=idx_map,
    )


def _bipartite_project(
    glg: GraphLensGraph,
    source_type: str,
    target_type: str,
    weight_mode: str,
    max_neighbors_per_source: int | None = None,
    max_pair_updates: int | None = None,
) -> GraphLensGraph:
    """
    Generic bipartite projection.

    Given a bipartite graph where edges go source_type -> target_type,
    build an undirected weighted projection over the target_type nodes.

    Two target nodes are connected if they share at least one source node.
    Edge weight = number of shared sources (or shared total amount).
    """
    if weight_mode not in {
        "shared_companies",
        "shared_recipients",
        "shared_sources",
        "shared_amount",
    }:
        raise ValueError(
            "weight_mode must be one of "
            "['shared_companies', 'shared_recipients', 'shared_sources', 'shared_amount']"
        )

    # Build adjacency: source_id -> {target_id: aggregated_edge_weight}
    src_to_targets: dict[str, dict[str, float]] = {}
    for e in glg.ig.es:
        sv = glg.ig.vs[e.source]
        tv = glg.ig.vs[e.target]
        if sv["node_type"] == source_type and tv["node_type"] == target_type:
            s_id = sv["id"]
            t_id = tv["id"]
        elif sv["node_type"] == target_type and tv["node_type"] == source_type:
            # Handle reversed edge direction in directed bipartite graphs.
            s_id = tv["id"]
            t_id = sv["id"]
        else:
            continue

        if s_id not in src_to_targets:
            src_to_targets[s_id] = {}
        src_to_targets[s_id][t_id] = src_to_targets[s_id].get(t_id, 0.0) + float(e["weight"] or 0.0)

    if not src_to_targets:
        raise ValueError(
            f"No edges found from '{source_type}' to '{target_type}'"
        )

    # Accumulate co-occurrence counts
    from collections import defaultdict
    from itertools import combinations

    pair_count: dict[tuple[str, str], float] = defaultdict(float)

    pair_updates = 0
    sources = list(src_to_targets.items())
    # Process dense sources first so capped runs preserve strongest signal.
    sources.sort(key=lambda kv: len(kv[1]), reverse=True)

    for _, target_map in sources:
        targets = list(target_map.items())
        if max_neighbors_per_source is not None and len(targets) > max_neighbors_per_source:
            targets.sort(key=lambda x: x[1], reverse=True)
            targets = targets[:max_neighbors_per_source]

        n = len(targets)
        if n < 2:
            continue

        next_pairs = (n * (n - 1)) // 2
        if max_pair_updates is not None and pair_updates + next_pairs > max_pair_updates:
            print(
                f"  WARNING projection budget reached for {target_type} "
                f"(processed {pair_updates:,} pairs). Returning approximate projection."
            )
            break

        for (t_i, w_i), (t_j, w_j) in combinations(targets, 2):
            a, b = (t_i, t_j) if t_i <= t_j else (t_j, t_i)
            if weight_mode == "shared_amount":
                pair_count[(a, b)] += min(w_i, w_j)
            else:
                pair_count[(a, b)] += 1.0

        pair_updates += next_pairs

    if not pair_count:
        raise ValueError("Projection is empty - no shared sources between targets.")

    # Build projected node set
    target_ids_set: set[str] = {t for tgts in src_to_targets.values() for t in tgts.keys()}
    proj_nodes = glg.nodes.filter(
        pl.col("id").cast(pl.Utf8).is_in(target_ids_set)
    )
    idx_map = proj_nodes["id"].cast(pl.Utf8).to_list()
    id_map = {v: i for i, v in enumerate(idx_map)}

    G = ig.Graph(n=len(idx_map), directed=False)
    G.vs["id"] = idx_map
    G.vs["node_type"] = _safe_attr(proj_nodes, "node_type", idx_map)
    G.vs["name"] = _safe_attr(proj_nodes, "name", idx_map)
    G.vs["state"] = _safe_attr(proj_nodes, "state", idx_map)
    G.vs["specialty"] = _safe_attr(proj_nodes, "specialty", idx_map)
    G.vs["specialties"] = _safe_attr(proj_nodes, "specialties", idx_map)
    G.vs["credential_type"] = _safe_attr(proj_nodes, "credential_type", idx_map)
    G.vs["zip_code"] = _safe_attr(proj_nodes, "zip_code", idx_map)

    edge_tuples = []
    weights = []
    for (a, b), w in pair_count.items():
        if a in id_map and b in id_map:
            edge_tuples.append((id_map[a], id_map[b]))
            weights.append(w)

    G.add_edges(edge_tuples)
    G.es["weight"] = weights

    # Synthetic edge DataFrame for the projection
    proj_edges = pl.DataFrame({
        "src_id": [idx_map[e[0]] for e in edge_tuples],
        "dst_id": [idx_map[e[1]] for e in edge_tuples],
        "total_amount": weights,
        "weight": weights,
        "year": [glg.year] * len(weights),
    })

    return GraphLensGraph(
        ig=G,
        nodes=proj_nodes,
        edges=proj_edges,
        year=glg.year,
        _id_map=id_map,
        _idx_map=idx_map,
    )


def _resolve_parquet_paths(processed_dir: str | Path | None = None) -> dict[str, Path]:
    if processed_dir is None:
        from graphlens.etl import node_products_path, record_ids_path
        return {
            "nodes": nodes_path(),
            "general": edges_path(),
            "research": research_path(),
            "ownership": ownership_path(),
            "node_products": node_products_path(),
            "record_ids": record_ids_path(),
        }
    base = Path(processed_dir)
    return {
        "nodes": base / "nodes.parquet",
        "general": base / "edges_general.parquet",
        "research": base / "edges_research.parquet",
        "ownership": base / "edges_ownership.parquet",
        "node_products": base / "node_products.parquet",
        "record_ids": base / "record_ids_general.parquet",
    }


def _check_processed(nodes_fp: Path, edges_fp: Path) -> None:
    missing = [p for p in [nodes_fp, edges_fp] if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Processed Parquet files not found:\n" + "\n".join(f"  {p}" for p in missing) + "\nRun the ETL first:\n  uv run python -m graphlens.etl"
        )


def _safe_attr(df: pl.DataFrame, col: str, idx_map: list[str]) -> list:
    """Return vertex attribute list aligned to idx_map order."""
    if col not in df.columns:
        return [""] * len(idx_map)
    lookup = dict(zip(
        df["id"].cast(pl.Utf8).to_list(),
        df[col].to_list(),
    ))
    return [str(lookup.get(nid, "") or "") for nid in idx_map]


def _safe_edge_attr(
    df: pl.DataFrame,
    col_name: str,
    default,
    cast_type,
) -> list:
    """
    Return an edge attribute list from a DataFrame column.
    If the column is absent, fills with `default`.
    If cast_type is given (e.g. pl.Int32), casts before extracting.
    """
    if col_name not in df.columns:
        return [default] * len(df)
    series = df[col_name]
    if cast_type is not None:
        series = series.cast(cast_type, strict=False)
    return [v if v is not None else default for v in series.to_list()]


def load_node_products(processed_dir: str | Path | None = None) -> pl.DataFrame:
    """Drug/device product associations (node_products.parquet)."""
    fp = _resolve_parquet_paths(processed_dir)["node_products"]
    if not fp.exists():
        raise FileNotFoundError(
            f"node_products.parquet not found at {fp}\n"
            "Run the ETL first:  uv run python -m graphlens.etl"
        )
    return pl.read_parquet(fp)
