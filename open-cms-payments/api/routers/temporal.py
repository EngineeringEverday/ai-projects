#! usr/bin/env python3
# -*- coding: utf-8 -*-


from fastapi import APIRouter, Query    # type: ignore[import-not-found]
import polars as pl    # type: ignore[import-not-found]

from api.schemas import TableResponse
from api.utils import parse_fields, read_analytics_table, table_response


router = APIRouter(prefix="/temporal", tags=["temporal"])


@router.get("/evolution", response_model=TableResponse)
def temporal_evolution(
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    df = read_analytics_table("temporal_evolution")
    out = df.sort("year") if "year" in df.columns else df
    return table_response(out, limit=out.height, offset=0, fields=parse_fields(fields))


@router.get("/emerging", response_model=TableResponse)
def emerging_entities(
    metric: str = Query("in_strength", pattern="^(in_strength|pagerank)$"),
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    stem = "emerging_entities_in_strength" if metric == "in_strength" else "emerging_entities_pagerank"
    df = read_analytics_table(stem)
    return table_response(df, limit=limit, offset=offset, sort_by="slope", desc=True, fields=parse_fields(fields))


@router.get("/trajectory", response_model=TableResponse)
def entity_trajectory(
    metric: str = Query("in_strength", pattern="^(in_strength|pagerank)$"),
    entity_id: str | None = Query(default=None),
    limit: int = Query(5000, ge=1, le=50000),
    offset: int = Query(0, ge=0),
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    stem = "entity_trajectory_in_strength" if metric == "in_strength" else "entity_trajectory_pagerank"
    df = read_analytics_table(stem)
    if entity_id and "id" in df.columns:
        df = df.filter(pl.col("id").cast(pl.Utf8) == entity_id)
    return table_response(df, limit=limit, offset=offset, sort_by="year", desc=False, fields=parse_fields(fields))


@router.get("/jumps", response_model=TableResponse)
def sudden_jumps(
    metric: str = Query("in_strength", pattern="^(in_strength|pagerank)$"),
    limit: int = Query(500, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    stem = "sudden_jumps_in_strength" if metric == "in_strength" else "sudden_jumps_pagerank"
    df = read_analytics_table(stem)
    return table_response(df, limit=limit, offset=offset, sort_by="jump_factor", desc=True, fields=parse_fields(fields))


@router.get("/flows/{scope}", response_model=TableResponse)
def payment_flows(
    scope: str,
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    valid = {"specialty", "state", "credential"}
    if scope not in valid:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"scope must be one of {sorted(valid)}")

    df = read_analytics_table(f"payment_flow_{scope}")
    return table_response(df, limit=limit, offset=offset, sort_by="year", desc=False, fields=parse_fields(fields))


@router.get("/payment-form-trends/{scope}", response_model=TableResponse)
def payment_form_trends(
    scope: str,
    limit: int = Query(1000, ge=1, le=20000),
    offset: int = Query(0, ge=0),
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    valid = {"global", "specialty", "state", "credential"}
    if scope not in valid:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"scope must be one of {sorted(valid)}")

    stem = "payment_form_trends" if scope == "global" else f"payment_form_trends_{scope}"
    df = read_analytics_table(stem)
    return table_response(df, limit=limit, offset=offset, sort_by="year", desc=False, fields=parse_fields(fields))


@router.get("/relationship-persistence", response_model=TableResponse)
def relationship_persistence(
    limit: int = Query(2000, ge=1, le=50000),
    offset: int = Query(0, ge=0),
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    df = read_analytics_table("relationship_persistence")
    return table_response(df, limit=limit, offset=offset, sort_by="n_years_active", desc=True, fields=parse_fields(fields))
