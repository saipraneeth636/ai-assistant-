"""
Pydantic schemas for SalesIQ API request/response models.
"""

from typing import Any, Optional
# pyrefly: ignore[missing-import]
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Overview / KPI
# ---------------------------------------------------------------------------
class OverviewResponse(BaseModel):
    total_revenue: float
    transaction_count: int
    product_count: int
    region_count: int
    returns_value: float
    returns_count: int
    total_transactions: int


# ---------------------------------------------------------------------------
# Monthly Revenue
# ---------------------------------------------------------------------------
class MonthlyRevenueItem(BaseModel):
    month: str
    revenue: float
    transaction_count: int


class MonthlyRevenueResponse(BaseModel):
    data: list[MonthlyRevenueItem]


# ---------------------------------------------------------------------------
# Region Revenue
# ---------------------------------------------------------------------------
class RegionRevenueItem(BaseModel):
    region: str
    revenue: float
    transaction_count: int


class RegionRevenueResponse(BaseModel):
    data: list[RegionRevenueItem]


# ---------------------------------------------------------------------------
# Top Products
# ---------------------------------------------------------------------------
class TopProductItem(BaseModel):
    product: str
    category: str
    revenue: float
    total_quantity: int
    transaction_count: int
    avg_unit_price: float


class TopProductsResponse(BaseModel):
    data: list[TopProductItem]


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)


class ChatResponse(BaseModel):
    question: str
    answer: str
    intent: Optional[str] = None
    data: Optional[Any] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------
class SuggestionsResponse(BaseModel):
    suggestions: list[str]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str
    version: str
    groq_configured: bool
