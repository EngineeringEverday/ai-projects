#! usr/bin/env python3
# -*- coding: utf-8 -*-

"""
analytics.precompute
====================
Master analytics orchestrator.

This module is the **scalability boundary** between the heavy Python
analytics layer and the FastAPI serving layer.  Run it once (or nightly)
to precompute all graph analytics across all years and save the results
as compressed Parquet files.  The API then reads these lightweight files
directly - no graph loading or computation at request time.

Output files  (written to PROCESSED_DIR/analytics/)
----------------------------------------------------
  node_metrics_{year}.parquet          - per-node centrality + new ETL signals
    community_assignments_{year}.parquet - bipartite community membership per node
    community_summaries_{year}.parquet   - bipartite per-community aggregates
    community_assignments_{mode}_{year}.parquet  - all community modes
    community_summaries_{mode}_{year}.parquet    - all community modes
  concentration_specialty_{year}.parquet
  concentration_state_{year}.parquet
  concentration_credential_{year}.parquet  <- NEW: MD vs NPP concentration
    payment_distribution_{scope}_{year}.parquet  <- NEW: histogram/boxplot stats
  payment_forms_{year}.parquet             <- NEW: Cash/Stock/In-kind breakdown
  seasonality_{year}.parquet               <- NEW: YYYY-MM payment activity
  top_entities_specialty_{year}.parquet
    top_entities_state_{year}.parquet
    top_entities_credential_{year}.parquet
    top_products_drug_{year}.parquet
    top_products_device_{year}.parquet
    physician_product_diversity_{year}.parquet
  anomaly_scores_{year}.parquet
  capture_analysis_{year}.parquet
  temporal_evolution.parquet           - network-level metrics per year
    emerging_entities.parquet            - backward-compatible alias (in_strength)
    emerging_entities_in_strength.parquet
    emerging_entities_pagerank.parquet
    entity_trajectory_in_strength.parquet
    entity_trajectory_pagerank.parquet
    sudden_jumps_in_strength.parquet
    sudden_jumps_pagerank.parquet
  relationship_persistence.parquet
  payment_flow_specialty.parquet
  payment_flow_state.parquet
  payment_flow_credential.parquet      <- NEW: flow by credential type
    payment_form_trends.parquet          <- NEW: Cash/Stock/In-kind share over years (global)
    payment_form_trends_specialty.parquet
    payment_form_trends_state.parquet
    payment_form_trends_credential.parquet
  all_*.parquet                        - consolidated multi-year files

Usage
-----
  uv run python -m analytics.precompute              # all years
  uv run python -m analytics.precompute --year 2023  # single year
"""

import argparse
import time
from typing import Literal

import polars as pl     # type: ignore[import-not-found]

from graphlens.config import PROCESSED_DIR
from graphlens.graph import load_graph, load_temporal_snapshots, available_years, GraphLensGraph


# Output directory
ANALYTICS_DIR = PROCESSED_DIR / "analytics"
ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)


def _save(df: pl.DataFrame, name: str) -> None:
    """Save a DataFrame to parquet with compression."""
    if df is None or df.is_empty():
        print(f"    {name}: empty - skipped")
        return
    path = ANALYTICS_DIR / name
    df.write_parquet(path, compression="zstd")
    size_kb = path.stat().st_size // 1024
    print(f"    {name}: {len(df):,} rows  ({size_kb} KB)")


def _timer(label: str):
    """Simple context manager that prints elapsed time."""
    class _T:
        def __enter__(self):
            self._t = time.perf_counter()
            return self

        def __exit__(self, *_):
            elapsed = time.perf_counter() - self._t
            print(f"    └─ {elapsed:.1f}s")
    print(f"  ▶ {label}")
    return _T()


# Per-year analytics
def run_year(
    year: int,
    betweenness_samples: int = 150,
) -> None:
    """Run all analytics for a single program year."""
    from analytics.centrality import compute_all_centrality
    from analytics.community import detect_communities
    from analytics.concentration import (
        top_entities_by_group,
        payment_distribution_stats,
        payment_forms_breakdown,
        seasonality_by_month,
    )
    from analytics.anomaly import (
        compute_anomaly_scores,
        company_physician_capture,
    )
    from analytics.products import (
        top_products_global,
        physician_product_diversity,
    )
    print(f"  Year: {year}")
    glg = load_graph(year=year, min_amount=1.0)
    print(f"  Graph: {glg}")
    suffix = f"_{year}"

    # Centrality
    with _timer("Centrality"):
        c_df = compute_all_centrality(glg, betweenness_samples=betweenness_samples)
        c_df = c_df.with_columns(pl.lit(year).alias("year"))
    _save(c_df, f"node_metrics{suffix}.parquet")

    # Community detection (all modes)
    with _timer("Community detection"):
        community_modes: list[
            Literal["bipartite", "physician_projection", "company_projection"]
        ] = [
            "bipartite",
            "physician_projection",
            "company_projection",
        ]
        for mode in community_modes:
            try:
                print(f"    mode={mode} ...")
                assign_df, summary_df = detect_communities(
                    glg, mode=mode, resolution=1.0
                )
                if not assign_df.is_empty():
                    assign_df = assign_df.with_columns(pl.lit(year).alias("year"))
                    summary_df = summary_df.with_columns(pl.lit(year).alias("year"))
            except Exception as exc:
                print(f"    WARNING {mode}: {exc}")
                assign_df, summary_df = pl.DataFrame(), pl.DataFrame()

            mode_suffix = f"_{mode}"
            _save(assign_df, f"community_assignments{mode_suffix}{suffix}.parquet")
            _save(summary_df, f"community_summaries{mode_suffix}{suffix}.parquet")

            # Backward-compatible names keep bipartite mode as the default output.
            if mode == "bipartite":
                _save(assign_df, f"community_assignments{suffix}.parquet")
                _save(summary_df, f"community_summaries{suffix}.parquet")

    # Enrich edges with node attributes (reused across blocks)
    edges_with_spec = _enrich_edges_with_node_attr(glg, "specialty")
    edges_with_state = _enrich_edges_with_node_attr(glg, "state")
    edges_with_cred = _enrich_edges_with_node_attr(glg, "credential_type")

    # Concentration by specialty
    with _timer("Concentration by specialty"):
        conc_spec = _safe_concentration(
            edges_with_spec, group_col="specialty", year=year
        )
    _save(conc_spec, f"concentration_specialty{suffix}.parquet")

    # Concentration by state
    with _timer("Concentration by state"):
        conc_state = _safe_concentration(
            edges_with_state, group_col="state", year=year
        )
    _save(conc_state, f"concentration_state{suffix}.parquet")

    # Concentration by credential type (MD vs PA/NP)
    with _timer("Concentration by credential type"):
        conc_cred = _safe_concentration(
            edges_with_cred, group_col="credential_type", year=year
        )
    _save(conc_cred, f"concentration_credential{suffix}.parquet")

    # Payment forms breakdown (Cash / Stock / In-kind …)
    with _timer("Payment forms breakdown"):
        try:
            forms_df = payment_forms_breakdown(
                glg.edges, group_col=None
            ).with_columns(pl.lit(year).alias("year"))
            forms_spec = payment_forms_breakdown(
                edges_with_spec, group_col="specialty"
            ).with_columns(pl.lit(year).alias("year"))
            forms_combined = pl.concat([forms_df, forms_spec], how="diagonal")
        except Exception as exc:
            print(f"    WARNING: {exc}")
            forms_combined = pl.DataFrame()
    _save(forms_combined, f"payment_forms{suffix}.parquet")

    # Seasonality by payment month (YYYY-MM)
    with _timer("Seasonality by month"):
        try:
            season_df = seasonality_by_month(
                glg.edges, group_col=None
            ).with_columns(pl.lit(year).alias("year"))
        except Exception as exc:
            print(f"    WARNING: {exc}")
            season_df = pl.DataFrame()
    _save(season_df, f"seasonality{suffix}.parquet")

    # Distribution stats for charting (global + subgroup views)
    with _timer("Payment distribution stats"):
        try:
            dist_global = payment_distribution_stats(glg.edges).with_columns(
                pl.lit(year).alias("year")
            )
        except Exception as exc:
            print(f"    WARNING global distribution: {exc}")
            dist_global = pl.DataFrame()
        _save(dist_global, f"payment_distribution_global{suffix}.parquet")

        for scope, scoped_edges in [
            ("specialty", edges_with_spec),
            ("state", edges_with_state),
            ("credential", edges_with_cred),
        ]:
            try:
                col = "credential_type" if scope == "credential" else scope
                dist_df = payment_distribution_stats(
                    scoped_edges, group_col=col
                ).with_columns(pl.lit(year).alias("year"))
            except Exception as exc:
                print(f"    WARNING distribution ({scope}): {exc}")
                dist_df = pl.DataFrame()
            _save(dist_df, f"payment_distribution_{scope}{suffix}.parquet")

    # Anomaly scores
    with _timer("Anomaly detection"):
        try:
            anomaly_df = compute_anomaly_scores(glg, c_df)
            anomaly_df = anomaly_df.with_columns(pl.lit(year).alias("year"))
        except Exception as exc:
            print(f"    WARNING: {exc}")
            anomaly_df = pl.DataFrame()
    _save(anomaly_df, f"anomaly_scores{suffix}.parquet")

    # Capture analysis
    with _timer("Capture analysis"):
        try:
            capture_df = company_physician_capture(glg, c_df)
            capture_df = capture_df.with_columns(pl.lit(year).alias("year"))
        except Exception as exc:
            print(f"    WARNING: {exc}")
            capture_df = pl.DataFrame()
    _save(capture_df, f"capture_analysis{suffix}.parquet")

    # Top entities by specialty (treemap / bar chart data)
    with _timer("Top entities by group"):
        if "specialty" in edges_with_spec.columns:
            top_spec = top_entities_by_group(
                edges_with_spec, group_col="specialty",
                entity_col="src_id", top_k=10,
            ).with_columns(pl.lit(year).alias("year"))
            _save(top_spec, f"top_entities_specialty{suffix}.parquet")
        if "state" in edges_with_state.columns:
            top_state = top_entities_by_group(
                edges_with_state, group_col="state",
                entity_col="src_id", top_k=10,
            ).with_columns(pl.lit(year).alias("year"))
            _save(top_state, f"top_entities_state{suffix}.parquet")
        if "credential_type" in edges_with_cred.columns:
            top_cred = top_entities_by_group(
                edges_with_cred, group_col="credential_type",
                entity_col="src_id", top_k=10,
            ).with_columns(pl.lit(year).alias("year"))
            _save(top_cred, f"top_entities_credential{suffix}.parquet")

    # Product analytics (requires node_products ETL output)
    with _timer("Product analytics"):
        try:
            top_drug = top_products_global(
                year=year, product_type="drug", top_k=200
            ).with_columns(pl.lit(year).alias("year"))
        except Exception as exc:
            print(f"    WARNING top_products_drug: {exc}")
            top_drug = pl.DataFrame()
        _save(top_drug, f"top_products_drug{suffix}.parquet")

        try:
            top_device = top_products_global(
                year=year, product_type="device", top_k=200
            ).with_columns(pl.lit(year).alias("year"))
        except Exception as exc:
            print(f"    WARNING top_products_device: {exc}")
            top_device = pl.DataFrame()
        _save(top_device, f"top_products_device{suffix}.parquet")

        try:
            prod_div = physician_product_diversity(glg.edges).with_columns(
                pl.lit(year).alias("year")
            )
        except Exception as exc:
            print(f"    WARNING physician_product_diversity: {exc}")
            prod_div = pl.DataFrame()
        _save(prod_div, f"physician_product_diversity{suffix}.parquet")

    print(f"  Year {year} complete.")


# Cross-year (temporal) analytics
def run_temporal(
    years: list[int] | None = None,
) -> None:
    """Run analytics that require multiple year snapshots."""
    from analytics.temporal import (
        network_evolution_metrics,
        entity_trajectory,
        emerging_entities,
        relationship_persistence,
        payment_flow_shifts,
        payment_form_trends,
    )
    from analytics.anomaly import detect_sudden_jumps

    print("  Temporal analytics (multi-year)")

    target_years = years or available_years()
    snapshots = load_temporal_snapshots(years=target_years, min_amount=1.0)
    print(f"  Loaded {len(snapshots)} year snapshots: {sorted(snapshots)}")

    if not snapshots:
        print("  No snapshots found - skipping temporal analytics.")
        return

    # Network evolution
    with _timer("Network evolution metrics"):
        try:
            evo_df = network_evolution_metrics(snapshots)
        except Exception as exc:
            print(f"    WARNING: {exc}")
            evo_df = pl.DataFrame()
    _save(evo_df, "temporal_evolution.parquet")

    # Emerging entities
    with _timer("Emerging entities"):
        try:
            emerg_df = emerging_entities(
                snapshots, metric="in_strength", top_k=100
            )
        except Exception as exc:
            print(f"    WARNING: {exc}")
            emerg_df = pl.DataFrame()
    _save(emerg_df, "emerging_entities_in_strength.parquet")
    # Backward-compatible output name
    _save(emerg_df, "emerging_entities.parquet")

    # Emerging entities (PageRank)
    with _timer("Emerging entities (PageRank)"):
        try:
            emerg_pr_df = emerging_entities(
                snapshots, metric="pagerank", top_k=100
            )
        except Exception as exc:
            print(f"    WARNING: {exc}")
            emerg_pr_df = pl.DataFrame()
    _save(emerg_pr_df, "emerging_entities_pagerank.parquet")

    # Entity trajectories (long format)
    with _timer("Entity trajectory (in_strength)"):
        try:
            traj_in = entity_trajectory(
                snapshots, entity_ids=None, metric="in_strength", top_k=300
            )
        except Exception as exc:
            print(f"    WARNING: {exc}")
            traj_in = pl.DataFrame()
    _save(traj_in, "entity_trajectory_in_strength.parquet")

    with _timer("Entity trajectory (PageRank)"):
        try:
            traj_pr = entity_trajectory(
                snapshots, entity_ids=None, metric="pagerank", top_k=300
            )
        except Exception as exc:
            print(f"    WARNING: {exc}")
            traj_pr = pl.DataFrame()
    _save(traj_pr, "entity_trajectory_pagerank.parquet")

    # Sudden jumps between consecutive years
    with _timer("Sudden jumps (in_strength)"):
        try:
            jumps_in = detect_sudden_jumps(
                snapshots, min_jump_factor=3.0, metric="in_strength"
            )
        except Exception as exc:
            print(f"    WARNING: {exc}")
            jumps_in = pl.DataFrame()
    _save(jumps_in, "sudden_jumps_in_strength.parquet")

    with _timer("Sudden jumps (PageRank)"):
        try:
            jumps_pr = detect_sudden_jumps(
                snapshots, min_jump_factor=3.0, metric="pagerank"
            )
        except Exception as exc:
            print(f"    WARNING: {exc}")
            jumps_pr = pl.DataFrame()
    _save(jumps_pr, "sudden_jumps_pagerank.parquet")

    # Payment flow by specialty
    with _timer("Payment flow by specialty"):
        try:
            flow_spec = payment_flow_shifts(snapshots, group_col="specialty")
        except Exception as exc:
            print(f"    WARNING: {exc}")
            flow_spec = pl.DataFrame()
    _save(flow_spec, "payment_flow_specialty.parquet")

    # Payment flow by state
    with _timer("Payment flow by state"):
        try:
            flow_state = payment_flow_shifts(snapshots, group_col="state")
        except Exception as exc:
            print(f"    WARNING: {exc}")
            flow_state = pl.DataFrame()
    _save(flow_state, "payment_flow_state.parquet")

    # Payment flow by credential type (MD vs NPP)
    with _timer("Payment flow by credential type"):
        try:
            flow_cred = payment_flow_shifts(snapshots, group_col="credential_type")
        except Exception as exc:
            print(f"    WARNING: {exc}")
            flow_cred = pl.DataFrame()
    _save(flow_cred, "payment_flow_credential.parquet")

    # Payment form trends (Cash / Stock / In-kind share over years)
    with _timer("Payment form trends (global)"):
        try:
            form_trends_df = payment_form_trends(snapshots)
        except Exception as exc:
            print(f"    WARNING: {exc}")
            form_trends_df = pl.DataFrame()
    _save(form_trends_df, "payment_form_trends.parquet")

    with _timer("Payment form trends (specialty)"):
        try:
            form_trends_spec = payment_form_trends(
                snapshots, group_col="specialty"
            )
        except Exception as exc:
            print(f"    WARNING: {exc}")
            form_trends_spec = pl.DataFrame()
    _save(form_trends_spec, "payment_form_trends_specialty.parquet")

    with _timer("Payment form trends (state)"):
        try:
            form_trends_state = payment_form_trends(
                snapshots, group_col="state"
            )
        except Exception as exc:
            print(f"    WARNING: {exc}")
            form_trends_state = pl.DataFrame()
    _save(form_trends_state, "payment_form_trends_state.parquet")

    with _timer("Payment form trends (credential)"):
        try:
            form_trends_cred = payment_form_trends(
                snapshots, group_col="credential_type"
            )
        except Exception as exc:
            print(f"    WARNING: {exc}")
            form_trends_cred = pl.DataFrame()
    _save(form_trends_cred, "payment_form_trends_credential.parquet")

    # Relationship persistence (expensive)
    with _timer("Relationship persistence"):
        try:
            persist_df = relationship_persistence(snapshots)
        except Exception as exc:
            print(f"    WARNING: {exc}")
            persist_df = pl.DataFrame()
    _save(persist_df, "relationship_persistence.parquet")

    print("  Temporal analytics complete.")


# Consolidation: merge per-year files into single multi-year files
def consolidate(years: list[int] | None = None) -> None:
    """
    Merge per-year parquet files into consolidated multi-year files.
    The per-year files are retained; consolidated files are prefixed with 'all_'.
    """
    target_years = years or available_years()

    files_to_merge = [
        "node_metrics",
        "community_assignments",
        "community_summaries",
        "community_assignments_bipartite",
        "community_summaries_bipartite",
        "community_assignments_physician_projection",
        "community_summaries_physician_projection",
        "community_assignments_company_projection",
        "community_summaries_company_projection",
        "concentration_specialty",
        "concentration_state",
        "concentration_credential",
        "payment_distribution_global",
        "payment_distribution_specialty",
        "payment_distribution_state",
        "payment_distribution_credential",
        "payment_forms",
        "seasonality",
        "anomaly_scores",
        "capture_analysis",
        "top_entities_specialty",
        "top_entities_state",
        "top_entities_credential",
        "top_products_drug",
        "top_products_device",
        "physician_product_diversity",
    ]

    print("  Consolidating per-year files")

    for stem in files_to_merge:
        frames = []
        for yr in sorted(target_years):
            fp = ANALYTICS_DIR / f"{stem}_{yr}.parquet"
            if fp.exists():
                frames.append(pl.read_parquet(fp))
        if frames:
            merged = pl.concat(frames, how="diagonal")
            _save(merged, f"all_{stem}.parquet")


# Entry point
def run(
    years: list[int] | None = None,
    betweenness_samples: int = 150,
) -> None:
    """Run the full precompute pipeline."""
    target_years = years or available_years()
    if not target_years:
        print("No processed years found.  Run the ETL first.")
        return

    total_start = time.perf_counter()
    print(f"\nGraphLens Precompute  |  years: {target_years}  |  mode=full")
    print(f"Output directory: {ANALYTICS_DIR}\n")

    # Per-year analytics
    for yr in sorted(target_years):
        run_year(yr, betweenness_samples=betweenness_samples)

    # Cross-year analytics
    run_temporal(years=list(target_years))

    # Consolidate
    consolidate(years=list(target_years))

    elapsed = time.perf_counter() - total_start
    print(f"\n  All analytics complete in {elapsed:.1f}s")
    size_mb = sum(
        p.stat().st_size for p in ANALYTICS_DIR.glob("*.parquet")
    ) / 1e6
    print(f"  Analytics dir size: {size_mb:.1f} MB")


# Utilities for reading precomputed analytics
def load_precomputed(name: str) -> pl.DataFrame:
    """
    Load a precomputed analytics file by short name.

    Example
    -------
    >>> df = load_precomputed("all_node_metrics")
    >>> df = load_precomputed("temporal_evolution")
    """
    fp = ANALYTICS_DIR / f"{name}.parquet"
    if not fp.exists():
        fp = ANALYTICS_DIR / f"all_{name}.parquet"
    if not fp.exists():
        raise FileNotFoundError(
            f"Precomputed file not found: {fp}\n"
            "Run:  uv run python -m analytics.precompute"
        )
    return pl.read_parquet(fp)


def list_precomputed() -> list[str]:
    """Return names of all available precomputed analytics files."""
    return sorted(p.stem for p in ANALYTICS_DIR.glob("*.parquet"))


# Internal helpers
def _enrich_edges_with_node_attr(
    glg: "GraphLensGraph",
    attr: str,
) -> pl.DataFrame:
    """
    Join a node attribute onto the edge DataFrame via dst_id (recipient node).
    Returns edges with an additional column for the attribute.
    Works for any column present in glg.nodes: specialty, state,
    credential_type, zip_code, etc.
    """
    nodes = glg.nodes.with_columns(pl.col("id").cast(pl.Utf8))
    if attr not in nodes.columns:
        return glg.edges

    node_attr = nodes.select(["id", attr]).rename({"id": "dst_id"})
    return glg.edges.with_columns(
        pl.col("dst_id").cast(pl.Utf8)
    ).join(node_attr, on="dst_id", how="left")


def _safe_concentration(
    enriched_edges: pl.DataFrame,
    group_col: str,
    year: int,
) -> pl.DataFrame:
    """
    Run concentration_by_group safely, returning an empty DataFrame on failure.
    Tags the result with the given year.
    """
    from analytics.concentration import concentration_by_group
    if group_col not in enriched_edges.columns:
        return pl.DataFrame()
    try:
        return (
            concentration_by_group(
                enriched_edges,
                group_col=group_col,
                amount_col="total_amount",
                entity_col="src_id",
            ).with_columns(pl.lit(year).alias("year"))
        )
    except Exception as exc:
        print(f"    WARNING concentration({group_col}): {exc}")
        return pl.DataFrame()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GraphLens Analytics Precompute")
    parser.add_argument("--year", type=int, default=None,
                        help="Process a single year only")
    parser.add_argument("--samples", type=int, default=150,
                        help="Betweenness centrality sample count")
    args = parser.parse_args()

    run(
        years=[args.year] if args.year else None,
        betweenness_samples=args.samples,
    )
