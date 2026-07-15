#!/usr/bin/env python3
"""
Precompute UMAP embeddings (2D + 3D) for community visualization.
Also precomputes state-to-state payment flows for choropleth connections.

Run from the project root:
    uv run python analytics/precompute_embeddings.py

Outputs (in processed/analytics/):
    community_umap2d_{year}.parquet   - id, x, y, community_id, node_type, name, in_strength, ...
    community_umap3d_{year}.parquet   - id, x, y, z, community_id, ...
    state_flows_{year}.parquet        - src_state, dst_state, total_amount, payment_count
"""

import json
import warnings
from pathlib import Path

import numpy as np      # type: ignore[import-not-found]
import polars as pl     # type: ignore[import-not-found]

warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "processed"
ANALYTICS = PROCESSED / "analytics"
JSON_DIR = PROCESSED / "analytics_json"
YEARS = [2020, 2021, 2022, 2023, 2024]

# Feature columns used for embedding
EMBED_FEATURES = [
    "pagerank", "in_degree", "out_degree", "in_strength", "out_strength",
    "betweenness", "hub_score", "authority_score",
    "payment_diversity", "cash_ratio", "disputed_ratio", "third_party_ratio",
]


def safe_read_parquet(path: Path) -> pl.DataFrame | None:
    if not path.exists():
        print(f"  [skip] {path.name} not found")
        return None
    return pl.read_parquet(path)


def write_parquet_and_json(df: pl.DataFrame, stem: str, year: int | None = None) -> None:
    name = f"{stem}_{year}" if year is not None else stem
    pq_path = ANALYTICS / f"{name}.parquet"
    json_path = JSON_DIR / f"{name}.json"

    # Write Parquet
    df.write_parquet(pq_path)

    # Write JSON (for fast API streaming)
    rows = df.to_dicts()
    payload = {
        "columns": df.columns,
        "total_rows": len(rows),
        "rows": rows,
    }
    json_path.write_text(json.dumps(payload, default=str))
    print(f"  ✓  {pq_path.name}  ({len(rows)} rows)")


#  UMAP embeddings
def compute_umap_for_year(year: int) -> None:
    print(f"\n── Year {year} ──")

    # Load node metrics + community assignments
    metrics_df = safe_read_parquet(ANALYTICS / f"node_metrics_{year}.parquet")
    comm_df = safe_read_parquet(ANALYTICS / f"community_assignments_{year}.parquet")
    if metrics_df is None or comm_df is None:
        return

    # Join community IDs onto metrics
    df = metrics_df.join(
        comm_df.select(["id", "community_id"]),
        on="id",
        how="left",
    )

    # Keep only physician-type rows for embedding (manufacturers have very different scales)
    # Actually embed all nodes - we'll color by type
    df = df.filter(pl.col("node_type").is_in(["Physician", "Manufacturer", "TeachingHospital"]))

    if len(df) < 10:
        print(f"  [skip] too few rows ({len(df)})")
        return

    # Build feature matrix - fill nulls with column median
    feature_cols = [c for c in EMBED_FEATURES if c in df.columns]
    X = df.select(feature_cols).to_numpy().astype(float)

    # Replace NaN / inf with 0
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    # Log-scale skewed financial columns
    for i, col in enumerate(feature_cols):
        if col in ("in_strength", "out_strength", "pagerank"):
            X[:, i] = np.log1p(X[:, i])

    # Standardize
    from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    n_samples = len(X_scaled)
    n_neighbors = min(15, max(2, n_samples // 10))

    # ── 2D UMAP ──
    try:
        import umap  # type: ignore[import-untyped]
        reducer_2d = umap.UMAP(
            n_components=2,
            n_neighbors=n_neighbors,
            min_dist=0.1,
            metric="euclidean",
            random_state=42,
        )
        coords_2d = reducer_2d.fit_transform(X_scaled)

        out_2d = df.select(
            ["id", "node_type", "name", "state", "specialty",
             "in_strength", "pagerank", "cash_ratio", "community_id"]
        ).with_columns([
            pl.Series("umap_x", coords_2d[:, 0].astype(float)),
            pl.Series("umap_y", coords_2d[:, 1].astype(float)),
        ])
        write_parquet_and_json(out_2d, "community_umap2d", year)
    except Exception as e:
        print(f"  [warn] 2D UMAP failed: {e}")
        # Fallback: PCA
        try:
            from sklearn.decomposition import PCA  # type: ignore[import-untyped]
            pca = PCA(n_components=2, random_state=16)
            coords_2d = pca.fit_transform(X_scaled)
            out_2d = df.select(
                ["id", "node_type", "name", "state", "specialty",
                 "in_strength", "pagerank", "cash_ratio", "community_id"]
            ).with_columns([
                pl.Series("umap_x", coords_2d[:, 0].astype(float)),
                pl.Series("umap_y", coords_2d[:, 1].astype(float)),
            ])
            write_parquet_and_json(out_2d, "community_umap2d", year)
            print("  (used PCA fallback for 2D)")
        except Exception as e2:
            print(f"  [error] PCA also failed: {e2}")

    # ── 3D UMAP ──
    try:
        import umap  # type: ignore[import-untyped]
        reducer_3d = umap.UMAP(
            n_components=3,
            n_neighbors=n_neighbors,
            min_dist=0.15,
            metric="euclidean",
            random_state=42,
        )
        coords_3d = reducer_3d.fit_transform(X_scaled)

        out_3d = df.select(
            ["id", "node_type", "name", "state", "specialty",
             "in_strength", "pagerank", "cash_ratio", "composite_anomaly_score",
             "community_id"]
            if "composite_anomaly_score" in df.columns else
            ["id", "node_type", "name", "state", "specialty",
             "in_strength", "pagerank", "cash_ratio", "community_id"]
        ).with_columns([
            pl.Series("umap_x", coords_3d[:, 0].astype(float)),
            pl.Series("umap_y", coords_3d[:, 1].astype(float)),
            pl.Series("umap_z", coords_3d[:, 2].astype(float)),
        ])
        write_parquet_and_json(out_3d, "community_umap3d", year)
    except Exception as e:
        print(f"  [warn] 3D UMAP failed: {e}")


# ── State-to-state payment flows ───────────────────────────────────
def compute_state_flows() -> None:
    print("\n── State flows ──")

    nodes_path = PROCESSED / "nodes.parquet"
    edges_path = PROCESSED / "edges_general.parquet"

    if not nodes_path.exists() or not edges_path.exists():
        print("  [skip] nodes or edges parquet not found")
        return

    nodes = pl.read_parquet(nodes_path).select(["id", "state"])
    edges = pl.read_parquet(edges_path).select(
        ["src_id", "dst_id", "year", "total_amount", "payment_count"]
    )

    # Join source state
    df = edges.join(
        nodes.rename({"id": "src_id", "state": "src_state"}),
        on="src_id", how="left",
    )
    # Join destination state
    df = df.join(
        nodes.rename({"id": "dst_id", "state": "dst_state"}),
        on="dst_id", how="left",
    )

    # Drop rows where either state is null or same state (keep cross-state)
    df = df.filter(
        pl.col("src_state").is_not_null() & pl.col("dst_state").is_not_null() & (pl.col("src_state") != pl.col("dst_state"))
    )

    # Aggregate by year, src_state, dst_state
    flows = (
        df.group_by(["year", "src_state", "dst_state"])
        .agg([
            pl.col("total_amount").sum().alias("total_amount"),
            pl.col("payment_count").sum().alias("payment_count"),
        ])
        .sort(["year", "total_amount"], descending=[False, True])
    )

    for year in YEARS:
        year_flows = flows.filter(pl.col("year") == year)
        if len(year_flows) == 0:
            continue
        write_parquet_and_json(year_flows, "state_flows", year)


# ── Main ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    ANALYTICS.mkdir(parents=True, exist_ok=True)
    JSON_DIR.mkdir(parents=True, exist_ok=True)

    print("GraphLens - Precomputing community embeddings & state flows")

    for year in YEARS:
        compute_umap_for_year(year)

    compute_state_flows()

    print("\n✓ Done.")
