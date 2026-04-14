import pytest
import json
from unittest.mock import patch, MagicMock
from backend.explainer import get_llm_explanation


SAMPLE_METRICS = {
    "sex": {
        "demographic_parity_difference": 0.2,
        "equalized_odds_difference": 0.15,
        "disparate_impact_ratio": 0.6,
        "most_favoured_group": "Male",
        "least_favoured_group": "Female",
        "positive_rates": {"Male": 0.35, "Female": 0.15},
    }
}

VALID_LLM_RESPONSE = {
    "impact": "Female applicants are half as likely to receive favorable predictions.",
    "root_cause": "Training data reflects historical hiring discrimination.",
    "severity_score": 7,
    "fixes": [
        {"description": "Re-sample training data", "effort": "medium", "impact": "Reduce DP diff by 50%"},
        {"description": "Remove sex as feature", "effort": "low", "impact": "Eliminate direct discrimination"},
        {"description": "Use adversarial debiasing", "effort": "high", "impact": "Near-zero bias"}
    ]
}


class TestGetLLMExplanation:
    def test_returns_error_dict_on_empty_metrics(self):
        """Should handle metrics with all errors gracefully."""
        metrics = {"sex": {"error": "Too many groups"}}
        result = get_llm_explanation(metrics, ["sex"], "fake-key", max_retries=1)
        assert "No valid metrics" in result["impact"]

    @patch('backend.explainer.urllib.request.urlopen')
    def test_parses_valid_response(self, mock_urlopen):
        """Should correctly parse a valid Gemini response."""
        response_body = json.dumps({
            "candidates": [{
                "content": {
                    "parts": [{"text": json.dumps(VALID_LLM_RESPONSE)}]
                }
            }]
        }).encode('utf-8')

        mock_response = MagicMock()
        mock_response.read.return_value = response_body
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = get_llm_explanation(SAMPLE_METRICS, ["sex"], "fake-key")

        assert result["severity_score"] == 7
        assert len(result["fixes"]) == 3
        assert "Female" in result["impact"]

    @patch('backend.explainer.urllib.request.urlopen')
    def test_handles_markdown_wrapped_json(self, mock_urlopen):
        """Should strip markdown fences from LLM response."""
        wrapped = "```json\n" + json.dumps(VALID_LLM_RESPONSE) + "\n```"
        response_body = json.dumps({
            "candidates": [{
                "content": {
                    "parts": [{"text": wrapped}]
                }
            }]
        }).encode('utf-8')

        mock_response = MagicMock()
        mock_response.read.return_value = response_body
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = get_llm_explanation(SAMPLE_METRICS, ["sex"], "fake-key")
        assert result["severity_score"] == 7

    @patch('backend.explainer.urllib.request.urlopen')
    def test_handles_auth_error(self, mock_urlopen):
        """Should return auth error message on 401/403."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url='', code=401, msg='Unauthorized', hdrs={}, fp=MagicMock(read=lambda: b'Bad key')
        )

        result = get_llm_explanation(SAMPLE_METRICS, ["sex"], "bad-key", max_retries=1)
        assert "Authentication failed" in result["impact"]
        assert result["severity_score"] == 0

    @patch('backend.explainer.urllib.request.urlopen')
    @patch('backend.explainer.time.sleep')  # Skip actual sleep in tests
    def test_retries_on_server_error(self, mock_sleep, mock_urlopen):
        """Should retry on 500 errors."""
        import urllib.error

        # First call fails with 500, second succeeds
        response_body = json.dumps({
            "candidates": [{
                "content": {
                    "parts": [{"text": json.dumps(VALID_LLM_RESPONSE)}]
                }
            }]
        }).encode('utf-8')

        mock_response = MagicMock()
        mock_response.read.return_value = response_body
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [
            urllib.error.HTTPError(url='', code=500, msg='Server Error', hdrs={}, fp=MagicMock(read=lambda: b'Error')),
            mock_response
        ]

        result = get_llm_explanation(SAMPLE_METRICS, ["sex"], "fake-key", max_retries=3)
        assert result["severity_score"] == 7
        assert mock_urlopen.call_count == 2

    @patch('backend.explainer.urllib.request.urlopen')
    @patch('backend.explainer.time.sleep')
    def test_exhausted_retries(self, mock_sleep, mock_urlopen):
        """Should return error after all retries exhausted."""
        import urllib.error

        mock_urlopen.side_effect = urllib.error.HTTPError(
            url='', code=500, msg='Server Error', hdrs={}, fp=MagicMock(read=lambda: b'Error')
        )

        result = get_llm_explanation(SAMPLE_METRICS, ["sex"], "fake-key", max_retries=2)
        assert "Could not get an explanation" in result["impact"]
        assert mock_urlopen.call_count == 2
