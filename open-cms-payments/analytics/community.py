#! usr/bin/env python3
# -*- coding: utf-8 -*-

"""
analytics.community
===================
Community detection for the Open Payments graph.

Strategy
--------
The raw graph is a bipartite directed graph (companies -> physicians).
Community detection is applied in two complementary ways:

  1. Bipartite Leiden (default):
     Collapse the directed bipartite graph to undirected and run
     Leiden / Louvain directly.  Communities contain a mix of companies
     and physicians that form cohesive payment ecosystems.

  2. Projection-based:
     Project onto the physician set (two physicians are linked if they
     share >=1 payer), then run Leiden on that unipartite graph.
     Communities here represent physician clusters with similar funding sources.

Both modes return consistent DataFrames so the API/frontend can choose.

Public API
----------
  detect_communities(glg, mode, resolution)  ->  (assignments_df, summary_df)
  community_summary(glg, assignments_df)  -> summary_df
"""

from typing import Literal, TYPE_CHECKING

import polars as pl     # type: ignore[import-not-found]
import igraph as ig     # type: ignore[import-untyped]
try:
    import leidenalg  # type: ignore[import-untyped]
except ImportError:
    leidenalg = None  # type: ignore[assignment]


if TYPE_CHECKING:
    from graphlens.graph import GraphLensGraph


# Public API
def detect_communities(
    glg: "GraphLensGraph",
    mode: Literal["bipartite", "physician_projection", "company_projection"] = "bipartite",
    resolution: float = 1.0,
    min_community_size: int = 3,
    projection_max_neighbors: int = 75,
    projection_max_pairs: int = 300_000,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """
    Run Leiden community detection and return assignments + per-community summary.

    Parameters
    ----------
    glg                 : GraphLensGraph to partition.
    mode                : Which graph to run detection on.
                          "bipartite"            -> undirected full graph
                          "physician_projection" -> physician co-payment unipartite
                          "company_projection"   -> company co-recipient unipartite
    resolution          : Leiden resolution parameter.  Higher = more, smaller communities.
    min_community_size  : Drop communities smaller than this.

    Returns
    -------
    (assignments_df, summary_df)

    assignments_df columns:
        id, node_type, name, state, specialty, community_id

    summary_df columns:
        community_id, size, n_companies, n_physicians,
        total_payment_usd, top_specialties, top_companies, modularity_contribution
    """
    if mode == "bipartite":
        work_glg = glg.to_undirected_weighted()
    elif mode == "physician_projection":
        work_glg = glg.project_physicians(
            max_neighbors_per_source=projection_max_neighbors,
            max_pair_updates=projection_max_pairs,
        )
    elif mode == "company_projection":
        work_glg = glg.project_companies(
            max_neighbors_per_source=max(projection_max_neighbors, 150),
            max_pair_updates=projection_max_pairs,
        )
    else:
        raise ValueError(f"Unknown mode: {mode}")

    G = work_glg.ig
    if G.vcount() == 0 or G.ecount() == 0:
        return pl.DataFrame(), pl.DataFrame()

    partition = _run_leiden(G, resolution=resolution)

    assignments_df = _build_assignments(work_glg, partition, min_community_size)
    summary_df = community_summary(glg, assignments_df)

    return assignments_df, summary_df


def community_summary(
    glg: "GraphLensGraph",
    assignments_df: pl.DataFrame,
) -> pl.DataFrame:
    """
    Build per-community summary statistics from an assignments DataFrame.

    Joins assignments back to the original graph's edge data to compute
    financial aggregates.  Uses all new ETL edge columns when present.

    Returns pl.DataFrame with columns:
        community_id, size, n_companies, n_physicians, n_hospitals,
        n_md, n_npp,                          <- credential breakdown (new)
        total_payment_usd, avg_payment_usd,
        cash_payment_usd, cash_share,         <- payment form breakdown (new)
        disputed_payment_count,               <- dispute signal (new)
        third_party_payment_count,            <- compliance signal (new)
        top_specialties, top_credential_types, top_companies
    """
    if assignments_df.is_empty():
        return pl.DataFrame()

    # Node-level counts per community
    has_cred = "credential_type" in assignments_df.columns
    base_agg = [
        pl.len().alias("size"),
        (pl.col("node_type") == "Manufacturer").sum().alias("n_companies"),
        (pl.col("node_type") == "Physician").sum().alias("n_physicians"),
        (pl.col("node_type") == "TeachingHospital").sum().alias("n_hospitals"),
    ]
    if has_cred:
        base_agg += [
            pl.col("credential_type").fill_null("").str.to_uppercase()
              .str.contains("MD|DO").sum().alias("n_md"),
            pl.col("credential_type").fill_null("").str.to_uppercase()
              .str.contains("PA|NP|CRNA|CNM|CNS").sum().alias("n_npp"),
        ]

    node_stats = assignments_df.group_by("community_id").agg(base_agg)

    # Financial aggregates via edge data
    edges = glg.edges.with_columns([
        pl.col("src_id").cast(pl.Utf8),
        pl.col("dst_id").cast(pl.Utf8),
    ])

    id_to_community = dict(zip(
        assignments_df["id"].cast(pl.Utf8).to_list(),
        assignments_df["community_id"].to_list(),
    ))

    src_communities = [id_to_community.get(s, -1) for s in edges["src_id"].to_list()]
    dst_communities = [id_to_community.get(d, -1) for d in edges["dst_id"].to_list()]
    edges_annotated = edges.with_columns(
        pl.Series("src_community", src_communities, dtype=pl.Int32),
        pl.Series("dst_community", dst_communities, dtype=pl.Int32),
    ).with_columns(
        pl.when(pl.col("dst_community") >= 0)
          .then(pl.col("dst_community"))
          .otherwise(pl.col("src_community"))
          .alias("community_id")
    ).filter(pl.col("community_id") >= 0)

    fin_agg = [
        pl.col("total_amount").sum().alias("total_payment_usd"),
        pl.col("total_amount").mean().alias("avg_payment_usd"),
    ]

    # Cash payments: requires payment_forms column from ETL
    if "payment_forms" in edges_annotated.columns:
        cash_mask = (
            edges_annotated["payment_forms"]
            .fill_null("").str.to_lowercase().str.contains("cash")
        )
        edges_annotated = edges_annotated.with_columns(
            (pl.col("total_amount") * cash_mask.cast(pl.Float64)).alias("_cash_amount")
        )
        fin_agg += [
            pl.col("_cash_amount").sum().alias("cash_payment_usd"),
        ]

    if "disputed_count" in edges_annotated.columns:
        fin_agg.append(pl.col("disputed_count").sum().alias("disputed_payment_count"))

    if "third_party_count" in edges_annotated.columns:
        fin_agg.append(pl.col("third_party_count").sum().alias("third_party_payment_count"))

    fin_stats = edges_annotated.group_by("community_id").agg(fin_agg)

    # Add cash_share
    if "cash_payment_usd" in fin_stats.columns:
        fin_stats = fin_stats.with_columns(
            (pl.col("cash_payment_usd") / (pl.col("total_payment_usd") + 1e-9))
            .alias("cash_share")
        )

    # Top specialties per community
    specialty_series = (
        assignments_df
        .filter(pl.col("node_type") == "Physician")
        .filter(pl.col("specialty").is_not_null() & (pl.col("specialty") != ""))
        .group_by(["community_id", "specialty"])
        .agg(pl.len().alias("count"))
        .sort(["community_id", "count"], descending=[False, True])
        .group_by("community_id")
        .agg(pl.col("specialty").head(3).alias("top_specialties"))
        .with_columns(pl.col("top_specialties").list.join(", "))
    )

    # Top credential types per community
    cred_series = pl.DataFrame()
    if has_cred:
        cred_series = (
            assignments_df
            .filter(
                pl.col("credential_type").is_not_null() & (pl.col("credential_type") != "")
            )
            .group_by(["community_id", "credential_type"])
            .agg(pl.len().alias("count"))
            .sort(["community_id", "count"], descending=[False, True])
            .group_by("community_id")
            .agg(pl.col("credential_type").head(3).alias("top_credential_types"))
            .with_columns(pl.col("top_credential_types").list.join(", "))
        )

    # Top companies per community
    company_series = (
        assignments_df
        .filter(pl.col("node_type") == "Manufacturer")
        .filter(pl.col("name").is_not_null() & (pl.col("name") != ""))
        .group_by(["community_id", "name"])
        .agg(pl.len().alias("count"))
        .sort(["community_id", "count"], descending=[False, True])
        .group_by("community_id")
        .agg(pl.col("name").head(3).alias("top_companies"))
        .with_columns(pl.col("top_companies").list.join(", "))
    )

    summary = (
        node_stats
        .join(fin_stats, on="community_id", how="left")
        .join(specialty_series, on="community_id", how="left")
        .join(company_series, on="community_id", how="left")
    )
    if not cred_series.is_empty():
        summary = summary.join(cred_series, on="community_id", how="left")

    return summary.sort("total_payment_usd", descending=True, nulls_last=True)


# Internal helpers
def _run_leiden(G: ig.Graph, resolution: float = 1.0) -> list[int]:
    """
    Run Leiden community detection via leidenalg if available,
    falling back to igraph's Louvain.

    Returns a list mapping vertex index -> community id.
    """
    try:
        if leidenalg is not None:
            # leidenalg works with python-igraph Graph objects
            partition = leidenalg.find_partition(
                G,
                leidenalg.RBConfigurationVertexPartition,
                weights="weight",
                resolution_parameter=resolution,
                seed=69,
            )
            return list(partition.membership)

        # Fall back to igraph's built-in Louvain / community_multilevel
        partition = G.community_multilevel(
            weights="weight" if G.ecount() > 0 else None,
            return_levels=False,
        )
        return list(partition.membership)

    except Exception as exc:
        print(f"  WARNING community detection failed ({exc}), using greedy modularity")
        partition = G.community_fastgreedy(
            weights="weight" if G.ecount() > 0 else None,
        ).as_clustering()
        return list(partition.membership)


def _build_assignments(
    glg: "GraphLensGraph",
    membership: list[int],
    min_community_size: int,
) -> pl.DataFrame:
    """
    Build the assignments DataFrame from igraph membership list.
    Communities smaller than min_community_size are labelled -1 (noise).
    Includes all new node attributes from the updated ETL/graph loader.
    """
    G = glg.ig
    v_attrs = G.vs.attribute_names()

    base = {
        "id": G.vs["id"],
        "node_type": G.vs["node_type"],
        "name": G.vs["name"],
        "state": G.vs["state"],
        "specialty": G.vs["specialty"],
        "community_id": membership,
    }
    # New ETL node fields - include if present on the igraph vertex set
    for attr in ("credential_type", "zip_code", "specialties", "recipient_type"):
        if attr in v_attrs:
            base[attr] = G.vs[attr]

    raw_df = pl.DataFrame(base).with_columns(
        pl.col("community_id").cast(pl.Int32)
    )

    # Drop communities below min size -> label -1
    sizes = raw_df.group_by("community_id").agg(pl.len().alias("size"))
    raw_df = (
        raw_df.join(sizes, on="community_id", how="left")
              .with_columns(
                  pl.when(pl.col("size") < min_community_size)
                  .then(pl.lit(-1))
                  .otherwise(pl.col("community_id"))
                  .alias("community_id")).drop("size")
    )

    # Renumber surviving communities 0..N-1 by descending size
    valid_communities = (
        raw_df
        .filter(pl.col("community_id") >= 0)
        .group_by("community_id")
        .agg(pl.len().alias("size"))
        .sort("size", descending=True)
        .with_row_index("new_id")
        .select(["community_id", "new_id"])
    )
    old_to_new = dict(zip(
        valid_communities["community_id"].to_list(),
        valid_communities["new_id"].to_list(),
    ))
    new_ids = [
        old_to_new.get(c, -1) if c >= 0 else -1
        for c in raw_df["community_id"].to_list()
    ]
    return raw_df.with_columns(
        pl.Series("community_id", new_ids, dtype=pl.Int32)
    )
