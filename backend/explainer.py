import json
import time
import urllib.request
import urllib.error


def get_llm_explanation(metrics: dict, sensitive_cols: list, api_key: str, max_retries: int = 3) -> dict:
    """
    Send fairness metrics to Gemini and get a plain-language explanation
    with root cause analysis and ranked fix recommendations.
    Includes retry logic with exponential backoff.
    """
    # Build a clean summary of the metrics to send to the LLM
    metrics_summary = []
    for attr, data in metrics.items():
        if "error" in data:
            continue

        dp = data["demographic_parity_difference"]
        eo = data["equalized_odds_difference"]
        di = data["disparate_impact_ratio"]
        favoured = data["most_favoured_group"]
        least = data["least_favoured_group"]
        rates = data["positive_rates"]

        metrics_summary.append(f"""
Attribute: {attr}
- Demographic Parity Difference: {dp} (0 = fair, >0.1 = biased)
- Equalized Odds Difference: {eo}
- Disparate Impact Ratio: {di} (<0.8 fails the 80% rule)
- Most favoured group: {favoured} (positive rate: {rates.get(favoured, '?')})
- Least favoured group: {least} (positive rate: {rates.get(least, '?')})
- All group rates: {json.dumps(rates)}
""")

    if not metrics_summary:
        return {
            "impact": "No valid metrics to explain.",
            "root_cause": "All attribute analyses encountered errors.",
            "severity_score": 0,
            "fixes": []
        }

    prompt = f"""You are an AI fairness auditor. Analyze these fairness metrics from an automated decision-making model and provide a clear, accessible report.

METRICS:
{''.join(metrics_summary)}

Respond ONLY with a valid JSON object (no markdown, no backticks) with exactly these keys:
{{
  "impact": "2-3 sentences explaining what this bias means for real people affected by this model's decisions. Be specific and human.",
  "root_cause": "2-3 sentences on the most likely reason this bias exists — e.g. historical data imbalance, proxy variables, underrepresentation. Be specific.",
  "severity_score": <integer 1-10 where 10 is most severe>,
  "fixes": [
    {{
      "description": "Specific actionable fix",
      "effort": "low|medium|high",
      "impact": "Expected improvement"
    }},
    {{
      "description": "Second fix",
      "effort": "low|medium|high",
      "impact": "Expected improvement"
    }},
    {{
      "description": "Third fix",
      "effort": "low|medium|high",
      "impact": "Expected improvement"
    }}
  ]
}}"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024}
    }).encode("utf-8")

    last_error = None

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=45) as response:
                result = json.loads(response.read().decode("utf-8"))
                text = result["candidates"][0]["content"]["parts"][0]["text"]

                # Strip any accidental markdown fences
                text = text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

                return json.loads(text)

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            last_error = f"HTTP {e.code}: {error_body[:200]}"

            # Don't retry on auth errors
            if e.code in (401, 403):
                return {
                    "impact": "Authentication failed. Please check your Gemini API key.",
                    "root_cause": f"API returned {e.code}. Your key may be invalid or expired.",
                    "severity_score": 0,
                    "fixes": []
                }

            # Retry on 429 (rate limit) and 5xx (server errors)
            if e.code in (429, 500, 502, 503, 504):
                wait_time = (2 ** attempt) + 1
                time.sleep(wait_time)
                continue

            # Other HTTP errors — don't retry
            return {
                "impact": f"API error ({e.code}). Check your API key and try again.",
                "root_cause": error_body[:300],
                "severity_score": 0,
                "fixes": []
            }

        except (json.JSONDecodeError, KeyError) as e:
            last_error = f"Parse error: {str(e)}"
            # Retry parse errors — LLM might give valid JSON next time
            wait_time = (2 ** attempt) + 1
            time.sleep(wait_time)
            continue

        except Exception as e:
            last_error = str(e)
            wait_time = (2 ** attempt) + 1
            time.sleep(wait_time)
            continue

    # All retries exhausted
    return {
        "impact": "Could not get an explanation after multiple attempts. You can try again.",
        "root_cause": f"Last error: {last_error}",
        "severity_score": 0,
        "fixes": []
    }
