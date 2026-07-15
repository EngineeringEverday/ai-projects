#! usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import APIRouter, Query    # type: ignore[import-not-found]

from api.schemas import TableResponse
from api.utils import parse_fields, read_analytics_table, table_response


router = APIRouter(prefix="/communities", tags=["communities"])


@router.get("/{year}/embeddings", response_model=TableResponse)
def community_embeddings(
    year: int,
    dims: int = Query(2, ge=2, le=3),
    limit: int = Query(5000, ge=1, le=50000),
    offset: int = Query(0, ge=0),
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    """UMAP embeddings for community visualization (2D or 3D)."""
    stem = f"community_umap{dims}d"
    df = read_analytics_table(stem, year)
    return table_response(df, limit=limit, offset=offset, fields=parse_fields(fields))


@router.get("/{year}/state-flows", response_model=TableResponse)
def state_flows(
    year: int,
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    fields: str | None = Query(default=None),
) -> TableResponse:
    """Cross-state payment flows for choropleth connection lines."""
    df = read_analytics_table("state_flows", year)
    return table_response(df, limit=limit, offset=offset, sort_by="total_amount", desc=True, fields=parse_fields(fields))


@router.get("/{year}/assignments", response_model=TableResponse)
def community_assignments(
    year: int,
    mode: str = Query("bipartite", pattern="^(bipartite|physician_projection|company_projection)$"),
    limit: int = Query(500, ge=1, le=20000),
    offset: int = Query(0, ge=0),
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    stem = "community_assignments" if mode == "bipartite" else f"community_assignments_{mode}"
    df = read_analytics_table(stem, year)
    return table_response(df, limit=limit, offset=offset, sort_by="community_id", desc=False, fields=parse_fields(fields))


@router.get("/{year}/summaries", response_model=TableResponse)
def community_summaries(
    year: int,
    mode: str = Query("bipartite", pattern="^(bipartite|physician_projection|company_projection)$"),
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    stem = "community_summaries" if mode == "bipartite" else f"community_summaries_{mode}"
    df = read_analytics_table(stem, year)
    return table_response(df, limit=limit, offset=offset, sort_by="total_payment_usd", desc=True, fields=parse_fields(fields))
