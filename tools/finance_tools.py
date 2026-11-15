"""Tool-enabled data access for the finance agent.

These tools intentionally expose only read-only database queries so the model can
fetch approved portfolio, risk, and market data without mutating the system.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine

from services.database import (
    asset_risk_logs,
    document_chunks,
    document_versions,
    market_indicators,
    portfolio_holdings,
    portfolios,
    source_documents,
)

try:
    from langchain_core.tools import tool
except ImportError:  # pragma: no cover - exercised when langchain is absent.
    def tool(*_args: Any, **_kwargs: Any):
        def decorator(func: Any) -> Any:
            return func

        return decorator


_TOOL_ENGINE: Engine | None = None


def configure_finance_tools(engine: Engine | None = None) -> list[Any]:
    """Register the current SQL engine for tool execution."""
    global _TOOL_ENGINE
    _TOOL_ENGINE = engine
    return [
        get_portfolio_summary,
        get_risk_snapshot,
        get_market_indicators,
        search_policy_documents,
    ]


def _require_engine() -> Engine:
    if _TOOL_ENGINE is None:
        raise RuntimeError("Finance tools are not configured with a database engine.")
    return _TOOL_ENGINE


@tool
def get_portfolio_summary(portfolio_id: int) -> str:
    """Return the portfolio summary plus top holding allocation details."""
    engine = _require_engine()
    with engine.connect() as connection:
        portfolio_row = connection.execute(
            select(portfolios).where(portfolios.c.portfolio_id == portfolio_id)
        ).mappings().first()
        if portfolio_row is None:
            return json.dumps({"error": "Portfolio not found."})
        holding_rows = connection.execute(
            select(portfolio_holdings)
            .where(portfolio_holdings.c.portfolio_id == portfolio_id)
            .order_by(portfolio_holdings.c.allocation_percentage.desc())
            .limit(10)
        ).mappings().all()

    holdings = [
        {
            "holding_id": row["holding_id"],
            "asset_name": row["asset_name"],
            "asset_type": row["asset_type"],
            "sector": row["sector"],
            "allocation_percentage": float(row["allocation_percentage"])
            if row["allocation_percentage"] is not None
            else None,
            "market_value": float(row["market_value"])
            if row["market_value"] is not None
            else None,
        }
        for row in holding_rows
    ]
    summary = {
        "portfolio_id": portfolio_row["portfolio_id"],
        "portfolio_name": portfolio_row["portfolio_name"],
        "portfolio_manager": portfolio_row["portfolio_manager"],
        "risk_category": portfolio_row["risk_category"],
        "benchmark_index": portfolio_row["benchmark_index"],
        "total_value": float(portfolio_row["total_value"])
        if portfolio_row["total_value"] is not None
        else None,
        "holding_count": len(holdings),
        "top_holdings": holdings,
    }
    return json.dumps(summary)


@tool
def get_risk_snapshot(
    portfolio_id: int | None = None,
    asset_name: str | None = None,
    risk_level: str | None = None,
) -> str:
    """Return risk records filtered by portfolio or asset name, limited to read-only output."""
    engine = _require_engine()
    stmt = select(asset_risk_logs)
    if portfolio_id is not None:
        portfolio_assets = select(portfolio_holdings.c.asset_name).where(
            portfolio_holdings.c.portfolio_id == portfolio_id
        )
        stmt = stmt.where(asset_risk_logs.c.asset_name.in_(portfolio_assets))
    if asset_name:
        stmt = stmt.where(asset_risk_logs.c.asset_name == asset_name)
    if risk_level:
        stmt = stmt.where(asset_risk_logs.c.risk_level == risk_level)
    stmt = stmt.order_by(asset_risk_logs.c.assessment_date.desc(), asset_risk_logs.c.risk_id.desc()).limit(20)
    with engine.connect() as connection:
        rows = connection.execute(stmt).mappings().all()

    result = [
        {
            "risk_id": row["risk_id"],
            "asset_name": row["asset_name"],
            "risk_type": row["risk_type"],
            "risk_score": row["risk_score"],
            "risk_level": row["risk_level"],
            "risk_description": row["risk_description"],
            "assessment_date": str(row["assessment_date"])
            if row["assessment_date"] is not None
            else None,
            "escalation_flag": bool(row["escalation_flag"]),
        }
        for row in rows
    ]
    return json.dumps({"risk_records": result})


@tool
def get_market_indicators(region: str | None = None, limit: int = 5) -> str:
    """Fetch tailored market indicators with optional region filters."""
    if limit <= 0:
        limit = 5
    engine = _require_engine()
    stmt = select(market_indicators)
    if region:
        stmt = stmt.where(market_indicators.c.region == region)
    stmt = stmt.order_by(
        market_indicators.c.measurement_date.desc(),
        market_indicators.c.indicator_id.desc(),
    ).limit(limit)
    with engine.connect() as connection:
        rows = connection.execute(stmt).mappings().all()

    result = [
        {
            "indicator_id": row["indicator_id"],
            "indicator_name": row["indicator_name"],
            "region": row["region"],
            "indicator_value": float(row["indicator_value"])
            if row["indicator_value"] is not None
            else None,
            "measurement_date": str(row["measurement_date"])
            if row["measurement_date"] is not None
            else None,
            "trend_direction": row["trend_direction"],
        }
        for row in rows
    ]
    return json.dumps({"market_indicators": result})


@tool
def search_policy_documents(query: str, limit: int = 3) -> str:
    """Search approved policy and compliance documents using title and chunk text."""
    if not query.strip():
        return json.dumps({"error": "A search query is required."})
    if limit <= 0:
        limit = 3
    engine = _require_engine()
    with engine.connect() as connection:
        rows = connection.execute(
            select(
                source_documents.c.source_key,
                source_documents.c.title,
                document_chunks.c.chunk_id,
                document_chunks.c.chunk_text,
                document_chunks.c.section_path,
            )
            .join(
                document_versions,
                document_versions.c.document_version_id == document_chunks.c.document_version_id,
            )
            .join(
                source_documents,
                source_documents.c.document_id == document_versions.c.document_id,
            )
            .where(
                source_documents.c.approved.is_(True),
                source_documents.c.enabled.is_(True),
                document_chunks.c.chunk_text.is_not(None),
            )
            .order_by(document_chunks.c.chunk_id)
            .limit(50)
        ).mappings().all()

    query_lower = query.lower()
    matches = []
    for row in rows:
        haystack = "\n".join(
            [
                str(row["title"] or ""),
                str(row["section_path"] or ""),
                str(row["chunk_text"] or ""),
            ]
        ).lower()
        if query_lower in haystack:
            matches.append(
                {
                    "source_key": row["source_key"],
                    "title": row["title"],
                    "chunk_id": row["chunk_id"],
                    "section_path": row["section_path"],
                    "excerpt": (row["chunk_text"] or "")[:400],
                }
            )
        if len(matches) >= limit:
            break

    return json.dumps({"matches": matches})
