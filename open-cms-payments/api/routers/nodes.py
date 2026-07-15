#! usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import APIRouter, Query    # type: ignore[import-not-found]
import polars as pl     # type: ignore[import-not-found]

from api.schemas import NodeDetailsResponse, TableResponse
from api.utils import page_df
from graphlens.graph import load_graph, load_nodes


router = APIRouter(prefix="/nodes", tags=["nodes"])


@router.get("/", response_model=TableResponse)
def list_nodes(
    year: int | None = Query(default=None),
    node_type: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> TableResponse:
    nodes = load_nodes()

    if node_type:
        nodes = nodes.filter(pl.col("node_type") == node_type)

    if q:
        q_lower = q.lower()
        if "name" in nodes.columns:
            nodes = nodes.filter(
                pl.col("name").fill_null("").str.to_lowercase().str.contains(q_lower, literal=True)
            )

    if year is not None:
        glg = load_graph(year=year, min_amount=1.0)
        active_ids = set(glg.nodes["id"].cast(str).to_list())
        nodes = nodes.filter(pl.col("id").cast(pl.Utf8).is_in(active_ids))

    total = nodes.height
    page = page_df(nodes, limit=limit, offset=offset, sort_by="name", desc=False)
    return TableResponse(columns=page.columns, total_rows=total, rows=page.to_dicts())


@router.get("/{year}/{node_id}", response_model=NodeDetailsResponse)
def node_details(
    year: int,
    node_id: str,
    edge_limit: int = Query(500, ge=1, le=5000),
) -> NodeDetailsResponse:
    glg = load_graph(year=year, min_amount=1.0)
    nodes = glg.nodes.filter(pl.col("id").cast(pl.Utf8) == node_id)
    if nodes.is_empty():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found for year {year}")

    outgoing_all = glg.edges.filter(pl.col("src_id").cast(pl.Utf8) == node_id)
    outgoing_total = outgoing_all.height
    outgoing = page_df(outgoing_all, limit=edge_limit, offset=0, sort_by="total_amount", desc=True)

    incoming_all = glg.edges.filter(pl.col("dst_id").cast(pl.Utf8) == node_id)
    incoming_total = incoming_all.height
    incoming = page_df(incoming_all, limit=edge_limit, offset=0, sort_by="total_amount", desc=True)

    return NodeDetailsResponse(
        node=nodes.row(0, named=True),
        outgoing_edges=TableResponse(columns=outgoing.columns, total_rows=outgoing_total, rows=outgoing.to_dicts()),
        incoming_edges=TableResponse(columns=incoming.columns, total_rows=incoming_total, rows=incoming.to_dicts()),
    )
