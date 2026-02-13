"""Tests for Curator agent tools."""
import pytest
import json
from unittest.mock import patch, MagicMock


class TestFetchEdgarAiMentions:
    """Tests for _fetch_edgar_ai_mentions helper."""

    def test_returns_dict_with_expected_keys(self):
        """Should return dict with count and snippets keys."""
        from app.agents.curator.tools import _fetch_edgar_ai_mentions
        mock_response = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "period_of_report": "2024-12-31",
                            "file_date": "2025-02-01"
                        },
                        "highlight": {
                            "file_contents": [
                                "We develop <em>artificial intelligence</em> chips for data centers."
                            ]
                        }
                    }
                ],
                "total": {"value": 1}
            }
        }
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response
            )
            result = _fetch_edgar_ai_mentions("NVDA", "NVIDIA")

        assert "count" in result
        assert "snippets" in result
        assert isinstance(result["snippets"], list)

    def test_returns_zero_for_no_filings(self):
        """Should return count=0 when no 10-K filings found."""
        from app.agents.curator.tools import _fetch_edgar_ai_mentions
        mock_response = {"hits": {"hits": [], "total": {"value": 0}}}
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response
            )
            result = _fetch_edgar_ai_mentions("MCD", "McDonald's")

        assert result["count"] == 0
        assert result["snippets"] == []

    def test_handles_request_exception_gracefully(self):
        """Should return empty result on network error, not raise."""
        from app.agents.curator.tools import _fetch_edgar_ai_mentions
        import requests
        with patch("requests.get", side_effect=requests.exceptions.Timeout):
            result = _fetch_edgar_ai_mentions("NVDA", "NVIDIA")

        assert result["count"] == 0
        assert "error" in result
