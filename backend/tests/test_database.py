"""
Tests for database initialization and CSV import.

Pre-calculated expected values from the CSV
(excluding TXN0034 qty=0 and TXN0051 price imputed to 1200):

  Total rows imported: 51  (52 data rows - 1 qty=0)
  Completed rows:      50
  Returned rows:        1  (TXN0033)

Revenue spot-checks (Completed transactions):
  TXN0001: 10 × 1200 - 0 = 12000
  TXN0004: 6 × 9500 - 500 = 56500
  TXN0022: 4 × 12500 - 2500 = 47500
  TXN0051: 5 × 1200 - 0 = 6000  (imputed price)

TXN0033 (Returned): 2 × 9500 - 0 = 19000 (stored, not in revenue sums)
"""

import os
import sys
import sqlite3
import tempfile
import shutil
# pyrefly: ignore[missing-import]
import pytest

# Ensure backend/ is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture(scope="module")
def tmp_db(tmp_path_factory):
    """Create a fresh temp database for the module."""
    tmp_dir = tmp_path_factory.mktemp("db")
    db_path = str(tmp_dir / "test_sales.db")

    # Patch config to use temp db
    import config
    config.DATABASE_PATH = db_path

    import database
    # Also patch database module
    database.DATABASE_PATH = db_path

    database.init_db()
    yield db_path


def _conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


class TestDatabaseInit:
    def test_tables_created(self, tmp_db):
        conn = _conn(tmp_db)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "sales" in tables
        assert "import_meta" in tables
        conn.close()

    def test_row_count(self, tmp_db):
        """51 rows: 52 data rows minus TXN0034 (qty=0)."""
        conn = _conn(tmp_db)
        count = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        conn.close()
        assert count == 51, f"Expected 51 rows, got {count}"

    def test_completed_count(self, tmp_db):
        conn = _conn(tmp_db)
        count = conn.execute("SELECT COUNT(*) FROM sales WHERE status='Completed'").fetchone()[0]
        conn.close()
        assert count == 50

    def test_returned_count(self, tmp_db):
        conn = _conn(tmp_db)
        count = conn.execute("SELECT COUNT(*) FROM sales WHERE status='Returned'").fetchone()[0]
        conn.close()
        assert count == 1

    def test_txn0034_excluded(self, tmp_db):
        """Zero-quantity transaction must not be imported."""
        conn = _conn(tmp_db)
        row = conn.execute("SELECT * FROM sales WHERE transaction_id='TXN0034'").fetchone()
        conn.close()
        assert row is None, "TXN0034 (qty=0) must be excluded."

    def test_txn0051_imputed_price(self, tmp_db):
        """TXN0051 missing price must be imputed to 1200."""
        conn = _conn(tmp_db)
        row = conn.execute("SELECT unit_price FROM sales WHERE transaction_id='TXN0051'").fetchone()
        conn.close()
        assert row is not None, "TXN0051 must be imported."
        assert row["unit_price"] == pytest.approx(1200.0)

    def test_txn0033_present(self, tmp_db):
        """Returned transaction must be stored (not excluded)."""
        conn = _conn(tmp_db)
        row = conn.execute("SELECT * FROM sales WHERE transaction_id='TXN0033'").fetchone()
        conn.close()
        assert row is not None
        assert row["status"] == "Returned"

    def test_duplicate_import_prevention(self, tmp_db):
        """Running init_db() again must not duplicate rows."""
        import database
        before = sqlite3.connect(tmp_db).execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        database.init_db()
        after = sqlite3.connect(tmp_db).execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        assert before == after, "Duplicate import occurred."

    def test_revenue_calculation_standard(self, tmp_db):
        """TXN0001: 10 × 1200 − 0 = 12000."""
        conn = _conn(tmp_db)
        row = conn.execute("SELECT revenue FROM sales WHERE transaction_id='TXN0001'").fetchone()
        conn.close()
        assert row["revenue"] == pytest.approx(12000.0)

    def test_revenue_calculation_with_discount(self, tmp_db):
        """TXN0004: 6 × 9500 − 500 = 56500."""
        conn = _conn(tmp_db)
        row = conn.execute("SELECT revenue FROM sales WHERE transaction_id='TXN0004'").fetchone()
        conn.close()
        assert row["revenue"] == pytest.approx(56500.0)

    def test_revenue_calculation_desk_discount(self, tmp_db):
        """TXN0022: 4 × 12500 − 2500 = 47500."""
        conn = _conn(tmp_db)
        row = conn.execute("SELECT revenue FROM sales WHERE transaction_id='TXN0022'").fetchone()
        conn.close()
        assert row["revenue"] == pytest.approx(47500.0)

    def test_txn0051_revenue(self, tmp_db):
        """TXN0051: 5 × 1200 − 0 = 6000 (imputed price)."""
        conn = _conn(tmp_db)
        row = conn.execute("SELECT revenue FROM sales WHERE transaction_id='TXN0051'").fetchone()
        conn.close()
        assert row["revenue"] == pytest.approx(6000.0)

    def test_date_format(self, tmp_db):
        """Dates must be stored as YYYY-MM-DD."""
        conn = _conn(tmp_db)
        row = conn.execute("SELECT order_date FROM sales WHERE transaction_id='TXN0001'").fetchone()
        conn.close()
        assert row["order_date"] == "2026-01-03"

    def test_import_meta_recorded(self, tmp_db):
        conn = _conn(tmp_db)
        row = conn.execute("SELECT * FROM import_meta").fetchone()
        conn.close()
        assert row is not None
        assert row["row_count"] == 51
