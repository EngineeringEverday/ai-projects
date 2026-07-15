#! usr/bin/env python3
# -*- coding: utf-8 -*-

"""
analytics.export_json
=====================
Convert precomputed analytics parquet files to JSON files for API serving.

Usage
-----
  uv run python -m analytics.export_json
  uv run python -m analytics.export_json --year 2022
"""

import argparse

import polars as pl  # type: ignore[import-not-found]

from graphlens.config import PROCESSED_DIR


ANALYTICS_PARQUET_DIR = PROCESSED_DIR / "analytics"
ANALYTICS_JSON_DIR = PROCESSED_DIR / "analytics_json"


def _matches_year(stem: str, year: int) -> bool:
    suffix = f"_{year}"
    return stem.endswith(suffix)


def run(year: int | None = None) -> None:
    ANALYTICS_JSON_DIR.mkdir(parents=True, exist_ok=True)

    parquet_files = sorted(ANALYTICS_PARQUET_DIR.glob("*.parquet"))
    if year is not None:
        parquet_files = [p for p in parquet_files if _matches_year(p.stem, year)]

    if not parquet_files:
        print("No analytics parquet files found to export.")
        return

    print(f"Exporting {len(parquet_files)} analytics files to JSON")
    total_rows = 0

    for src in parquet_files:
        dst = ANALYTICS_JSON_DIR / f"{src.stem}.json"
        df = pl.read_parquet(src)
        df.write_json(dst)
        total_rows += df.height
        size_kb = dst.stat().st_size // 1024
        print(f"  {src.name} -> {dst.name}  rows={df.height:,} size={size_kb} KB")

    total_mb = sum(p.stat().st_size for p in ANALYTICS_JSON_DIR.glob("*.json")) / 1e6
    print(f"Done. Exported rows={total_rows:,}. JSON dir size={total_mb:.1f} MB")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export analytics parquet files to JSON")
    parser.add_argument("--year", type=int, default=None, help="Export only files for a single year")
    args = parser.parse_args()
    run(year=args.year)
