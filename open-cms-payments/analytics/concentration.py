#! usr/bin/env python3
# -*- coding: utf-8 -*-

"""
analytics.concentration
=======================
Payment concentration and market inequality metrics.

These metrics answer questions like:
  - "Is Oncology funding dominated by a few companies?"
  - "Which states show the highest payment concentration?"
  - "Has market concentration increased year-over-year?"

Metrics implemented
-------------------
  Gini coefficient   : [0, 1]  - 0 = perfectly equal, 1 = one entity gets all
  HHI                : [0, 10000] - Herfindahl-Hirschman Index (economic standard)
  CR-k               : Concentration ratio - share held by top-k entities
  Theil T            : Entropy-based inequality (sensitive to top-end)
  Normalised entropy : [0, 1] - diversity of payers; 1 = all equally funded

Public API
----------
  concentration_by_group(edges_df, group_col, amount_col, entity_col)
      -> pl.DataFrame with one row per group value

  concentration_over_time(edges_df, group_col, amount_col)
      -> pl.DataFrame with one row per (group_value, year)

  concentration_matrix(edges_df, row_col, col_col, amount_col)
      -> pl.DataFrame pivot (concentration heatmap)
"""

import math

import polars as pl  # type: ignore[import-not-found]


# Public API
def concentration_by_group(
    edges_df: pl.DataFrame,
    group_col: str,
    amount_col: str = "total_amount",
    entity_col: str = "src_id",
    top_k: int = 5,
) -> pl.DataFrame:
    """
    Compute concentration metrics for each value of group_col.

    Typical uses:
      - group_col="specialty",       entity_col="src_id"  -> company concentration per specialty
      - group_col="state",           entity_col="src_id"  -> concentration per state
      - group_col="credential_type", entity_col="src_id"  -> concentration by MD/PA/NP
      - group_col="src_id",          entity_col="dst_id"  -> physician diversity per company

    group_col may be any column on edges_df.  If it is a node attribute
    (specialty, state, credential_type, zip_code) join it onto the edges
    DataFrame first via precompute._enrich_edges_with_node_attr().

    Parameters
    ----------
    edges_df   : Edge DataFrame with group_col, amount_col, entity_col present.
    group_col  : Column to group by.
    amount_col : Payment amount column.
    entity_col : The entity whose share we measure (e.g. payer = "src_id").
    top_k      : Compute CR-k (top-k concentration ratio).

    Returns
    -------
    pl.DataFrame with columns:
        <group_col>, total_payment, n_entities,
        gini, hhi, cr_k, theil_t, norm_entropy,
        top_entity_share, dominant_entity_id
    """
    if group_col not in edges_df.columns:
        raise ValueError(f"Column '{group_col}' not found in edges_df")

    # Aggregate per (group, entity) -> payment share
    agg = (
        edges_df
        .filter(pl.col(group_col).is_not_null() & (pl.col(group_col) != ""))
        .group_by([group_col, entity_col])
        .agg(pl.col(amount_col).sum().alias("entity_amount"))
    )

    # Compute metrics per group
    groups = agg[group_col].unique().to_list()
    rows = []
    for g in groups:
        sub = agg.filter(pl.col(group_col) == g)
        amounts = sub["entity_amount"].to_list()
        entity_ids = sub[entity_col].to_list()
        if not amounts:
            continue

        total = sum(amounts)
        if total <= 0:
            continue

        gini_val = _gini(amounts)
        hhi_val = _hhi(amounts)
        crk_val = _cr_k(amounts, k=top_k)
        theil_val = _theil_t(amounts)
        entropy_val = _norm_entropy(amounts)

        # Dominant entity
        max_idx = amounts.index(max(amounts))
        top_share = amounts[max_idx] / total
        dominant_entity = entity_ids[max_idx]

        rows.append({
            group_col: g,
            "total_payment": total,
            "n_entities": len(amounts),
            "gini": round(gini_val, 4),
            "hhi": round(hhi_val, 2),
            f"cr_{top_k}": round(crk_val, 4),
            "theil_t": round(theil_val, 4),
            "norm_entropy": round(entropy_val, 4),
            "top_entity_share": round(top_share, 4),
            "dominant_entity": str(dominant_entity),
        })

    if not rows:
        return pl.DataFrame()

    return (
        pl.DataFrame(rows)
        .sort("total_payment", descending=True)
        .with_columns(pl.col("gini").cast(pl.Float64))
    )


def concentration_over_time(
    edges_df: pl.DataFrame,
    group_col: str,
    amount_col: str = "total_amount",
    entity_col: str = "src_id",
) -> pl.DataFrame:
    """
    Compute Gini and HHI for each (group_col, year) combination.

    Useful for plotting concentration trends over time:
      "Has cardiology funding become more or less concentrated since 2020?"

    Returns pl.DataFrame with columns:
        <group_col>, year, total_payment, n_entities, gini, hhi, norm_entropy
    """
    if "year" not in edges_df.columns:
        raise ValueError("edges_df must have a 'year' column")

    agg = (
        edges_df
        .filter(pl.col(group_col).is_not_null() & (pl.col(group_col) != ""))
        .group_by([group_col, "year", entity_col])
        .agg(pl.col(amount_col).sum().alias("entity_amount"))
    )

    groups = agg[[group_col, "year"]].unique().to_dicts()
    rows = []
    for gdict in groups:
        g_val = gdict[group_col]
        yr = gdict["year"]
        sub = agg.filter(
            (pl.col(group_col) == g_val) & (pl.col("year") == yr)
        )
        amounts = sub["entity_amount"].to_list()
        if not amounts:
            continue
        total = sum(amounts)
        if total <= 0:
            continue

        rows.append({
            group_col: g_val,
            "year": yr,
            "total_payment": total,
            "n_entities": len(amounts),
            "gini": round(_gini(amounts), 4),
            "hhi": round(_hhi(amounts), 2),
            "norm_entropy": round(_norm_entropy(amounts), 4),
        })

    if not rows:
        return pl.DataFrame()

    return pl.DataFrame(rows).sort([group_col, "year"])


def top_entities_by_group(
    edges_df: pl.DataFrame,
    group_col: str,
    entity_col: str = "src_id",
    amount_col: str = "total_amount",
    top_k: int = 10,
) -> pl.DataFrame:
    """
    For each group value, return the top-k entities by payment amount
    along with their share.  Useful for treemap and bar chart data.

    Returns pl.DataFrame with columns:
        <group_col>, <entity_col>, total_payment, share, rank
    """
    agg = (
        edges_df
        .filter(pl.col(group_col).is_not_null() & (pl.col(group_col) != ""))
        .group_by([group_col, entity_col])
        .agg(pl.col(amount_col).sum().alias("total_payment"))
    )

    group_totals = agg.group_by(group_col).agg(
        pl.col("total_payment").sum().alias("group_total")
    )

    return (
        agg
        .join(group_totals, on=group_col)
        .with_columns(
            (pl.col("total_payment") / pl.col("group_total")).alias("share")
        )
        .sort([group_col, "total_payment"], descending=[False, True])
        .with_columns(
            pl.int_range(pl.len()).over(group_col).alias("rank") + 1
        )
        .filter(pl.col("rank") <= top_k)
        .drop("group_total")
        .sort([group_col, "rank"])
    )


def payment_distribution_stats(
    edges_df: pl.DataFrame,
    group_col: str | None = None,
    amount_col: str = "total_amount",
) -> pl.DataFrame:
    """
    Distribution statistics (mean, median, p25, p75, p90, p99, skewness)
    optionally grouped by group_col.  Used for histogram/boxplot data.
    """
    base = (
        edges_df
        .filter(pl.col(amount_col) > 0)
        .with_columns(pl.col(amount_col).log1p().alias("log_amount"))
    )

    groupby = [group_col] if group_col and group_col in base.columns else []

    agg_exprs = [
        pl.col(amount_col).count().alias("n"),
        pl.col(amount_col).sum().alias("total"),
        pl.col(amount_col).mean().alias("mean"),
        pl.col(amount_col).median().alias("median"),
        pl.col(amount_col).quantile(0.25).alias("p25"),
        pl.col(amount_col).quantile(0.75).alias("p75"),
        pl.col(amount_col).quantile(0.90).alias("p90"),
        pl.col(amount_col).quantile(0.99).alias("p99"),
        pl.col(amount_col).max().alias("max"),
        pl.col(amount_col).std().alias("std"),
        pl.col("log_amount").mean().alias("log_mean"),
        pl.col("log_amount").std().alias("log_std"),
    ]

    if groupby:
        result = (
            base.filter(pl.col(group_col).is_not_null() & (pl.col(group_col) != ""))    # type: ignore[arg-type]
                .group_by(groupby)
                .agg(agg_exprs)
                .sort(groupby)
        )
    else:
        result = base.select(agg_exprs)

    return result


# Scalar metrics (operate on plain Python lists of positive floats)
def _gini(amounts: list[float]) -> float:
    """
    Gini coefficient via the sorted-array formula.
    Returns value in [0, 1].
    """
    n = len(amounts)
    if n == 0:
        return 0.0
    s = sorted(amounts)
    total = sum(s)
    if total == 0:
        return 0.0
    weighted_sum = 0.0
    for i, v in enumerate(s, 1):
        weighted_sum += i * v
    # Standard formula for sorted values:
    # G = (2 * sum(i*x_i) / (n * sum(x))) - (n + 1) / n
    g = (2.0 * weighted_sum) / (n * total) - (n + 1) / n
    return max(0.0, min(1.0, g))


def _hhi(amounts: list[float]) -> float:
    """
    Herfindahl-Hirschman Index (0-10000 scale).
    HHI < 1500 = competitive, 1500-2500 = moderate, > 2500 = concentrated.
    """
    total = sum(amounts)
    if total == 0:
        return 0.0
    return sum((a / total * 100) ** 2 for a in amounts)


def _cr_k(amounts: list[float], k: int = 5) -> float:
    """Top-k Concentration Ratio: share of total held by the k largest entities."""
    total = sum(amounts)
    if total == 0:
        return 0.0
    top_k_sum = sum(sorted(amounts, reverse=True)[:k])
    return top_k_sum / total


def _theil_t(amounts: list[float]) -> float:
    """
    Theil T index.  Returns 0 for perfect equality.
    More sensitive to top-end concentration than Gini.
    """
    n = len(amounts)
    if n == 0:
        return 0.0
    total = sum(amounts)
    if total == 0:
        return 0.0
    mu = total / n
    t = 0.0
    for a in amounts:
        if a > 0:
            t += (a / total) * math.log(a / mu)
    return max(t, 0.0)  # numerical clamp


def _norm_entropy(amounts: list[float]) -> float:
    """
    Shannon entropy normalised to [0, 1] by log(n).
    1 = maximum diversity (all entities share equally).
    0 = one entity holds everything.
    """
    n = len(amounts)
    if n <= 1:
        return 0.0
    total = sum(amounts)
    if total == 0:
        return 0.0
    entropy = 0.0
    for a in amounts:
        if a > 0:
            p = a / total
            entropy -= p * math.log(p)
    return entropy / math.log(n)


def payment_forms_breakdown(
    edges_df: pl.DataFrame,
    group_col: str | None = None,
    amount_col: str = "total_amount",
    forms_col: str = "payment_forms",
) -> pl.DataFrame:
    """
    Break down total payment amount by payment form (Cash, Stock, In-kind, etc.)
    optionally grouped by group_col (specialty, state, credential_type…).

    Requires the `payment_forms` column written by the new ETL.
    Each edge may have multiple pipe-joined forms; the payment amount
    is attributed to each form present on that edge.

    Returns pl.DataFrame:
        [<group_col>], form, total_amount, share
    """
    if forms_col not in edges_df.columns:
        raise ValueError(
            f"Column '{forms_col}' not found. Run the updated ETL to populate it."
        )

    # Explode pipe-joined form strings
    group_cols = [group_col] if group_col and group_col in edges_df.columns else []
    base = edges_df.select(group_cols + [forms_col, amount_col]).filter(
        pl.col(forms_col).is_not_null() & (pl.col(forms_col) != "")
    )

    # Split on | and explode
    exploded = (
        base
        .with_columns(
            pl.col(forms_col).str.split("|").alias("_form_list")
        )
        .explode("_form_list")
        .rename({"_form_list": "form"})
        .filter(pl.col("form").is_not_null() & (pl.col("form") != ""))
    )

    agg_cols = group_cols + ["form"]
    result = (
        exploded
        .group_by(agg_cols)
        .agg(pl.col(amount_col).sum().alias("total_amount"))
        .sort(agg_cols)
    )

    # Compute share within each group
    if group_cols:
        group_totals = result.group_by(group_cols).agg(
            pl.col("total_amount").sum().alias("_group_total")
        )
        result = result.join(group_totals, on=group_cols).with_columns(
            (pl.col("total_amount") / pl.col("_group_total")).alias("share")
        ).drop("_group_total")
    else:
        grand_total = result["total_amount"].sum()
        result = result.with_columns(
            (pl.col("total_amount") / grand_total).alias("share")
        )

    return result.sort("total_amount", descending=True)


def seasonality_by_month(
    edges_df: pl.DataFrame,
    group_col: str | None = None,
    amount_col: str = "total_amount",
    months_col: str = "active_months",
) -> pl.DataFrame:
    """
    Aggregate payment activity by calendar month (YYYY-MM) from the
    `active_months` pipe-joined column written by the new ETL.

    Reveals conference-season spikes, Q4 year-end pushes, and other
    seasonal payment patterns.

    Returns pl.DataFrame:
        [<group_col>], month (YYYY-MM), total_amount, n_edges
    """
    if months_col not in edges_df.columns:
        raise ValueError(
            f"Column '{months_col}' not found. Run the updated ETL to populate it."
        )

    group_cols = [group_col] if group_col and group_col in edges_df.columns else []
    base = edges_df.select(group_cols + [months_col, amount_col]).filter(
        pl.col(months_col).is_not_null() & (pl.col(months_col) != "")
    )

    exploded = (
        base
        .with_columns(
            pl.col(months_col).str.split("|").alias("_month_list")
        )
        .explode("_month_list")
        .rename({"_month_list": "month"})
        .filter(pl.col("month").is_not_null() & (pl.col("month") != ""))
    )

    agg_cols = group_cols + ["month"]
    return (
        exploded
        .group_by(agg_cols)
        .agg([
            pl.col(amount_col).sum().alias("total_amount"),
            pl.len().alias("n_edges"),
        ])
        .sort(agg_cols)
    )
