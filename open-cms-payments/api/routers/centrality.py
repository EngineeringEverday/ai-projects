#! usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import APIRouter, Query    # type: ignore[import-not-found]
import polars as pl     # type: ignore[import-not-found]

from api.schemas import TableResponse
from api.utils import parse_fields, read_analytics_table, table_response


router = APIRouter(prefix="/centrality", tags=["centrality"])


@router.get("/{year}", response_model=TableResponse)
def get_centrality(
    year: int,
    metric: str | None = Query(default=None),
    top_k: int | None = Query(default=None, ge=1, le=5000),
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    df = read_analytics_table("node_metrics", year)

    if metric and metric in df.columns:
        df = df.sort(metric, descending=True)

    if top_k:
        df = df.head(top_k)

    return table_response(
        df,
        limit=limit,
        offset=offset,
        sort_by=metric if metric in df.columns else "pagerank",
        desc=True,
        fields=parse_fields(fields),
    )


@router.get("/{year}/node/{node_id}", response_model=TableResponse)
def get_node_centrality(
    year: int,
    node_id: str,
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    df = read_analytics_table("node_metrics", year).filter(pl.col("id").cast(pl.Utf8) == node_id)
    return table_response(df, limit=df.height, offset=0, fields=parse_fields(fields))
