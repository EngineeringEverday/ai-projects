#! usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import APIRouter, Query    # type: ignore[import-not-found]
import polars as pl     # type: ignore[import-not-found]

from api.schemas import TableResponse
from api.utils import parse_fields, read_analytics_table, table_response


router = APIRouter(prefix="/anomalies", tags=["anomalies"])


@router.get("/{year}", response_model=TableResponse)
def get_anomalies(
    year: int,
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(500, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    df = read_analytics_table("anomaly_scores", year)
    if "composite_anomaly_score" in df.columns:
        df = df.filter(pl.col("composite_anomaly_score") >= min_score)
    return table_response(df, limit=limit, offset=offset, sort_by="composite_anomaly_score", desc=True, fields=parse_fields(fields))


@router.get("/{year}/capture", response_model=TableResponse)
def get_capture_analysis(
    year: int,
    min_capture_ratio: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(500, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    df = read_analytics_table("capture_analysis", year)
    if "capture_ratio" in df.columns:
        df = df.filter(pl.col("capture_ratio") >= min_capture_ratio)
    return table_response(df, limit=limit, offset=offset, sort_by="capture_ratio", desc=True, fields=parse_fields(fields))
