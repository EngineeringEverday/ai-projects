#! usr/bin/env python3
# -*- coding: utf-8 -*-

"""
analytics.centrality
====================
Compute node-level influence and structural centrality metrics.

All public functions return a pl.DataFrame with one row per node,
indexed by the node's string id.

Metrics
-------
  pagerank          : Weighted PageRank (damping=0.85) - structural influence
  in_degree         : Raw count of unique payers (companies) per recipient
  out_degree        : Raw count of unique recipients per company
  in_strength       : Sum of incoming payment weights (total received USD)
  out_strength      : Sum of outgoing payment weights (total paid USD)
  betweenness       : Normalized edge-weighted betweenness centrality
                      (approximate for large graphs via sampling)
  hub_score         : HITS hub score (companies that fund many influential physicians)
  authority_score   : HITS authority score (physicians funded by many influential companies)
  payment_diversity : Number of distinct companies paying a physician (or vice versa)
"""

import math
from typing import TYPE_CHECKING

import polars as pl  # type: ignore[import-not-found]
import igraph as ig  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from graphlens.graph import GraphLensGraph


# Public API
def compute_all_centrality(
    glg: "GraphLensGraph",
    betweenness_samples: int | None = 200,
) -> pl.DataFrame:
    """
    Compute the full centrality suite and return one merged DataFrame.

    Parameters
    ----------
    glg                  : GraphLensGraph to analyse.
    betweenness_samples  : Number of source vertices sampled for approximate
                           betweenness.  None = exact (slow for large graphs).

    Returns
    -------
    pl.DataFrame with columns:
        id, node_type, name, state, specialty, credential_type,
        pagerank, in_degree, out_degree,
        in_strength, out_strength, strength_ratio,
        betweenness, hub_score, authority_score,
        payment_diversity, log_in_strength,
        cash_ratio, disputed_ratio, third_party_ratio
    """
    G = glg.ig
    n = G.vcount()

    if n == 0:
        return pl.DataFrame()

    # PageRank (weighted, damping 0.85)
    pr = G.pagerank(
        directed=True,
        weights="weight" if G.ecount() > 0 else None,
        damping=0.85,
    )

    #  Degree (structural)
    in_deg = G.degree(mode="in")
    out_deg = G.degree(mode="out")

    # Strength (sum of weights)
    in_str = G.strength(mode="in", weights="weight") if G.ecount() > 0 else [0.0] * n
    out_str = G.strength(mode="out", weights="weight") if G.ecount() > 0 else [0.0] * n

    # strength_ratio
    strength_ratio = [
        (ins / (outs + 1.0)) if ntype == "Physician" else (outs / (ins + 1.0))
        for ins, outs, ntype in zip(in_str, out_str, G.vs["node_type"])
    ]

    #  Betweenness
    if G.ecount() > 0:
        btw = _betweenness(G, samples=betweenness_samples)
    else:
        btw = [0.0] * n

    # HITS (hub & authority)
    hub_scores, auth_scores = _hits(G)

    # Payment diversity: distinct trading partners
    diversity = _payment_diversity(G)

    # log-transformed in_strength (for anomaly layer)
    log_in_str = [math.log1p(v) for v in in_str]

    # Cash ratio: share of incoming weight that is cash payments
    # Uses payment_forms edge attribute added by the new ETL
    cash_ratio = [0.0] * n
    disputed_ratio = [0.0] * n
    third_party_ratio = [0.0] * n

    has_payment_forms = "payment_forms" in G.es.attribute_names()
    has_disputed = "disputed_count" in G.es.attribute_names()
    has_payment_count = "payment_count" in G.es.attribute_names()
    has_third_party = "third_party_count" in G.es.attribute_names()

    if G.ecount() > 0 and (has_payment_forms or has_disputed or has_third_party):
        # Accumulate per-target-node
        cash_in = [0.0] * n
        disput_in = [0.0] * n
        third_in = [0.0] * n
        total_in = [0.0] * n

        for e in G.es:
            w = e["weight"]
            tgt = e.target
            total_in[tgt] += w

            if has_payment_forms:
                forms = (e["payment_forms"] or "").lower()
                if "cash" in forms:
                    cash_in[tgt] += w

            if has_disputed:
                dc = e["disputed_count"] or 0
                pc = e["payment_count"] or 1 if has_payment_count else 1
                disput_in[tgt] += dc / max(pc, 1) * w

            if has_third_party:
                tc = e["third_party_count"] or 0
                pc = e["payment_count"] or 1 if has_payment_count else 1
                third_in[tgt] += tc / max(pc, 1) * w

        cash_ratio = [c / max(t, 1e-9) for c, t in zip(cash_in, total_in)]
        disputed_ratio = [d / max(t, 1e-9) for d, t in zip(disput_in, total_in)]
        third_party_ratio = [tp / max(t, 1e-9) for tp, t in zip(third_in, total_in)]

    # Assemble DataFrame #
    rows = {
        "id": G.vs["id"],
        "node_type": G.vs["node_type"],
        "name": G.vs["name"],
        "state": G.vs["state"],
        "specialty": G.vs["specialty"],
        "credential_type": G.vs["credential_type"] if "credential_type" in G.vs.attribute_names() else [""] * n,
        "pagerank": pr,
        "in_degree": in_deg,
        "out_degree": out_deg,
        "in_strength": in_str,
        "out_strength": out_str,
        "strength_ratio": strength_ratio,
        "betweenness": btw,
        "hub_score": hub_scores,
        "authority_score": auth_scores,
        "payment_diversity": diversity,
        "log_in_strength": log_in_str,
        "cash_ratio": cash_ratio,
        "disputed_ratio": disputed_ratio,
        "third_party_ratio": third_party_ratio,
    }

    return pl.DataFrame(rows).with_columns([
        pl.col("id").cast(pl.Utf8),
        pl.col("pagerank").cast(pl.Float64),
        pl.col("in_strength").cast(pl.Float64),
        pl.col("out_strength").cast(pl.Float64),
        pl.col("betweenness").cast(pl.Float64),
        pl.col("hub_score").cast(pl.Float64),
        pl.col("authority_score").cast(pl.Float64),
        pl.col("log_in_strength").cast(pl.Float64),
        pl.col("cash_ratio").cast(pl.Float64),
        pl.col("disputed_ratio").cast(pl.Float64),
        pl.col("third_party_ratio").cast(pl.Float64),
    ])


def compute_pagerank(
    glg: "GraphLensGraph",
    damping: float = 0.85,
) -> pl.DataFrame:
    """Lightweight PageRank-only computation."""
    G = glg.ig
    pr = G.pagerank(
        directed=True,
        weights="weight" if G.ecount() > 0 else None,
        damping=damping,
    )
    return pl.DataFrame({
        "id": G.vs["id"],
        "node_type": G.vs["node_type"],
        "pagerank": pr,
    }).with_columns(pl.col("pagerank").cast(pl.Float64))


def compute_degree_strength(glg: "GraphLensGraph") -> pl.DataFrame:
    """Degree and weighted strength for all nodes."""
    G = glg.ig
    n = G.vcount()
    return pl.DataFrame({
        "id": G.vs["id"],
        "node_type": G.vs["node_type"],
        "in_degree": G.degree(mode="in"),
        "out_degree": G.degree(mode="out"),
        "in_strength": G.strength(mode="in", weights="weight") if G.ecount() > 0 else [0.0] * n,
        "out_strength": G.strength(mode="out", weights="weight") if G.ecount() > 0 else [0.0] * n,
    })


# Internal algorithms
def _betweenness(G: ig.Graph, samples: int | None = 200) -> list[float]:
    """
    Compute normalised betweenness centrality.

    Uses igraph's built-in estimate_betweenness when samples is set
    (O(k x E) instead of O(V x E)), exact otherwise.

    Edge weights are interpreted as distances (shorter = more central path),
    so we pass 1/weight as the distance for monetary-flow graphs.
    """
    n = G.vcount()
    if n <= 1 or G.ecount() == 0:
        return [0.0] * n

    # Convert weights to distances (inverse): heavier edge = shorter path
    raw_weights = G.es["weight"]
    max_w = max(raw_weights) if raw_weights else 1.0
    distances = [max_w / (w + 1e-9) for w in raw_weights]

    try:
        if samples and n > samples * 2:
            btw = G.estimate_betweenness(
                directed=True,
                cutoff=None,
                samples=samples,
                weights=distances,
            )
        else:
            btw = G.betweenness(
                directed=True,
                weights=distances,
            )
    except Exception:
        # Fall back to unweighted if something goes wrong
        btw = G.betweenness(directed=True)

    # Normalise to [0, 1]
    max_btw = max(btw) if btw else 1.0
    if max_btw == 0:
        return [0.0] * n
    return [b / max_btw for b in btw]


def _hits(G: ig.Graph) -> tuple[list[float], list[float]]:
    """
    Power-iteration HITS (Kleinberg 1999).
    Returns (hub_scores, authority_scores) both normalised to [0,1].
    """
    n = G.vcount()
    if n == 0 or G.ecount() == 0:
        return [0.0] * n, [0.0] * n

    # Sparse adjacency via igraph edge lists
    edge_src = [e.source for e in G.es]
    edge_dst = [e.target for e in G.es]
    weights = G.es["weight"]

    hub = [1.0] * n
    auth = [1.0] * n

    for _ in range(30):  # 30 iterations usually sufficient
        # authority ← sum of hub scores of in-neighbours (weighted)
        new_auth = [0.0] * n
        for s, d, w in zip(edge_src, edge_dst, weights):
            new_auth[d] += hub[s] * w

        # hub ← sum of authority scores of out-neighbours (weighted)
        new_hub = [0.0] * n
        for s, d, w in zip(edge_src, edge_dst, weights):
            new_hub[s] += new_auth[d] * w

        # Normalise
        norm_a = sum(a * a for a in new_auth) ** 0.5 or 1.0
        norm_h = sum(h * h for h in new_hub) ** 0.5 or 1.0
        auth = [a / norm_a for a in new_auth]
        hub = [h / norm_h for h in new_hub]

    max_h = max(hub) or 1.0
    max_a = max(auth) or 1.0
    return [h / max_h for h in hub], [a / max_a for a in auth]


def _payment_diversity(G: ig.Graph) -> list[int]:
    """
    For each node: number of distinct counterparties (in + out).
    For physicians: how many distinct companies pay them.
    For companies: how many distinct physicians they pay.
    """
    n = G.vcount()
    partners: list[set[int]] = [set() for _ in range(n)]
    for e in G.es:
        partners[e.source].add(e.target)
        partners[e.target].add(e.source)
    return [len(p) for p in partners]
