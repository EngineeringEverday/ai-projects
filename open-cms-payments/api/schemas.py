#! usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    message: str


class YearListResponse(BaseModel):
    years: list[int]


class GraphSummaryResponse(BaseModel):
    year: int
    nodes: int
    edges: int
    node_types: dict[str, int]
    credential_types: dict[str, int]
    total_payment_usd: float
    cash_payment_usd: float
    avg_edge_weight_usd: float
    is_directed: bool


class TableResponse(BaseModel):
    columns: list[str]
    total_rows: int
    limit: int | None = None
    offset: int | None = None
    rows: list[dict[str, Any]]


class DashboardSectionResponse(BaseModel):
    title: str
    table: TableResponse


class DashboardOverviewResponse(BaseModel):
    year: int
    summary: GraphSummaryResponse
    sections: list[DashboardSectionResponse]


class GraphPayloadResponse(BaseModel):
    summary: GraphSummaryResponse
    nodes: TableResponse
    edges: TableResponse


class NodeDetailsResponse(BaseModel):
    node: dict[str, Any]
    outgoing_edges: TableResponse
    incoming_edges: TableResponse
