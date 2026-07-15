#! usr/bin/env python3
# -*- coding: utf-8 -*-

"""
analytics.anomaly
=================
Anomaly and outlier detection for the Open Payments graph.

Approach
--------
We combine two complementary anomaly signals:

  1. **Financial outliers** (statistical)
     - Log-transform total_amount and compute z-scores within peer group
       (specialty x state, or specialty alone).
     - Flag physicians in the top-2.5% of z-score within their group.

  2. **Structural anomalies** (graph-based)
     - High PageRank but unusually low payment diversity
       ("captured physician": one company dominates their income)
     - High PageRank but sudden year-over-year payment jump
       ("emerging star": sudden influence spike)
     - Bridge nodes: top betweenness but neither largest payer nor largest receiver
       ("structural broker")

Both signals are combined into a composite anomaly_score ∈ [0, 1].
We deliberately avoid hard labels to prevent misuse; the UI surfaces
degree rather than binary classification.

Public API
----------
  compute_anomaly_scores(glg, centrality_df, year)      -> pl.DataFrame
  detect_sudden_jumps(snapshots, min_jump_factor)        -> pl.DataFrame
  company_physician_capture(glg, centrality_df)          -> pl.DataFrame
"""

from typing import TYPE_CHECKING

import polars as pl     # type: ignore[import-not-found]
from analytics.centrality import compute_degree_strength, compute_pagerank

if TYPE_CHECKING:
    from graphlens.graph import GraphLensGraph


# Public API
def compute_anomaly_scores(
    glg: "GraphLensGraph",
    centrality_df: pl.DataFrame,
    zscore_threshold: float = 2.0,
) -> pl.DataFrame:
    """
    Compute per-node anomaly scores combining financial and structural signals.

    Parameters
    ----------
    glg               : GraphLensGraph (for edge data and node metadata).
    centrality_df     : Output of analytics.centrality.compute_all_centrality().
                        Must include cash_ratio, disputed_ratio, third_party_ratio
                        columns produced by the updated centrality module.
    zscore_threshold  : Z-score threshold for marking financial outliers.

    Returns
    -------
    pl.DataFrame with columns:
        id, node_type, name, state, specialty, credential_type,
        in_strength, pagerank, payment_diversity,
        zscore_within_specialty, zscore_within_state, zscore_global,
        is_financial_outlier,
        capture_ratio,
        cash_ratio,            ← share of income that is cash payments
        third_party_ratio,     ← share routed via third-party entities
        disputed_ratio,        ← share of payments under dispute
        structural_anomaly,
        composite_anomaly_score
    """
    if centrality_df.is_empty():
        return pl.DataFrame()

    phys = centrality_df.filter(pl.col("node_type") == "Physician")

    if phys.is_empty():
        return _add_zero_anomaly_cols(centrality_df)

    # z-scores on log_in_strength
    phys = _add_zscores(phys, value_col="log_in_strength", group_col="specialty",
                        out_col="zscore_within_specialty")
    phys = _add_zscores(phys, value_col="log_in_strength", group_col="state",
                        out_col="zscore_within_state")

    # z-score by credential_type too - NPPs vs MDs have different payment scales
    if "credential_type" in phys.columns:
        phys = _add_zscores(phys, value_col="log_in_strength",
                            group_col="credential_type",
                            out_col="zscore_within_credential")
    else:
        phys = phys.with_columns(pl.lit(0.0).alias("zscore_within_credential"))

    phys = _add_zscores_global(phys, value_col="log_in_strength",
                               out_col="zscore_global")

    phys = phys.with_columns(
        (
            (pl.col("zscore_within_specialty").abs() > zscore_threshold) | (pl.col("zscore_global").abs() > zscore_threshold)
        ).alias("is_financial_outlier")
    )

    # capture ratio
    capture = _compute_capture_ratio(glg)
    phys = phys.join(capture, on="id", how="left").with_columns(
        pl.col("capture_ratio").fill_null(0.0)
    )

    # structural anomaly
    pr_q75 = phys["pagerank"].quantile(0.75) or 0.0
    div_q25 = phys["payment_diversity"].quantile(0.25) or 0.0
    cap_q75 = phys["capture_ratio"].quantile(0.75) or 0.0

    phys = phys.with_columns(
        (
            (pl.col("pagerank") > pr_q75) & (pl.col("payment_diversity") <= div_q25) & (pl.col("capture_ratio") >= cap_q75)
        ).alias("structural_anomaly")
    )

    # ensure new signal columns exist (may be absent on older centrality output)
    for col_name in ["cash_ratio", "disputed_ratio", "third_party_ratio"]:
        if col_name not in phys.columns:
            phys = phys.with_columns(pl.lit(0.0).alias(col_name))

    phys = phys.with_columns([
        pl.col("zscore_within_specialty").fill_null(0.0),
        pl.col("zscore_global").fill_null(0.0),
        pl.col("cash_ratio").fill_null(0.0),
        pl.col("disputed_ratio").fill_null(0.0),
        pl.col("third_party_ratio").fill_null(0.0),
    ])

    # composite anomaly score [0, 1]
    # Weights:
    #   0.30 normalised |z-score| (financial outlier signal)
    #   0.20 capture ratio         (single-payer dominance)
    #   0.15 structural flag       (high-PR + low diversity)
    #   0.15 third_party_ratio     (compliance red flag)
    #   0.10 cash_ratio            (direct influence signal)
    #   0.10 disputed_ratio        (dispute flag density)
    max_z = phys["zscore_global"].abs().max() or 1.0
    phys = phys.with_columns(
        (
            0.30 * (pl.col("zscore_global").abs() / max_z) + 0.20 * pl.col("capture_ratio") + 0.15 * pl.col("structural_anomaly").cast(pl.Float64) + 0.15 * pl.col("third_party_ratio") + 0.10 * pl.col("cash_ratio") + 0.10 * pl.col("disputed_ratio")
        ).clip(0.0, 1.0).alias("composite_anomaly_score")
    )

    non_phys = _add_zero_anomaly_cols(
        centrality_df.filter(pl.col("node_type") != "Physician")
    )
    return pl.concat([phys, non_phys], how="diagonal").sort(
        "composite_anomaly_score", descending=True
    )


def detect_sudden_jumps(
    snapshots: "dict[int, GraphLensGraph]",
    min_jump_factor: float = 3.0,
    metric: str = "in_strength",
) -> pl.DataFrame:
    """
    Detect entities whose payment metric increased by ≥ min_jump_factor
    between consecutive years.

    Parameters
    ----------
    snapshots        : dict[year -> GraphLensGraph] from load_temporal_snapshots().
    min_jump_factor  : Flag if new_value / old_value ≥ this.
    metric           : Which metric to compare: "in_strength" | "pagerank".

    Returns
    -------
    pl.DataFrame with columns:
        id, node_type, name, specialty, state,
        year_from, year_to, value_from, value_to, jump_factor
    """
    year_metrics: dict[int, pl.DataFrame] = {}
    for yr, glg in sorted(snapshots.items()):
        if metric == "in_strength":
            df = compute_degree_strength(glg).select(
                ["id", "node_type", "in_strength"]
            ).rename({"in_strength": "value"})
        elif metric == "pagerank":
            df = compute_pagerank(glg).select(
                ["id", "node_type", "pagerank"]
            ).rename({"pagerank": "value"})
        else:
            raise ValueError(f"Unknown metric: {metric}")
        year_metrics[yr] = df

    years = sorted(year_metrics)
    rows = []
    for i in range(1, len(years)):
        yr_from = years[i - 1]
        yr_to = years[i]
        df_from = year_metrics[yr_from].rename({"value": "value_from"})
        df_to = year_metrics[yr_to].rename({"value": "value_to"})

        joined = df_from.join(df_to, on=["id", "node_type"], how="inner")
        jumps = joined.filter(
            (pl.col("value_from") > 0) & (pl.col("value_to") / pl.col("value_from") >= min_jump_factor)
        ).with_columns([
            pl.lit(yr_from).alias("year_from"),
            pl.lit(yr_to).alias("year_to"),
            (pl.col("value_to") / pl.col("value_from")).alias("jump_factor"),
        ])
        rows.append(jumps)

    if not rows:
        return pl.DataFrame()

    # Enrich with node metadata from the most recent snapshot
    last_glg = snapshots[max(snapshots)]
    node_meta = last_glg.nodes.select(
        [c for c in ["id", "name", "specialty", "state"] if c in last_glg.nodes.columns]
    ).with_columns(pl.col("id").cast(pl.Utf8))

    result = (
        pl.concat(rows, how="diagonal")
        .with_columns(pl.col("id").cast(pl.Utf8))
        .join(node_meta, on="id", how="left")
        .sort("jump_factor", descending=True)
    )
    return result


def company_physician_capture(
    glg: "GraphLensGraph",
    centrality_df: pl.DataFrame,
    capture_threshold: float = 0.8,
) -> pl.DataFrame:
    """
    Identify company-physician pairs where a single company accounts for
    ≥ capture_threshold of a physician's total income.

    This surfaces potential "captured physicians" - those whose prescribing
    decisions could be significantly influenced by a single industry payer.

    Returns pl.DataFrame:
        physician_id, company_id, company_name,
        physician_name, specialty, state,
        company_payment, total_physician_payment,
        capture_ratio, physician_pagerank
    """
    edges = glg.edges
    if edges.is_empty():
        return pl.DataFrame()

    # Total income per physician
    phys_totals = (
        edges
        .group_by("dst_id")
        .agg(pl.col("total_amount").sum().alias("total_income"))
    )

    # Per (company, physician) payment
    pair_totals = (
        edges
        .group_by(["src_id", "dst_id"])
        .agg(pl.col("total_amount").sum().alias("pair_amount"))
    )

    # Capture ratio
    capture_df = (
        pair_totals
        .join(phys_totals, on="dst_id")
        .with_columns(
            (pl.col("pair_amount") / pl.col("total_income")).alias("capture_ratio")
        )
        .filter(pl.col("capture_ratio") >= capture_threshold)
    )

    if capture_df.is_empty():
        return pl.DataFrame()

    # Enrich with node metadata
    nodes = glg.nodes.with_columns(pl.col("id").cast(pl.Utf8))
    phys_meta = nodes.filter(pl.col("node_type") == "Physician").select(
        ["id", "name", "specialty", "state"]
    ).rename({"id": "dst_id", "name": "physician_name"})
    comp_meta = nodes.filter(pl.col("node_type") == "Manufacturer").select(
        ["id", "name"]
    ).rename({"id": "src_id", "name": "company_name"})

    # Add PageRank
    pr_df = centrality_df.select(["id", "pagerank"]).rename(
        {"id": "dst_id", "pagerank": "physician_pagerank"}
    )

    return (
        capture_df
        .with_columns([
            pl.col("src_id").cast(pl.Utf8),
            pl.col("dst_id").cast(pl.Utf8),
        ])
        .join(phys_meta, on="dst_id", how="left")
        .join(comp_meta, on="src_id", how="left")
        .join(pr_df, on="dst_id", how="left")
        .rename({
            "dst_id": "physician_id",
            "src_id": "company_id",
            "pair_amount": "company_payment",
            "total_income": "total_physician_payment",
        })
        .sort("capture_ratio", descending=True)
        .select([
            "physician_id", "company_id", "company_name",
            "physician_name", "specialty", "state",
            "company_payment", "total_physician_payment",
            "capture_ratio", "physician_pagerank",
        ])
    )


# Internal helpers
def _add_zero_anomaly_cols(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns([
        pl.lit(0.0).alias("zscore_within_specialty"),
        pl.lit(0.0).alias("zscore_within_state"),
        pl.lit(0.0).alias("zscore_within_credential"),
        pl.lit(0.0).alias("zscore_global"),
        pl.lit(False).alias("is_financial_outlier"),
        pl.lit(0.0).alias("capture_ratio"),
        pl.lit(0.0).alias("cash_ratio"),
        pl.lit(0.0).alias("third_party_ratio"),
        pl.lit(0.0).alias("disputed_ratio"),
        pl.lit(False).alias("structural_anomaly"),
        pl.lit(0.0).alias("composite_anomaly_score"),
    ])


def _add_zscores(
    df: pl.DataFrame,
    value_col: str,
    group_col: str,
    out_col: str,
    min_group_size: int = 5,
) -> pl.DataFrame:
    """
    Add z-score column computed within each group.
    Groups smaller than min_group_size get z-score = 0.
    """
    if group_col not in df.columns:
        return df.with_columns(pl.lit(0.0).alias(out_col))

    df = df.with_columns([
        pl.col(value_col).fill_nan(0.0).fill_null(0.0),
    ])

    return df.with_columns(
        pl.when(pl.count(value_col).over(group_col) >= min_group_size)
        .then(
            (
                pl.col(value_col) - pl.col(value_col).mean().over(group_col)
            ) / (pl.col(value_col).std().over(group_col) + 1e-9)
        )
        .otherwise(pl.lit(0.0))
        .alias(out_col)
    )


def _add_zscores_global(
    df: pl.DataFrame,
    value_col: str,
    out_col: str,
) -> pl.DataFrame:
    """Global z-score across the entire physician set."""
    df = df.with_columns(pl.col(value_col).fill_nan(0.0).fill_null(0.0))
    mean = df[value_col].mean() or 0.0
    std = df[value_col].std() or 1.0
    # Ensure std is numeric to avoid timedelta arithmetic errors
    std = float(std) if std is not None else 1.0    # type: ignore[arg-type]
    return df.with_columns(
        ((pl.col(value_col) - mean) / (std + 1e-9)).alias(out_col)
    )


def _compute_capture_ratio(glg: "GraphLensGraph") -> pl.DataFrame:
    """
    For each physician: what fraction of their total income came from
    the single largest payer?  Returns DataFrame (id, capture_ratio).
    """
    edges = glg.edges
    if edges.is_empty():
        return pl.DataFrame({"id": [], "capture_ratio": []})

    phys_totals = (
        edges
        .group_by("dst_id")
        .agg(pl.col("total_amount").sum().alias("total_income"))
    )
    pair_max = (
        edges
        .group_by(["src_id", "dst_id"])
        .agg(pl.col("total_amount").sum().alias("pair_amount"))
        .group_by("dst_id")
        .agg(pl.col("pair_amount").max().alias("max_single_company"))
    )

    return (
        phys_totals
        .join(pair_max, on="dst_id")
        .with_columns(
            (pl.col("max_single_company") / pl.col("total_income")).alias("capture_ratio")
        )
        .rename({"dst_id": "id"})
        .select(["id", "capture_ratio"])
        .with_columns(pl.col("id").cast(pl.Utf8))
    )
