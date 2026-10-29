"""
Tests for the AI assistant and chat API endpoint.
Groq API is fully mocked — no real API key required, no API charges.
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ---------------------------------------------------------------------------
# Helpers to build a mock Groq response
# ---------------------------------------------------------------------------
def _mock_groq_response(content: str):
    """Build a mock object matching Groq SDK response shape."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _intent_json(intent: str, month1=None, month2=None) -> str:
    return json.dumps({
        "intent": intent,
        "params": {"month1": month1, "month2": month2},
    })


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module", autouse=True)
def setup_db(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("chat_db")
    db_path = str(tmp_dir / "chat_test.db")
    import config
    config.DATABASE_PATH = db_path
    import database
    database.DATABASE_PATH = db_path
    database.init_db()
    yield db_path


@pytest.fixture
def mock_groq_client():
    """Return a mock Groq client with a patchable completions.create."""
    client = MagicMock()
    return client


# ---------------------------------------------------------------------------
# Tests for ai_assistant.answer_question
# ---------------------------------------------------------------------------
class TestAIAssistantAnswerQuestion:

    @patch("ai_assistant.GROQ_API_KEY", "fake-key-for-testing")
    @patch("ai_assistant._get_groq_client")
    def test_total_revenue_intent(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        # First call: intent classification
        # Second call: answer generation
        client.chat.completions.create.side_effect = [
            _mock_groq_response(_intent_json("total_revenue")),
            _mock_groq_response("Total net revenue is ₹10,00,000."),
        ]
        from ai_assistant import answer_question
        result = answer_question("What is the total revenue?")
        assert result["intent"] == "total_revenue"
        assert result["data"] is not None
        assert "total_revenue" in result["data"]
        assert result["error"] is None

    @patch("ai_assistant.GROQ_API_KEY", "fake-key-for-testing")
    @patch("ai_assistant._get_groq_client")
    def test_top_product_intent(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        client.chat.completions.create.side_effect = [
            _mock_groq_response(_intent_json("top_product")),
            _mock_groq_response("Monitor is the top product."),
        ]
        from ai_assistant import answer_question
        result = answer_question("Which product generated the highest revenue?")
        assert result["intent"] == "top_product"
        assert isinstance(result["data"], list)
        assert result["data"][0]["product"] == "Monitor"

    @patch("ai_assistant.GROQ_API_KEY", "fake-key-for-testing")
    @patch("ai_assistant._get_groq_client")
    def test_monthly_trend_intent(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        client.chat.completions.create.side_effect = [
            _mock_groq_response(_intent_json("monthly_trend")),
            _mock_groq_response("Monthly revenue trend is as follows…"),
        ]
        from ai_assistant import answer_question
        result = answer_question("What is the monthly revenue trend?")
        assert result["intent"] == "monthly_trend"
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 6

    @patch("ai_assistant.GROQ_API_KEY", "fake-key-for-testing")
    @patch("ai_assistant._get_groq_client")
    def test_region_revenue_intent(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        client.chat.completions.create.side_effect = [
            _mock_groq_response(_intent_json("region_revenue")),
            _mock_groq_response("The North region leads."),
        ]
        from ai_assistant import answer_question
        result = answer_question("Which region generated the highest revenue?")
        assert result["intent"] == "region_revenue"
        assert len(result["data"]) == 4

    @patch("ai_assistant.GROQ_API_KEY", "fake-key-for-testing")
    @patch("ai_assistant._get_groq_client")
    def test_month_comparison_intent(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        client.chat.completions.create.side_effect = [
            _mock_groq_response(_intent_json("month_comparison", "2026-01", "2026-02")),
            _mock_groq_response("Revenue increased from Jan to Feb."),
        ]
        from ai_assistant import answer_question
        result = answer_question("How did revenue change between January and February 2026?")
        assert result["intent"] == "month_comparison"
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 2

    @patch("ai_assistant.GROQ_API_KEY", "fake-key-for-testing")
    @patch("ai_assistant._get_groq_client")
    def test_unsupported_question(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        client.chat.completions.create.side_effect = [
            _mock_groq_response(_intent_json("unsupported")),
        ]
        from ai_assistant import answer_question
        result = answer_question("What is the weather today?")
        assert result["intent"] == "unsupported"
        assert "can't answer" in result["answer"].lower() or "sorry" in result["answer"].lower()

    def test_missing_api_key(self):
        """Should return graceful error when API key not set."""
        import config
        original = config.GROQ_API_KEY
        config.GROQ_API_KEY = ""
        try:
            import ai_assistant
            ai_assistant.GROQ_API_KEY = ""
            with patch("ai_assistant.GROQ_API_KEY", ""):
                from ai_assistant import answer_question
                result = answer_question("What is the total revenue?")
            assert result["error"] is not None
            assert "GROQ_API_KEY" in result["answer"] or "not configured" in result["answer"]
        finally:
            config.GROQ_API_KEY = original

    @patch("ai_assistant.GROQ_API_KEY", "fake-key-for-testing")
    @patch("ai_assistant._get_groq_client")
    def test_groq_api_error_during_classification(self, mock_get_client):
        """Groq API error should result in a graceful error response."""
        client = MagicMock()
        mock_get_client.return_value = client
        client.chat.completions.create.side_effect = Exception("API rate limit exceeded")
        from ai_assistant import answer_question
        result = answer_question("What is the total revenue?")
        assert result["error"] is not None
        assert "unavailable" in result["answer"].lower() or "error" in result["answer"].lower()

    @patch("ai_assistant.GROQ_API_KEY", "fake-key-for-testing")
    @patch("ai_assistant._get_groq_client")
    def test_malformed_json_from_model(self, mock_get_client):
        """Malformed LLM JSON should default to unsupported intent gracefully."""
        client = MagicMock()
        mock_get_client.return_value = client
        client.chat.completions.create.side_effect = [
            _mock_groq_response("This is not JSON at all!!!"),
        ]
        from ai_assistant import answer_question
        result = answer_question("What is the total revenue?")
        # Should gracefully handle and return unsupported
        assert result["intent"] in (None, "unsupported")
        assert result["answer"] != ""

    @patch("ai_assistant.GROQ_API_KEY", "fake-key-for-testing")
    @patch("ai_assistant._get_groq_client")
    def test_unknown_intent_from_model(self, mock_get_client):
        """Unknown intent from LLM must default to 'unsupported'."""
        client = MagicMock()
        mock_get_client.return_value = client
        client.chat.completions.create.side_effect = [
            _mock_groq_response(json.dumps({"intent": "delete_database", "params": {}})),
        ]
        from ai_assistant import answer_question
        result = answer_question("Delete everything!")
        assert result["intent"] == "unsupported"

    @patch("ai_assistant.GROQ_API_KEY", "fake-key-for-testing")
    @patch("ai_assistant._get_groq_client")
    def test_month_comparison_invalid_months(self, mock_get_client):
        """Invalid month format in params should be handled gracefully."""
        client = MagicMock()
        mock_get_client.return_value = client
        client.chat.completions.create.side_effect = [
            _mock_groq_response(_intent_json("month_comparison", "bad", "dates")),
            _mock_groq_response("Cannot compare."),
        ]
        from ai_assistant import answer_question
        result = answer_question("Compare January vs February")
        # Should not crash; data may be None or empty
        assert result["answer"] is not None


# ---------------------------------------------------------------------------
# Tests for the FastAPI /api/chat endpoint
# ---------------------------------------------------------------------------
class TestChatEndpoint:

    @pytest.fixture(scope="class")
    def client(self):
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)

    def test_health_endpoint(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"

    def test_analytics_overview_endpoint(self, client):
        r = client.get("/api/analytics/overview")
        assert r.status_code == 200
        data = r.json()
        assert "total_revenue" in data
        assert data["transaction_count"] == 50

    def test_monthly_revenue_endpoint(self, client):
        r = client.get("/api/analytics/monthly-revenue")
        assert r.status_code == 200
        data = r.json()
        assert len(data["data"]) == 6

    def test_region_revenue_endpoint(self, client):
        r = client.get("/api/analytics/region-revenue")
        assert r.status_code == 200
        data = r.json()
        assert len(data["data"]) == 4

    def test_top_products_endpoint(self, client):
        r = client.get("/api/analytics/top-products")
        assert r.status_code == 200
        data = r.json()
        assert len(data["data"]) == 7

    def test_suggestions_endpoint(self, client):
        r = client.get("/api/suggestions")
        assert r.status_code == 200
        data = r.json()
        assert len(data["suggestions"]) >= 4

    def test_chat_empty_question(self, client):
        r = client.post("/api/chat", json={"question": "   "})
        assert r.status_code in (422, 400)

    def test_chat_no_body(self, client):
        r = client.post("/api/chat")
        assert r.status_code == 422

    @patch("ai_assistant.GROQ_API_KEY", "fake-key-for-testing")
    @patch("ai_assistant._get_groq_client")
    def test_chat_valid_question(self, mock_get_client, client):
        c = MagicMock()
        mock_get_client.return_value = c
        c.chat.completions.create.side_effect = [
            _mock_groq_response(_intent_json("total_revenue")),
            _mock_groq_response("Total revenue is ₹X."),
        ]
        r = client.post("/api/chat", json={"question": "What is the total revenue?"})
        assert r.status_code == 200
        data = r.json()
        assert "answer" in data
        assert "intent" in data

    def test_chat_no_api_key_graceful(self, client):
        """Without API key, should return 200 with an error message (not crash)."""
        with patch("ai_assistant.GROQ_API_KEY", ""):
            r = client.post("/api/chat", json={"question": "What is total revenue?"})
        assert r.status_code == 200
        data = r.json()
        assert data["error"] is not None
        assert data["answer"] != ""
