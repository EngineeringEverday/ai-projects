#! usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from pathlib import Path
from typing import Any

import polars as pl     # type: ignore[import-not-found]
from fastapi import HTTPException   # type: ignore[import-not-found]

from api.schemas import TableResponse
from graphlens.config import PROCESSED_DIR
from graphlens.graph import available_years


ANALYTICS_PARQUET_DIR = PROCESSED_DIR / "analytics"
ANALYTICS_JSON_DIR = Path(os.getenv("ANALYTICS_JSON_DIR", str(PROCESSED_DIR / "analytics_json")))
ANALYTICS_CACHE_MAX_ENTRIES = int(os.getenv("ANALYTICS_CACHE_MAX_ENTRIES", "16"))
# JSON files larger than this (bytes) are never cached — they expand ~10x in memory
ANALYTICS_CACHE_MAX_FILE_BYTES = int(os.getenv("ANALYTICS_CACHE_MAX_FILE_BYTES", str(2 * 1024 * 1024)))


_ANALYTICS_CACHE: dict[tuple[str, int | None], tuple[Path, int, pl.DataFrame]] = {}
_CACHE_HITS = 0
_CACHE_MISSES = 0


def ensure_year_available(year: int) -> None:
    years = available_years()
    if year not in years:
        raise HTTPException(
            status_code=404,
            detail=f"Year {year} is not available. Available years: {years}",
        )


def read_parquet_or_404(path: Path) -> pl.DataFrame:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path.name}")
    return pl.read_parquet(path)


def analytics_file(stem: str, year: int | None = None) -> Path:
    if year is None:
        return ANALYTICS_PARQUET_DIR / f"{stem}.parquet"
    return ANALYTICS_PARQUET_DIR / f"{stem}_{year}.parquet"


def analytics_json_file(stem: str, year: int | None = None) -> Path:
    if year is None:
        return ANALYTICS_JSON_DIR / f"{stem}.json"
    return ANALYTICS_JSON_DIR / f"{stem}_{year}.json"


def _cache_lookup(key: tuple[str, int | None], path: Path) -> pl.DataFrame | None:
    global _CACHE_HITS, _CACHE_MISSES

    entry = _ANALYTICS_CACHE.get(key)
    if entry is None:
        _CACHE_MISSES += 1
        return None

    cached_path, cached_mtime, cached_df = entry
    mtime = path.stat().st_mtime_ns
    if cached_path == path and cached_mtime == mtime:
        _CACHE_HITS += 1
        return cached_df

    _CACHE_MISSES += 1
    return None


def _cache_store(key: tuple[str, int | None], path: Path, df: pl.DataFrame) -> None:
    if ANALYTICS_CACHE_MAX_ENTRIES <= 0:
        return

    # Skip caching large files — they expand ~10x in memory when parsed from JSON
    if path.stat().st_size > ANALYTICS_CACHE_MAX_FILE_BYTES:
        return

    if len(_ANALYTICS_CACHE) >= ANALYTICS_CACHE_MAX_ENTRIES:
        oldest = next(iter(_ANALYTICS_CACHE))
        _ANALYTICS_CACHE.pop(oldest, None)

    _ANALYTICS_CACHE[key] = (path, path.stat().st_mtime_ns, df)


def analytics_cache_stats() -> dict[str, int]:
    return {
        "entries": len(_ANALYTICS_CACHE),
        "max_entries": ANALYTICS_CACHE_MAX_ENTRIES,
        "hits": _CACHE_HITS,
        "misses": _CACHE_MISSES,
    }


def read_analytics_table(stem: str, year: int | None = None) -> pl.DataFrame:
    key = (stem, year)

    json_fp = analytics_json_file(stem, year)
    if json_fp.exists():
        cached = _cache_lookup(key, json_fp)
        if cached is not None:
            return cached

        raw = json.loads(json_fp.read_text())
        # JSON files may be saved in TableResponse format {columns, total_rows, rows: [...]}
        # or as a plain array. Detect and unwrap accordingly.
        if isinstance(raw, dict) and "rows" in raw and isinstance(raw["rows"], list):
            df = pl.DataFrame(raw["rows"]) if raw["rows"] else pl.DataFrame()
        else:
            df = pl.DataFrame(raw) if isinstance(raw, list) and raw else pl.read_json(json_fp)
        _cache_store(key, json_fp, df)
        return df

    parquet_fp = analytics_file(stem, year)
    if parquet_fp.exists():
        cached = _cache_lookup(key, parquet_fp)
        if cached is not None:
            return cached

        df = pl.read_parquet(parquet_fp)
        _cache_store(key, parquet_fp, df)
        return df

    raise HTTPException(
        status_code=404,
        detail=(
            f"Analytics file not found for '{stem}'"
            f"{' year=' + str(year) if year is not None else ''}. "
            "Run analytics precompute and JSON export first."
        ),
    )


def to_json_rows(df: pl.DataFrame) -> list[dict[str, Any]]:
    if df.is_empty():
        return []
    return df.to_dicts()


def parse_fields(fields: str | None) -> list[str] | None:
    if not fields:
        return None

    out: list[str] = []
    for raw in fields.split(","):
        col = raw.strip()
        if col and col not in out:
            out.append(col)
    return out or None


def select_fields(df: pl.DataFrame, fields: list[str] | None) -> pl.DataFrame:
    if not fields:
        return df

    valid = [col for col in fields if col in df.columns]
    if not valid:
        raise HTTPException(
            status_code=400,
            detail=f"None of requested fields are present. Requested={fields}",
        )
    return df.select(valid)


def page_df(
    df: pl.DataFrame,
    limit: int,
    offset: int,
    sort_by: str | None = None,
    desc: bool = True,
) -> pl.DataFrame:
    out = df
    if sort_by and sort_by in out.columns:
        out = out.sort(sort_by, descending=desc)
    if offset > 0:
        out = out.slice(offset)
    return out.head(limit)


def table_response(
    df: pl.DataFrame,
    limit: int,
    offset: int,
    sort_by: str | None = None,
    desc: bool = True,
    fields: list[str] | None = None,
) -> TableResponse:
    df = select_fields(df, fields)
    total = df.height
    page = page_df(df, limit=limit, offset=offset, sort_by=sort_by, desc=desc)
    return TableResponse(
        columns=page.columns,
        total_rows=total,
        limit=limit,
        offset=offset,
        rows=page.to_dicts(),
    )
