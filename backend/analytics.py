"""
SQL-based analytics functions for SalesIQ.

Revenue policy (mirrored from database.py):
  - Revenue = (Quantity × Unit_Price) - Discount_Amount
  - Status = 'Returned' transactions are EXCLUDED from all revenue sums.
  - Returns are reported separately via the `returns_value` field in overview.
"""

import sqlite3
from typing import Any

from database import get_connection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _fetchall(sql: str, params: tuple = ()) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def _fetchone(sql: str, params: tuple = ()) -> dict:
    with get_connection() as conn:
        row = conn.execute(sql, params).fetchone()
    return dict(row) if row else {}


# ---------------------------------------------------------------------------
# 1. Overview KPIs
# ---------------------------------------------------------------------------
def get_overview() -> dict[str, Any]:
    """
    Returns:
        total_revenue       – Net revenue from Completed transactions only (INR)
        transaction_count   – Number of Completed transactions (excl. returns)
        product_count       – Distinct products across all transactions
        region_count        – Distinct regions
        returns_value       – Gross value of Returned transactions (shown separately)
        returns_count       – Number of Returned transactions
        total_transactions  – All imported transactions (incl. returns)
    """
    completed = _fetchone(
        """
        SELECT
            COALESCE(SUM(revenue), 0)   AS total_revenue,
            COUNT(*)                    AS transaction_count
        FROM sales
        WHERE status = 'Completed'
        """
    )
    returns = _fetchone(
        """
        SELECT
            COALESCE(SUM(revenue), 0)   AS returns_value,
            COUNT(*)                    AS returns_count
        FROM sales
        WHERE status = 'Returned'
        """
    )
    misc = _fetchone(
        """
        SELECT
            COUNT(DISTINCT product) AS product_count,
            COUNT(DISTINCT region)  AS region_count,
            COUNT(*)                AS total_transactions
        FROM sales
        """
    )
    return {
        "total_revenue": round(completed["total_revenue"], 2),
        "transaction_count": completed["transaction_count"],
        "product_count": misc["product_count"],
        "region_count": misc["region_count"],
        "returns_value": round(returns["returns_value"], 2),
        "returns_count": returns["returns_count"],
        "total_transactions": misc["total_transactions"],
    }


# ---------------------------------------------------------------------------
# 2. Monthly Revenue
# ---------------------------------------------------------------------------
def get_monthly_revenue() -> list[dict]:
    """
    Returns monthly revenue for Completed transactions, ordered chronologically.
    Month label: YYYY-MM (e.g., '2026-01').
    """
    return _fetchall(
        """
        SELECT
            SUBSTR(order_date, 1, 7)        AS month,
            ROUND(SUM(revenue), 2)          AS revenue,
            COUNT(*)                        AS transaction_count
        FROM sales
        WHERE status = 'Completed'
        GROUP BY month
        ORDER BY month ASC
        """
    )


# ---------------------------------------------------------------------------
# 3. Regional Revenue
# ---------------------------------------------------------------------------
def get_region_revenue() -> list[dict]:
    """Returns revenue per region for Completed transactions, descending."""
    return _fetchall(
        """
        SELECT
            region,
            ROUND(SUM(revenue), 2)  AS revenue,
            COUNT(*)                AS transaction_count
        FROM sales
        WHERE status = 'Completed'
        GROUP BY region
        ORDER BY revenue DESC
        """
    )


# ---------------------------------------------------------------------------
# 4. Top Products
# ---------------------------------------------------------------------------
def get_top_products(limit: int = 10) -> list[dict]:
    """Returns top products by revenue for Completed transactions."""
    return _fetchall(
        """
        SELECT
            product,
            category,
            ROUND(SUM(revenue), 2)          AS revenue,
            SUM(quantity)                   AS total_quantity,
            COUNT(*)                        AS transaction_count,
            ROUND(AVG(unit_price), 2)       AS avg_unit_price
        FROM sales
        WHERE status = 'Completed'
        GROUP BY product
        ORDER BY revenue DESC
        LIMIT ?
        """,
        (limit,),
    )


# ---------------------------------------------------------------------------
# 5. Analytics for AI assistant (parameterised, safe queries)
# ---------------------------------------------------------------------------
def query_total_revenue() -> dict:
    return get_overview()


def query_top_product() -> list[dict]:
    return get_top_products(limit=10)


def query_monthly_trend() -> list[dict]:
    return get_monthly_revenue()


def query_region_revenue() -> list[dict]:
    return get_region_revenue()


def query_month_comparison(month1: str, month2: str) -> list[dict]:
    """
    Compare revenue between two months.
    month1/month2 must be in YYYY-MM format.
    """
    months = (month1, month2)
    return _fetchall(
        """
        SELECT
            SUBSTR(order_date, 1, 7)        AS month,
            ROUND(SUM(revenue), 2)          AS revenue,
            COUNT(*)                        AS transaction_count
        FROM sales
        WHERE status = 'Completed'
          AND SUBSTR(order_date, 1, 7) IN (?, ?)
        GROUP BY month
        ORDER BY month ASC
        """,
        months,
    )
