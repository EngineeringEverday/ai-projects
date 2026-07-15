#! usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import FastAPI     # type: ignore[import-not-found]
from fastapi.middleware.cors import CORSMiddleware      # type: ignore[import-not-found]
from fastapi.middleware.gzip import GZipMiddleware      # type: ignore[import-not-found]
import os

from api.routers import anomalies, centrality, communities, concentration, dashboard, graph, nodes, products, temporal
from api.schemas import HealthResponse
from api.utils import ANALYTICS_JSON_DIR, ANALYTICS_PARQUET_DIR, analytics_cache_stats
from graphlens.graph import available_years


app = FastAPI(
    title="GraphLens API",
    description="Versioned FastAPI backend serving graph and precomputed analytics parquet outputs.",
    version="1.0.0",
)

cors_origins_raw = os.getenv("CORS_ORIGINS", "*")
allowed_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.get("/")
def root() -> dict[str, object]:
    return {
        "service": "GraphLens API",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
        "meta": "/api/meta",
        "api_base": "/api/v1",
        "available_years": available_years(),
    }


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    yrs = available_years()
    return HealthResponse(
        status="ok",
        message=f"GraphLens API healthy. Available years: {yrs}",
    )


@app.get("/api/meta")
def api_meta() -> dict[str, object]:
    return {
        "api_version": "v1",
        "available_years": available_years(),
        "analytics_json_dir": str(ANALYTICS_JSON_DIR),
        "analytics_parquet_dir": str(ANALYTICS_PARQUET_DIR),
        "gzip_enabled": True,
        "analytics_source_priority": ["json", "parquet"],
        "analytics_cache": analytics_cache_stats(),
    }


API_V1 = "/api/v1"

# Core graph resources
app.include_router(graph.router, prefix=API_V1)
app.include_router(nodes.router, prefix=API_V1)

# Analytics resources grouped under /analytics
app.include_router(centrality.router, prefix=f"{API_V1}/analytics")
app.include_router(communities.router, prefix=f"{API_V1}/analytics")
app.include_router(concentration.router, prefix=f"{API_V1}/analytics")
app.include_router(anomalies.router, prefix=f"{API_V1}/analytics")
app.include_router(temporal.router, prefix=f"{API_V1}/analytics")
app.include_router(products.router, prefix=f"{API_V1}/analytics")

# Frontend-friendly grouped endpoints
app.include_router(dashboard.router, prefix=API_V1)

# Backward-compatible legacy mounts (/api/*)
app.include_router(graph.router, prefix="/api")
app.include_router(nodes.router, prefix="/api")
app.include_router(centrality.router, prefix="/api")
app.include_router(communities.router, prefix="/api")
app.include_router(concentration.router, prefix="/api")
app.include_router(anomalies.router, prefix="/api")
app.include_router(temporal.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
