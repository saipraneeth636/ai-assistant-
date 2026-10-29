"""Analytics API routes."""

import logging
from fastapi import APIRouter, HTTPException

import analytics
from models import (
    MonthlyRevenueResponse,
    OverviewResponse,
    RegionRevenueResponse,
    TopProductsResponse,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
logger = logging.getLogger(__name__)


@router.get("/overview", response_model=OverviewResponse)
def overview():
    try:
        return analytics.get_overview()
    except Exception as e:
        logger.error("Overview query failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch overview data.")


@router.get("/monthly-revenue", response_model=MonthlyRevenueResponse)
def monthly_revenue():
    try:
        data = analytics.get_monthly_revenue()
        return {"data": data}
    except Exception as e:
        logger.error("Monthly revenue query failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch monthly revenue data.")


@router.get("/region-revenue", response_model=RegionRevenueResponse)
def region_revenue():
    try:
        data = analytics.get_region_revenue()
        return {"data": data}
    except Exception as e:
        logger.error("Region revenue query failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch region revenue data.")


@router.get("/top-products", response_model=TopProductsResponse)
def top_products():
    try:
        data = analytics.get_top_products()
        return {"data": data}
    except Exception as e:
        logger.error("Top products query failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch top products data.")
