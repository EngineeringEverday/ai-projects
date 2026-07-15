#! usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import APIRouter, Query    # type: ignore[import-not-found]
import polars as pl     # type: ignore[import-not-found]

from api.schemas import TableResponse
from api.utils import parse_fields, read_analytics_table, table_response


router = APIRouter(prefix="/products", tags=["products"])


@router.get("/{year}/top", response_model=TableResponse)
def top_products(
    year: int,
    product_type: str = Query("drug", pattern="^(drug|device)$"),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    stem = "top_products_drug" if product_type == "drug" else "top_products_device"
    df = read_analytics_table(stem, year)
    return table_response(df, limit=limit, offset=offset, sort_by="n_records", desc=True, fields=parse_fields(fields))


@router.get("/{year}/diversity", response_model=TableResponse)
def physician_product_diversity(
    year: int,
    min_total_payment: float = Query(0.0, ge=0.0),
    limit: int = Query(500, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    df = read_analytics_table("physician_product_diversity", year)
    if "total_payment" in df.columns:
        df = df.filter(pl.col("total_payment") >= min_total_payment)
    return table_response(df, limit=limit, offset=offset, sort_by="total_payment", desc=True, fields=parse_fields(fields))
