"""
AI Assistant module for SalesIQ.

Architecture (safe-by-design):
  1.  Receive a natural-language question from the user.
  2.  Send the question + schema/business context to Groq to classify intent
      and extract parameters.  The LLM NEVER executes SQL or invents numbers.
  3.  Validate the returned intent against an explicit allowlist.
  4.  Execute a pre-defined, parameterised SQL query.
  5.  Return the real database results to the LLM to write a grounded answer.
  6.  Return both the answer text and the raw data to the frontend.

Supported intents (allowlist):
  - total_revenue       → overview KPI
  - top_product         → top-products ranking
  - monthly_trend       → monthly revenue series
  - region_revenue      → revenue by region
  - month_comparison    → compare two specific months
  - unsupported         → politely explain limitations

Security guarantees:
  - LLM cannot execute arbitrary SQL.
  - LLM cannot invent numbers; all figures come from SQLite.
  - GROQ_API_KEY is never exposed to the browser.
"""

import json
import logging
import re
from typing import Any, Optional

from config import GROQ_API_KEY, GROQ_MODEL
import analytics

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowlisted intents
# ---------------------------------------------------------------------------
SUPPORTED_INTENTS = {
    "total_revenue",
    "top_product",
    "monthly_trend",
    "region_revenue",
    "month_comparison",
    "unsupported",
}

SUPPORTED_QUESTIONS_DESCRIPTION = (
    "I can answer questions about: "
    "(1) total or net revenue, "
    "(2) which product generated the highest revenue, "
    "(3) monthly revenue trends, "
    "(4) which region generated the highest revenue, and "
    "(5) revenue comparison between two months."
)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------
INTENT_SYSTEM_PROMPT = """You are an intent classifier for a sales analytics assistant.
Your job is to classify the user's question into exactly one of these intents:
  - total_revenue: questions about total/overall/net revenue or sales
  - top_product: questions about the best-selling product or highest-revenue product
  - monthly_trend: questions about revenue by month or monthly trends
  - region_revenue: questions about revenue by region or highest-revenue region
  - month_comparison: questions comparing revenue between two specific months
  - unsupported: any other question

Dataset context:
  - Products: Laptop Stand, Wireless Mouse, Office Chair, Monitor, Keyboard, Desk, USB-C Hub
  - Regions: North, South, East, West
  - Months available: 2026-01 through 2026-06
  - Currency: INR (₹)

Respond ONLY with a JSON object in this exact format (no markdown, no extra text):
{"intent": "<intent_name>", "params": {"month1": "<YYYY-MM or null>", "month2": "<YYYY-MM or null>"}}

For month_comparison, extract both months as YYYY-MM strings.
For all other intents, set month1 and month2 to null.
"""

ANSWER_SYSTEM_PROMPT = """You are SalesIQ, a professional business intelligence assistant.
You have been given real data from a sales database. Use ONLY these numbers in your answer.
Do NOT invent, estimate, or approximate any figures.
Be concise (2–4 sentences), professional, and data-driven.
Format currency values in Indian Rupees (₹) with comma separators (e.g., ₹1,23,456).
"""


# ---------------------------------------------------------------------------
# Groq client (lazy init)
# ---------------------------------------------------------------------------
def _get_groq_client():
    """Return a Groq client, raising ValueError if key is not configured."""
    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY is not configured. "
            "Set the GROQ_API_KEY environment variable and restart the server."
        )
    try:
        # pyrefly: ignore[missing-import]
        from groq import Groq
        return Groq(api_key=GROQ_API_KEY)
    except ImportError as e:
        raise ImportError("groq package is not installed. Run: pip install groq") from e


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------
def _classify_intent(client, question: str) -> dict:
    """
    Call Groq to classify intent. Returns dict with 'intent' and 'params'.
    Raises on API errors.
    """
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0.0,
        max_tokens=150,
        timeout=15,
    )
    raw = response.choices[0].message.content.strip()

    # Strip potential markdown code fences
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip("` \n")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON for intent classification: %s", raw)
        return {"intent": "unsupported", "params": {}}

    intent = parsed.get("intent", "unsupported")
    if intent not in SUPPORTED_INTENTS:
        logger.warning("LLM returned unknown intent '%s'; defaulting to unsupported.", intent)
        intent = "unsupported"

    return {"intent": intent, "params": parsed.get("params", {})}


# ---------------------------------------------------------------------------
# Data fetching (safe, pre-defined SQL only)
# ---------------------------------------------------------------------------
def _fetch_data(intent: str, params: dict) -> tuple[Any, str]:
    """
    Execute the appropriate pre-defined query.
    Returns (data, data_summary_for_llm).
    """
    if intent == "total_revenue":
        data = analytics.get_overview()
        summary = (
            f"Total net revenue (Completed transactions): ₹{data['total_revenue']:,.2f}. "
            f"Transaction count: {data['transaction_count']}. "
            f"Returns: ₹{data['returns_value']:,.2f} ({data['returns_count']} transaction(s))."
        )
        return data, summary

    elif intent == "top_product":
        data = analytics.get_top_products(limit=10)
        top = data[0] if data else {}
        summary = (
            f"Top product by revenue: {top.get('product', 'N/A')} "
            f"with ₹{top.get('revenue', 0):,.2f} in revenue. "
            f"All products (ranked): "
            + ", ".join(
                f"{r['product']} ₹{r['revenue']:,.2f}" for r in data
            )
        )
        return data, summary

    elif intent == "monthly_trend":
        data = analytics.get_monthly_revenue()
        lines = [f"{r['month']}: ₹{r['revenue']:,.2f}" for r in data]
        summary = "Monthly revenue (Completed transactions): " + "; ".join(lines)
        return data, summary

    elif intent == "region_revenue":
        data = analytics.get_region_revenue()
        top = data[0] if data else {}
        lines = [f"{r['region']}: ₹{r['revenue']:,.2f}" for r in data]
        summary = (
            f"Highest-revenue region: {top.get('region', 'N/A')} "
            f"with ₹{top.get('revenue', 0):,.2f}. "
            f"All regions: " + "; ".join(lines)
        )
        return data, summary

    elif intent == "month_comparison":
        p = params or {}
        month1 = (p.get("month1") or "").strip()
        month2 = (p.get("month2") or "").strip()

        # Validate YYYY-MM format
        valid = re.compile(r"^\d{4}-\d{2}$")
        if not valid.match(month1) or not valid.match(month2):
            return None, "Could not extract two valid months (YYYY-MM) from the question."

        data = analytics.query_month_comparison(month1, month2)
        if len(data) < 2:
            found = [r["month"] for r in data]
            missing = [m for m in [month1, month2] if m not in found]
            summary = (
                f"Data found for: {found}. No data for: {missing}. "
                + (f"{data[0]['month']}: ₹{data[0]['revenue']:,.2f}" if data else "")
            )
        else:
            m1d = next((r for r in data if r["month"] == month1), data[0])
            m2d = next((r for r in data if r["month"] == month2), data[1])
            diff = m2d["revenue"] - m1d["revenue"]
            pct = (diff / m1d["revenue"] * 100) if m1d["revenue"] else 0
            summary = (
                f"{m1d['month']}: ₹{m1d['revenue']:,.2f}, "
                f"{m2d['month']}: ₹{m2d['revenue']:,.2f}. "
                f"Change: ₹{diff:,.2f} ({pct:+.1f}%)."
            )
        return data, summary

    else:  # unsupported
        return None, ""


# ---------------------------------------------------------------------------
# Answer generation
# ---------------------------------------------------------------------------
def _generate_answer(client, question: str, data_summary: str, intent: str) -> str:
    """Ask Groq to phrase a grounded answer given the real data."""
    if intent == "unsupported" or not data_summary:
        return (
            "I'm sorry, I can't answer that question with the current dataset. "
            + SUPPORTED_QUESTIONS_DESCRIPTION
        )

    user_prompt = (
        f"User question: {question}\n\n"
        f"Real data from the database:\n{data_summary}\n\n"
        "Write a concise, professional answer grounded in this data."
    )

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=300,
        timeout=15,
    )
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def answer_question(question: str) -> dict:
    """
    Main entry point. Returns dict with keys:
        question, answer, intent, data, error
    """
    result: dict = {
        "question": question,
        "answer": "",
        "intent": None,
        "data": None,
        "error": None,
    }

    # --- Guard: API key ---
    try:
        client = _get_groq_client()
    except ValueError as e:
        result["error"] = str(e)
        result["answer"] = (
            "The AI assistant is not configured. "
            "Please set the GROQ_API_KEY environment variable."
        )
        return result
    except ImportError as e:
        result["error"] = str(e)
        result["answer"] = "Internal error: Groq package not installed."
        return result

    # --- Step 1: Intent classification ---
    try:
        classification = _classify_intent(client, question)
    except Exception as e:
        logger.error("Groq intent classification failed: %s", e)
        result["error"] = f"AI service error: {type(e).__name__}"
        result["answer"] = (
            "The AI service is temporarily unavailable. "
            "Please try again in a moment."
        )
        return result

    intent = classification["intent"]
    params = classification.get("params", {})
    result["intent"] = intent

    # --- Step 2: Fetch real data ---
    try:
        data, data_summary = _fetch_data(intent, params)
        result["data"] = data
    except Exception as e:
        logger.error("Analytics query failed for intent '%s': %s", intent, e)
        result["error"] = f"Database query error: {type(e).__name__}"
        result["answer"] = "An error occurred while querying the database."
        return result

    # --- Step 3: Generate grounded answer ---
    try:
        result["answer"] = _generate_answer(client, question, data_summary, intent)
    except Exception as e:
        logger.error("Groq answer generation failed: %s", e)
        # Fall back to the raw data summary as the answer
        result["answer"] = (
            data_summary
            if data_summary
            else (
                "I could not generate an explanation. "
                "The raw data is available in the response."
            )
        )
        result["error"] = f"Answer generation error: {type(e).__name__}"

    return result
