#! usr/bin/env python3
# -*- coding: utf-8 -*-


from fastapi import APIRouter, Query    # type: ignore[import-not-found]

from api.schemas import GraphPayloadResponse, GraphSummaryResponse, TableResponse, YearListResponse
from api.utils import page_df
from graphlens.graph import available_years, load_graph, GraphLensGraph


router = APIRouter(prefix="/graph", tags=["graph"])

# ── In-process graph cache (avoids rebuilding igraph on every request) ────────
_graph_cache: dict[int, GraphLensGraph] = {}

def _get_graph(year: int) -> GraphLensGraph:
    if year not in _graph_cache:
        if len(_graph_cache) >= 3:          # keep at most 3 years in memory
            _graph_cache.pop(next(iter(_graph_cache)))
        _graph_cache[year] = load_graph(year=year, min_amount=1.0)
    return _graph_cache[year]


@router.get("/years", response_model=YearListResponse)
def list_years() -> YearListResponse:
    return YearListResponse(years=available_years())


@router.get("/summary/{year}", response_model=GraphSummaryResponse)
def graph_summary(year: int) -> GraphSummaryResponse:
    glg = _get_graph(year)
    summary = glg.summary()
    return GraphSummaryResponse(**summary)


@router.get("/{year}", response_model=GraphPayloadResponse)
def graph_payload(
    year: int,
    node_limit: int = Query(300, ge=1, le=5000),
    edge_limit: int = Query(600, ge=1, le=20000),
) -> GraphPayloadResponse:
    glg = _get_graph(year)
    summary = GraphSummaryResponse(**glg.summary())

    nodes = page_df(glg.nodes, limit=node_limit, offset=0, sort_by="id", desc=False)
    edges = page_df(glg.edges, limit=edge_limit, offset=0, sort_by="total_amount", desc=True)

    return GraphPayloadResponse(
        summary=summary,
        nodes=TableResponse(columns=nodes.columns, total_rows=glg.nodes.height, rows=nodes.to_dicts()),
        edges=TableResponse(columns=edges.columns, total_rows=glg.edges.height, rows=edges.to_dicts()),
    )
