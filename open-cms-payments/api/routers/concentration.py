#! usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import APIRouter, Query    # type: ignore[import-not-found]

from api.schemas import TableResponse
from api.utils import parse_fields, read_analytics_table, table_response


router = APIRouter(prefix="/concentration", tags=["concentration"])


# Specific literal-prefix routes must come before the wildcard /{scope}/{year}

@router.get("/distribution/{scope}/{year}", response_model=TableResponse)
def get_distribution(
    scope: str,
    year: int,
    limit: int = Query(500, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    valid = {"global", "specialty", "state", "credential"}
    if scope not in valid:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"scope must be one of {sorted(valid)}")

    df = read_analytics_table(f"payment_distribution_{scope}", year)
    return table_response(df, limit=limit, offset=offset, sort_by="total", desc=True, fields=parse_fields(fields))


@router.get("/top-entities/{scope}/{year}", response_model=TableResponse)
def get_top_entities(
    scope: str,
    year: int,
    limit: int = Query(500, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    valid = {"specialty", "state", "credential"}
    if scope not in valid:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"scope must be one of {sorted(valid)}")

    df = read_analytics_table(f"top_entities_{scope}", year)
    return table_response(df, limit=limit, offset=offset, sort_by="total_payment", desc=True, fields=parse_fields(fields))


@router.get("/seasonality/{year}", response_model=TableResponse)
def get_seasonality(
    year: int,
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    df = read_analytics_table("seasonality", year)
    return table_response(df, limit=df.height, offset=0, sort_by="month", desc=False, fields=parse_fields(fields))


@router.get("/payment-forms/{year}", response_model=TableResponse)
def get_payment_forms(
    year: int,
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    df = read_analytics_table("payment_forms", year)
    return table_response(df, limit=df.height, offset=0, sort_by="total_amount", desc=True, fields=parse_fields(fields))


# Wildcard route last - catches /{scope}/{year} after all literal prefixes
@router.get("/{scope}/{year}", response_model=TableResponse)
def get_concentration(
    scope: str,
    year: int,
    limit: int = Query(500, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    fields: str | None = Query(default=None, description="Comma-separated columns to include"),
) -> TableResponse:
    valid = {"specialty", "state", "credential"}
    if scope not in valid:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"scope must be one of {sorted(valid)}")

    df = read_analytics_table(f"concentration_{scope}", year)
    return table_response(df, limit=limit, offset=offset, sort_by="total_payment", desc=True, fields=parse_fields(fields))
