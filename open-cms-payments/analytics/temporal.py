#! usr/bin/env python3
# -*- coding: utf-8 -*-

"""
analytics.temporal
==================
Temporal analytics across multi-year Open Payments snapshots.

This module answers:
  - How do total payments and network structure evolve year-over-year?
  - Which companies/physicians are emerging (fast-rising influence)?
  - Which relationships are new vs. persistent across years?
  - How does the network's topological structure change over time?

All functions operate on a dict[year -> GraphLensGraph] from
load_temporal_snapshots(), and return Polars DataFrames.

Public API
----------
  network_evolution_metrics(snapshots)        -> pl.DataFrame  (1 row per year)
  entity_trajectory(snapshots, entity_ids)    -> pl.DataFrame  (entity x year)
  emerging_entities(snapshots, top_k)         -> pl.DataFrame  (top risers)
  relationship_persistence(snapshots)         -> pl.DataFrame  (edge stability)
  payment_flow_shifts(snapshots, group_col)   -> pl.DataFrame  (group x year)
"""

from typing import TYPE_CHECKING

import polars as pl     # type: ignore[import-not-found]
from analytics.concentration import _gini, _hhi
from analytics.centrality import compute_all_centrality

if TYPE_CHECKING:
    from graphlens.graph import GraphLensGraph


# Public API
def network_evolution_metrics(
    snapshots: "dict[int, GraphLensGraph]",
) -> pl.DataFrame:
    """
    Compute network-level metrics for each year.
    One row per year; suitable for line charts and trend analysis.

    Columns returned:
        year, n_nodes, n_edges, n_companies, n_physicians, n_npp,
        total_payment_usd, avg_payment_usd, median_payment_usd,
        cash_payment_usd, cash_share,
        disputed_payment_count, third_party_payment_count,
        density, avg_in_degree, avg_in_strength,
        gini_global, hhi_global,
        new_edges, churned_edges, persistent_edges
    """

    years = sorted(snapshots.keys())
    rows = []
    prev_edge_set: set[tuple[str, str]] | None = None

    for yr in years:
        glg = snapshots[yr]
        G = glg.ig
        n = G.vcount()
        m = G.ecount()

        weights = G.es["weight"] if m > 0 else [0.0]
        total = sum(weights)

        n_companies = sum(1 for v in G.vs if v["node_type"] == "Manufacturer")
        n_physicians = sum(1 for v in G.vs if v["node_type"] == "Physician")

        # NPP count (credential_type available from new ETL)
        n_npp = 0
        if "credential_type" in G.vs.attribute_names():
            n_npp = sum(
                1 for v in G.vs
                if v["node_type"] == "Physician" and any(
                    cred in (v["credential_type"] or "").upper()
                    for cred in ("PA", "NP", "CRNA", "CNM", "CNS")
                )
            )

        in_deg = G.degree(mode="in") if m > 0 else [0] * n
        in_str = G.strength(mode="in", weights="weight") if m > 0 else [0.0] * n
        avg_in_deg = sum(in_deg) / max(n, 1)
        avg_in_str = sum(in_str) / max(n, 1)

        max_possible = n_companies * n_physicians
        density = m / max(max_possible, 1)

        recv_totals: dict[str, float] = {}
        for e in G.es:
            dst_id = G.vs[e.target]["id"]
            recv_totals[dst_id] = recv_totals.get(dst_id, 0.0) + e["weight"]
        recv_amounts = list(recv_totals.values())
        gini = round(_gini(recv_amounts), 4) if recv_amounts else 0.0
        hhi = round(_hhi(recv_amounts), 2) if recv_amounts else 0.0

        median_pay = float(pl.Series(weights).median()) if weights else 0.0     # type: ignore[arg-type]

        # Cash / dispute / third-party totals from new edge attributes
        cash_usd = 0.0
        disputed_n = 0
        third_party_n = 0
        has_forms = "payment_forms" in G.es.attribute_names()
        has_disputed = "disputed_count" in G.es.attribute_names()
        has_third = "third_party_count" in G.es.attribute_names()
        if m > 0:
            for e in G.es:
                if has_forms and "cash" in (e["payment_forms"] or "").lower():
                    cash_usd += e["weight"]
                if has_disputed:
                    disputed_n += e["disputed_count"] or 0
                if has_third:
                    third_party_n += e["third_party_count"] or 0

        # Edge churn vs prior year
        cur_edge_set = {
            (G.vs[e.source]["id"], G.vs[e.target]["id"]) for e in G.es
        }
        new_edges: int | None
        churned_edges: int | None
        persistent_edges: int | None
        if prev_edge_set is not None:
            new_edges = len(cur_edge_set - prev_edge_set)
            churned_edges = len(prev_edge_set - cur_edge_set)
            persistent_edges = len(cur_edge_set & prev_edge_set)
        else:
            new_edges = persistent_edges = churned_edges = None
        prev_edge_set = cur_edge_set

        rows.append({
            "year": yr,
            "n_nodes": n,
            "n_edges": m,
            "n_companies": n_companies,
            "n_physicians": n_physicians,
            "n_npp": n_npp,
            "total_payment_usd": round(total, 2),
            "avg_payment_usd": round(total / max(m, 1), 2),
            "median_payment_usd": round(median_pay, 2),
            "cash_payment_usd": round(cash_usd, 2),
            "cash_share": round(cash_usd / max(total, 1e-9), 4),
            "disputed_payment_count": disputed_n,
            "third_party_payment_count": third_party_n,
            "density": round(density, 6),
            "avg_in_degree": round(avg_in_deg, 4),
            "avg_in_strength": round(avg_in_str, 2),
            "gini_global": gini,
            "hhi_global": hhi,
            "new_edges": new_edges,
            "churned_edges": churned_edges,
            "persistent_edges": persistent_edges,
        })

    return pl.DataFrame(rows).sort("year")


def entity_trajectory(
    snapshots: "dict[int, GraphLensGraph]",
    entity_ids: list[str] | None = None,
    metric: str = "in_strength",
    top_k: int = 50,
) -> pl.DataFrame:
    """
    Track a metric over time for selected entities (or top-k by last year).

    Parameters
    ----------
    snapshots   : dict[year -> GraphLensGraph]
    entity_ids  : List of string node ids to track.  If None, uses top-k
                  by the metric in the most recent year.
    metric      : "in_strength" | "out_strength" | "pagerank" | "payment_count"
    top_k       : Number of entities to include when entity_ids is None.

    Returns
    -------
    pl.DataFrame with columns:
        id, node_type, name, specialty, state, year, <metric>
    """
    # Build per-year metric tables
    year_dfs: list[pl.DataFrame] = []
    for yr in sorted(snapshots.keys()):
        glg = snapshots[yr]
        c_df = compute_all_centrality(glg, betweenness_samples=None)
        if c_df.is_empty():
            continue
        if metric not in c_df.columns:
            raise ValueError(f"Metric '{metric}' not in centrality output")
        # Include credential_type if present (new ETL field)
        extra_cols = [c for c in ("credential_type",) if c in c_df.columns]
        year_dfs.append(
            c_df.select(["id", "node_type", "name", "specialty", "state"] + extra_cols + [metric])
                .with_columns(pl.lit(yr).alias("year"))
        )

    if not year_dfs:
        return pl.DataFrame()

    all_years = pl.concat(year_dfs, how="diagonal")

    # If no ids specified, pick top-k from last year
    if entity_ids is None:
        last_yr = max(snapshots.keys())
        last_df = all_years.filter(pl.col("year") == last_yr)
        top_ids = (
            last_df.sort(metric, descending=True)
                   .head(top_k)["id"]
                   .to_list()
        )
        entity_ids = top_ids

    return (
        all_years
        .filter(pl.col("id").is_in(entity_ids))
        .sort(["id", "year"])
    )


def emerging_entities(
    snapshots: "dict[int, GraphLensGraph]",
    metric: str = "in_strength",
    top_k: int = 30,
    min_years_present: int = 2,
) -> pl.DataFrame:
    """
    Identify entities with the steepest upward trajectory in a metric.

    Uses linear slope of metric over time as the emergence signal.
    Only includes entities present in ≥ min_years_present snapshots.

    Returns pl.DataFrame:
        id, node_type, name, specialty, state,
        first_year, last_year, value_first, value_last,
        growth_factor, slope, rank
    """
    traj = entity_trajectory(
        snapshots, entity_ids=None, metric=metric, top_k=9999
    )
    if traj.is_empty():
        return pl.DataFrame()

    entity_ids = traj["id"].unique().to_list()
    rows = []
    for eid in entity_ids:
        sub = traj.filter(pl.col("id") == eid).sort("year")
        if len(sub) < min_years_present:
            continue

        years = sub["year"].to_list()
        values = sub[metric].to_list()

        # Replace nulls/zeros for stability
        values = [v if v else 0.0 for v in values]
        if sum(values) == 0:
            continue

        first_val = values[0]
        last_val = values[-1]
        if first_val <= 0:
            continue

        growth_factor = last_val / first_val
        slope = _linear_slope(years, values)

        rows.append({
            "id": eid,
            "node_type": sub["node_type"][0],
            "name": sub["name"][0],
            "specialty": sub["specialty"][0],
            "state": sub["state"][0],
            "first_year": years[0],
            "last_year": years[-1],
            "value_first": first_val,
            "value_last": last_val,
            "growth_factor": round(growth_factor, 4),
            "slope": round(slope, 6),
            "n_years": len(years),
        })

    if not rows:
        return pl.DataFrame()

    return (
        pl.DataFrame(rows)
        .sort("growth_factor", descending=True)
        .head(top_k)
        .with_row_index("rank")
        .with_columns(pl.col("rank") + 1)
    )


def relationship_persistence(
    snapshots: "dict[int, GraphLensGraph]",
) -> pl.DataFrame:
    """
    For each company–physician pair, determine across which years the
    relationship is active and compute a persistence score.

    A persistence score of 1.0 means the relationship appeared in every
    available year; 0.2 means it appeared in 1 of 5 years.

    New ETL fields carried through: ownership_flag, disputed_count,
    payment_forms (pipe-joined across years), products.

    Returns pl.DataFrame:
        src_id, dst_id, n_years_active, first_year, last_year,
        persistence_score, total_payment_usd, active_years_str,
        ever_ownership_flag, total_disputed_count,
        all_payment_forms, all_products
    """
    years = sorted(snapshots.keys())
    n_years = len(years)

    records = []
    for yr, glg in snapshots.items():
        G = glg.ig
        e_attrs = G.es.attribute_names()
        for e in G.es:
            rec = {
                "src_id": str(G.vs[e.source]["id"]),
                "dst_id": str(G.vs[e.target]["id"]),
                "year": yr,
                "amount": e["weight"],
            }
            if "ownership_flag" in e_attrs:
                rec["ownership_flag"] = e["ownership_flag"]
            if "disputed_count" in e_attrs:
                rec["disputed_count"] = e["disputed_count"] or 0
            if "payment_forms" in e_attrs:
                rec["payment_forms"] = e["payment_forms"] or ""
            if "products" in e_attrs:
                rec["products"] = e["products"] or ""
            records.append(rec)

    if not records:
        return pl.DataFrame()

    df = pl.DataFrame(records)

    agg_exprs = [
        pl.col("year").n_unique().alias("n_years_active"),
        pl.col("year").min().alias("first_year"),
        pl.col("year").max().alias("last_year"),
        pl.col("amount").sum().alias("total_payment_usd"),
        pl.col("year").cast(pl.Utf8).sort().str.join("-").alias("active_years_str"),
    ]
    if "ownership_flag" in df.columns:
        agg_exprs.append(pl.col("ownership_flag").any().alias("ever_ownership_flag"))
    if "disputed_count" in df.columns:
        agg_exprs.append(pl.col("disputed_count").sum().alias("total_disputed_count"))
    if "payment_forms" in df.columns:
        agg_exprs.append(
            pl.col("payment_forms").drop_nulls().filter(pl.col("payment_forms") != "")
              .unique().str.join("|").alias("all_payment_forms")
        )
    if "products" in df.columns:
        agg_exprs.append(
            pl.col("products").drop_nulls().filter(pl.col("products") != "")
              .unique().str.join("|").alias("all_products")
        )

    return (
        df.group_by(["src_id", "dst_id"])
          .agg(agg_exprs)
          .with_columns(
              (pl.col("n_years_active") / n_years).alias("persistence_score")).sort("total_payment_usd", descending=True)
    )


def payment_flow_shifts(
    snapshots: "dict[int, GraphLensGraph]",
    group_col: str = "specialty",
) -> pl.DataFrame:
    """
    Track total payment flow per group over time.

    group_col may be any node attribute available on recipient nodes:
    "specialty", "state", "credential_type", "zip_code".

    Returns pl.DataFrame with columns:
        <group_col>, year, total_payment_usd, n_physicians, n_companies,
        disputed_count, third_party_count,    ← new ETL signals
        yoy_change, yoy_pct_change
    """
    rows: list[pl.DataFrame] = []

    for yr, glg in snapshots.items():
        nodes = glg.nodes.with_columns(pl.col("id").cast(pl.Utf8))
        edges = glg.edges.with_columns(pl.col("dst_id").cast(pl.Utf8))

        if group_col not in nodes.columns:
            continue

        node_group = (
            nodes.filter(
                pl.col(group_col).is_not_null() & (pl.col(group_col) != "")
            ).select(["id", group_col])
             .rename({"id": "dst_id"})
        )
        enriched = edges.join(node_group, on="dst_id", how="inner")

        agg_exprs = [
            pl.col("total_amount").sum().alias("total_payment_usd"),
            pl.col("dst_id").n_unique().alias("n_physicians"),
            pl.col("src_id").n_unique().alias("n_companies"),
        ]
        if "disputed_count" in enriched.columns:
            agg_exprs.append(pl.col("disputed_count").sum().alias("disputed_count"))
        if "third_party_count" in enriched.columns:
            agg_exprs.append(pl.col("third_party_count").sum().alias("third_party_count"))

        agg = (
            enriched.group_by(group_col)
                    .agg(agg_exprs)
                    .with_columns(pl.lit(yr).alias("year"))
        )
        rows.append(agg)

    if not rows:
        return pl.DataFrame()

    combined = pl.concat(rows, how="diagonal").sort([group_col, "year"])

    combined = combined.with_columns([
        pl.col("total_payment_usd")
          .shift(1).over(group_col)
          .alias("prev_payment"),
    ]).with_columns([
        (pl.col("total_payment_usd") - pl.col("prev_payment")).alias("yoy_change"),
        pl.when(pl.col("prev_payment").is_not_null() & (pl.col("prev_payment") > 0))
          .then(
              (pl.col("total_payment_usd") - pl.col("prev_payment")) / pl.col("prev_payment"))
          .otherwise(None)
          .alias("yoy_pct_change"),
    ]).drop("prev_payment")

    return combined


def payment_form_trends(
    snapshots: "dict[int, GraphLensGraph]",
    group_col: str | None = None,
) -> pl.DataFrame:
    """
    Track how payment forms (Cash, Stock, In-kind…) shift over time
    across all years in the snapshot dict.

    Requires the `payment_forms` edge attribute written by the new ETL.

    Parameters
    ----------
    snapshots : dict[year -> GraphLensGraph]
    group_col : Optional node attribute to break down by (e.g. "specialty").
                If None, returns global year × form breakdown.

    Returns pl.DataFrame:
        year, [<group_col>], form, total_amount, share
    """
    rows: list[pl.DataFrame] = []

    for yr, glg in snapshots.items():
        G = glg.ig
        if "payment_forms" not in G.es.attribute_names():
            continue

        edges = glg.edges.with_columns(pl.col("dst_id").cast(pl.Utf8))
        if "payment_forms" not in edges.columns:
            continue

        if group_col:
            nodes = glg.nodes.with_columns(pl.col("id").cast(pl.Utf8))
            if group_col not in nodes.columns:
                continue
            node_attr = nodes.select(["id", group_col]).rename({"id": "dst_id"})
            edges = edges.join(node_attr, on="dst_id", how="left")

        # Explode pipe-joined forms
        group_cols = [group_col] if group_col and group_col in edges.columns else []
        exploded = (
            edges
            .filter(
                pl.col("payment_forms").is_not_null() & (pl.col("payment_forms") != "")
            )
            .with_columns(
                pl.col("payment_forms").str.split("|").alias("_form_list")
            )
            .explode("_form_list")
            .rename({"_form_list": "form"})
            .filter(pl.col("form").is_not_null() & (pl.col("form") != ""))
        )

        agg_cols = group_cols + ["form"]
        agg = (
            exploded
            .group_by(agg_cols)
            .agg(pl.col("total_amount").sum().alias("total_amount"))
            .with_columns(pl.lit(yr).alias("year"))
        )
        rows.append(agg)

    if not rows:
        return pl.DataFrame()

    combined = pl.concat(rows, how="diagonal")

    # Share within year (and group if set)
    share_group = ["year"] + ([group_col] if group_col else [])
    year_totals = combined.group_by(share_group).agg(
        pl.col("total_amount").sum().alias("_year_total")
    )
    return (
        combined
        .join(year_totals, on=share_group)
        .with_columns(
            (pl.col("total_amount") / pl.col("_year_total")).alias("share")
        )
        .drop("_year_total")
        .sort(share_group + ["total_amount"], descending=[*([False] * len(share_group)), True])
    )


# Internal helpers
def _linear_slope(x: list[float], y: list[float]) -> float:
    """Ordinary least-squares slope of y on x."""
    n = len(x)
    if n < 2:
        return 0.0
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    denom = sum((xi - mx) ** 2 for xi in x)
    return num / denom if denom else 0.0
