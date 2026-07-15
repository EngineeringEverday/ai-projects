#! usr/bin/env python3
# -*- coding: utf-8 -*-


from fastapi import APIRouter, Query    # type: ignore[import-not-found]

from api.schemas import (
    DashboardOverviewResponse,
    DashboardSectionResponse,
    GraphSummaryResponse,
    TableResponse,
)
from api.utils import page_df, read_analytics_table
from graphlens.graph import load_graph


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _table(df, limit: int, sort_by: str | None = None, desc: bool = True) -> TableResponse:
    total = df.height
    page = page_df(df, limit=limit, offset=0, sort_by=sort_by, desc=desc)
    return TableResponse(columns=page.columns, total_rows=total, limit=limit, offset=0, rows=page.to_dicts())


@router.get("/{year}/overview", response_model=DashboardOverviewResponse)
def dashboard_overview(
    year: int,
    top_k: int = Query(10, ge=3, le=100),
) -> DashboardOverviewResponse:
    glg = load_graph(year=year, min_amount=1.0)
    summary = GraphSummaryResponse(**glg.summary())

    centrality = read_analytics_table("node_metrics", year)
    anomalies = read_analytics_table("anomaly_scores", year)
    concentration = read_analytics_table("concentration_specialty", year)
    communities = read_analytics_table("community_summaries", year)
    top_drug = read_analytics_table("top_products_drug", year)
    top_device = read_analytics_table("top_products_device", year)

    sections = [
        DashboardSectionResponse(
            title="Top Centrality (PageRank)",
            table=_table(
                centrality.select([c for c in ["id", "name", "node_type", "pagerank", "in_strength"] if c in centrality.columns]),
                limit=top_k,
                sort_by="pagerank",
            ),
        ),
        DashboardSectionResponse(
            title="Top Anomalies",
            table=_table(
                anomalies.select([c for c in ["id", "name", "specialty", "composite_anomaly_score", "capture_ratio"] if c in anomalies.columns]),
                limit=top_k,
                sort_by="composite_anomaly_score",
            ),
        ),
        DashboardSectionResponse(
            title="Top Communities",
            table=_table(
                communities,
                limit=top_k,
                sort_by="total_payment_usd",
            ),
        ),
        DashboardSectionResponse(
            title="Concentration by Specialty",
            table=_table(
                concentration,
                limit=top_k,
                sort_by="total_payment",
            ),
        ),
        DashboardSectionResponse(
            title="Top Drug Products",
            table=_table(
                top_drug,
                limit=top_k,
                sort_by="n_records",
            ),
        ),
        DashboardSectionResponse(
            title="Top Device Products",
            table=_table(
                top_device,
                limit=top_k,
                sort_by="n_records",
            ),
        ),
    ]

    return DashboardOverviewResponse(
        year=year,
        summary=summary,
        sections=sections,
    )


@router.get("/{year}/graph-snapshot", response_model=TableResponse)
def graph_snapshot(
    year: int,
    edge_limit: int = Query(2000, ge=100, le=20000),
) -> TableResponse:
    glg = load_graph(year=year, min_amount=1.0)
    edges = page_df(glg.edges, limit=edge_limit, offset=0, sort_by="total_amount", desc=True)
    return TableResponse(columns=edges.columns, total_rows=glg.edges.height, limit=edge_limit, offset=0, rows=edges.to_dicts())
