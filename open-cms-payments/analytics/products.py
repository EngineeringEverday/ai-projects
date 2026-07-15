#! usr/bin/env python3
# -*- coding: utf-8 -*-

"""
analytics.products
==================
Drug, biological, and device product-level payment analytics.

These analytics require the node_products.parquet file written by the
ETL's _extract_products() function.  They answer:
  - Which drugs/devices drive the most total payments?
  - Which physicians receive the most payments associated with a given drug?
  - Which companies dominate payments for a given drug or therapeutic area?
  - Is a physician's payment profile concentrated on one product or diversified?

Public API
----------
  top_products_global(year)                -> pl.DataFrame
  product_concentration_by_physician(...)  -> pl.DataFrame
  product_network(product_name, year)      -> pl.DataFrame (edge list for subgraph)
  physician_product_diversity(edges_df)    -> pl.DataFrame
"""

from pathlib import Path

import polars as pl     # type: ignore[import-not-found]

from graphlens.config import PROCESSED_DIR


def _products_path() -> Path:
    return PROCESSED_DIR / "node_products.parquet"


def _edges_path() -> Path:
    return PROCESSED_DIR / "edges_general.parquet"


def _nodes_path() -> Path:
    return PROCESSED_DIR / "nodes.parquet"


# Public API
def top_products_global(
    year: int | None = None,
    product_type: str = "drug",
    top_k: int = 50,
) -> pl.DataFrame:
    """
    Top drugs or devices by total payment amount (via product-tagged edge records).

    Because product association is stored in node_products.parquet (one row per
    record_id × product slot), and the edge-level totals are in edges_general
    (aggregated), we approximate product-level totals by counting how many
    records mention each product and joining to average edge weights.

    Returns pl.DataFrame:
        product_name, product_type, n_records, n_physicians, n_companies,
        year (if year arg provided)
    """
    if not _products_path().exists():
        raise FileNotFoundError(
            "node_products.parquet not found. Run the ETL first."
        )

    prod = pl.read_parquet(_products_path())
    prod = prod.filter(pl.col("product_type") == product_type)

    if year is not None:
        prod = prod.filter(pl.col("year") == year)

    result = (
        prod
        .group_by("product_name")
        .agg([
            pl.len().alias("n_records"),
            pl.col("year").n_unique().alias("n_years"),
        ])
        .sort("n_records", descending=True)
        .head(top_k)
    )

    return result


def product_payment_trends(
    product_name: str,
    product_type: str = "drug",
) -> pl.DataFrame:
    """
    Year-over-year record count for a specific product.
    Useful for line charts showing product activity trends.

    Returns pl.DataFrame: product_name, year, n_records
    """
    if not _products_path().exists():
        raise FileNotFoundError("node_products.parquet not found.")

    prod = pl.read_parquet(_products_path())
    return (
        prod
        .filter(
            (pl.col("product_type") == product_type) & pl.col("product_name").str.to_uppercase().str.contains(product_name.upper(), literal=True)
        )
        .group_by(["product_name", "year"])
        .agg(pl.len().alias("n_records"))
        .sort(["product_name", "year"])
    )


def physician_product_diversity(
    edges_df: pl.DataFrame,
    product_col: str = "products",
    top_k: int | None = None,
) -> pl.DataFrame:
    """
    For each physician (dst_id), compute how many distinct products appear
    in their payment records.  Physicians with very low product diversity
    but high total payments may be excessively focused on one drug/device.

    Parameters
    ----------
    edges_df    : General payment edges DataFrame (from edges_general.parquet).
    product_col : Column containing pipe-joined product names.
    top_k       : Return only top-k physicians by payment (None = all).

    Returns pl.DataFrame:
        dst_id, total_payment, n_product_mentions, distinct_products,
        product_diversity_score  ∈ [0, 1]
    """
    if product_col not in edges_df.columns:
        raise ValueError(f"Column '{product_col}' not found in edges_df")

    # Prefer explicit edge typing when available; otherwise infer physician
    # recipients from nodes.parquet so this works with lean edge schemas.
    if "dst_type" in edges_df.columns:
        phys_edges = edges_df.filter(pl.col("dst_type") == "Physician")
    elif _nodes_path().exists():
        nodes = pl.read_parquet(_nodes_path())
        if {"id", "node_type"}.issubset(set(nodes.columns)):
            physician_ids = (
                nodes.filter(pl.col("node_type") == "Physician")
                .select(pl.col("id").cast(pl.Utf8).alias("id"))
            )
            phys_edges = edges_df.with_columns(
                pl.col("dst_id").cast(pl.Utf8)
            ).join(
                physician_ids.rename({"id": "dst_id"}),
                on="dst_id",
                how="inner",
            )
        else:
            phys_edges = edges_df
    else:
        phys_edges = edges_df

    if top_k:
        phys_totals = (
            phys_edges.group_by("dst_id")
            .agg(pl.col("total_amount").sum())
            .sort("total_amount", descending=True)
            .head(top_k)
        )
        phys_edges = phys_edges.filter(
            pl.col("dst_id").is_in(phys_totals["dst_id"])
        )

    # Explode pipe-joined products into individual rows
    prod_exploded = (
        phys_edges
        .filter(
            pl.col(product_col).is_not_null() & (pl.col(product_col) != "")
        )
        .with_columns(
            pl.col(product_col).str.split("|").alias("product_list")
        )
        .explode("product_list")
        .filter(
            pl.col("product_list").is_not_null() & (pl.col("product_list") != "")
        )
        .rename({"product_list": "product_name"})
    )

    # Per-physician product stats
    prod_stats = (
        prod_exploded
        .group_by("dst_id")
        .agg([
            pl.col("product_name").n_unique().alias("distinct_products"),
            pl.len().alias("n_product_mentions"),
        ])
    )

    phys_totals_all = (
        phys_edges.group_by("dst_id")
                  .agg(pl.col("total_amount").sum().alias("total_payment"))
    )

    result = phys_totals_all.join(prod_stats, on="dst_id", how="left").with_columns([
        pl.col("distinct_products").fill_null(0),
        pl.col("n_product_mentions").fill_null(0),
    ])

    # Normalise diversity to [0,1] using log scale
    max_prod = result["distinct_products"].max() or 1
    denom = float(pl.Series([max_prod]).log1p()[0])
    denom = denom if denom > 0 else 1.0
    result = result.with_columns(
        (pl.col("distinct_products").log1p() / denom)
        .clip(0.0, 1.0)
        .alias("product_diversity_score")
    )

    return result.sort("total_payment", descending=True)


def ndc_lookup(ndc_prefix: str) -> pl.DataFrame:
    """
    Find all product names associated with an NDC prefix.
    Useful for linking NDC codes to drug names across payment records.
    """
    if not _products_path().exists():
        raise FileNotFoundError("node_products.parquet not found.")

    prod = pl.read_parquet(_products_path())
    return (
        prod
        .filter(
            pl.col("ndc").is_not_null() & pl.col("ndc").str.starts_with(ndc_prefix)
        )
        .select(["ndc", "product_name"])
        .unique()
        .sort("ndc")
    )
