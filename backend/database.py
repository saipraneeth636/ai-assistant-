"""
Database initialization and CSV import for SalesIQ.

Revenue policy (documented):
  - Revenue = (Quantity × Unit_Price) - Discount_Amount
  - Discount_Amount is a FLAT amount in INR (not a percentage).
  - Returned transactions (Status = 'Returned') are stored in the database
    but EXCLUDED from all revenue aggregations. Their gross value is shown
    separately as a "returns" figure in the overview KPI.
  - TXN0034 (Quantity = 0) is excluded during import (zero-value transaction).
  - TXN0051 has a missing Unit_price; it is imputed to ₹1,200 based on the
    consistent price of Laptop Stand across all other transactions.

Date format in the CSV: DD-MM-YYYY  (e.g., 03-01-2026 → 3 Jan 2026)
Dates are stored in SQLite as ISO-format strings: YYYY-MM-DD for easy sorting.
"""

import csv
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Generator

from config import CSV_PATH, DATABASE_PATH

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sales (
    transaction_id  TEXT PRIMARY KEY,
    order_date      TEXT NOT NULL,          -- ISO format YYYY-MM-DD
    product         TEXT NOT NULL,
    category        TEXT NOT NULL,
    region          TEXT NOT NULL,
    sales_channel   TEXT NOT NULL,
    quantity        INTEGER NOT NULL,
    unit_price      REAL NOT NULL,
    discount_amount REAL NOT NULL DEFAULT 0,
    status          TEXT NOT NULL,
    revenue         REAL NOT NULL           -- pre-computed; see policy above
);
"""

CREATE_META_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS import_meta (
    id           INTEGER PRIMARY KEY,
    imported_at  TEXT NOT NULL,
    row_count    INTEGER NOT NULL
);
"""

# Imputed price for TXN0051 (Laptop Stand, missing Unit_price)
LAPTOP_STAND_IMPUTED_PRICE = 1200.0


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------
@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Yield a SQLite connection with row_factory set."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def init_db() -> None:
    """Create tables and import CSV (idempotent)."""
    with get_connection() as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.execute(CREATE_META_TABLE_SQL)

    _import_csv_if_needed()


def _import_csv_if_needed() -> None:
    """Import the CSV only if the sales table is empty (prevents duplicates)."""
    with get_connection() as conn:
        existing = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        if existing > 0:
            logger.info("Database already populated (%d rows). Skipping import.", existing)
            return

        rows = _parse_csv()
        if not rows:
            logger.warning("CSV produced no valid rows. Check the file at %s", CSV_PATH)
            return

        conn.executemany(
            """
            INSERT OR IGNORE INTO sales
                (transaction_id, order_date, product, category, region,
                 sales_channel, quantity, unit_price, discount_amount, status, revenue)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    r["transaction_id"],
                    r["order_date"],
                    r["product"],
                    r["category"],
                    r["region"],
                    r["sales_channel"],
                    r["quantity"],
                    r["unit_price"],
                    r["discount_amount"],
                    r["status"],
                    r["revenue"],
                )
                for r in rows
            ],
        )
        conn.execute(
            "INSERT INTO import_meta (imported_at, row_count) VALUES (?, ?)",
            (datetime.utcnow().isoformat(), len(rows)),
        )
        logger.info("Imported %d rows into sales table.", len(rows))


def _parse_csv() -> list[dict]:
    """Parse and validate CSV rows; apply imputation and exclusion rules."""
    if not CSV_PATH.exists():
        logger.error("CSV not found at %s", CSV_PATH)
        return []

    records: list[dict] = []

    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            txn_id = row.get("Transaction_Id", "").strip()
            if not txn_id:
                continue  # skip blank rows

            # --- Quantity ---
            try:
                quantity = int(row["Quantity"].strip())
            except (ValueError, KeyError):
                logger.warning("Skipping %s: invalid quantity '%s'", txn_id, row.get("Quantity"))
                continue

            # Exclude zero-quantity transactions (e.g., TXN0034)
            if quantity == 0:
                logger.info("Excluding %s: quantity is 0.", txn_id)
                continue

            # --- Unit price (impute if missing) ---
            raw_price = row.get("Unit_price", "").strip()
            if raw_price == "" or raw_price is None:
                if row.get("Product", "").strip() == "Laptop Stand":
                    unit_price = LAPTOP_STAND_IMPUTED_PRICE
                    logger.info("Imputing unit_price=1200 for %s (Laptop Stand).", txn_id)
                else:
                    logger.warning("Skipping %s: missing unit_price for non-Laptop-Stand product.", txn_id)
                    continue
            else:
                try:
                    unit_price = float(raw_price)
                except ValueError:
                    logger.warning("Skipping %s: invalid unit_price '%s'", txn_id, raw_price)
                    continue

            # --- Discount amount ---
            try:
                discount_amount = float(row.get("Discount_amount", "0").strip() or "0")
            except ValueError:
                discount_amount = 0.0

            # --- Date (DD-MM-YYYY → YYYY-MM-DD) ---
            raw_date = row.get("Order_date", "").strip()
            try:
                order_date = datetime.strptime(raw_date, "%d-%m-%Y").strftime("%Y-%m-%d")
            except ValueError:
                logger.warning("Skipping %s: invalid date '%s'", txn_id, raw_date)
                continue

            # --- Revenue (Returned txns get revenue = 0 in aggregations,
            #     but we still store the gross value so it can be reported) ---
            status = row.get("Status", "Completed").strip()
            revenue = (quantity * unit_price) - discount_amount

            records.append(
                {
                    "transaction_id": txn_id,
                    "order_date": order_date,
                    "product": row.get("Product", "").strip(),
                    "category": row.get("Category", "").strip(),
                    "region": row.get("Region", "").strip(),
                    "sales_channel": row.get("Sales_channel", "").strip(),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "discount_amount": discount_amount,
                    "status": status,
                    "revenue": revenue,  # stored for all, filtered in analytics
                }
            )

    return records
