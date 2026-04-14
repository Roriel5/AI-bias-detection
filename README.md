# Bias Autopsy 🔬

> Detect, explain, and fix hidden bias in AI models — with plain-language reports for non-technical stakeholders.

Built for **Google Solution Challenge 2026**.

---

## Quick Start

```bash
# 1. Clone / download this folder
cd bias_autopsy

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
uvicorn backend.main:app --reload --port 8000
```

Then open **http://localhost:8000** in your browser.

---

## Architecture

```
bias_autopsy/
├── backend/
│   ├── main.py          # FastAPI app — API endpoints + static file serving
│   ├── analyzer.py      # Fairness metrics (demographic parity, equalized odds, disparate impact)
│   ├── explainer.py     # Gemini API — plain-language explanation + fix suggestions
│   ├── report.py        # PDF report card generator
│   └── create_demo.py   # Script to generate demo CSV from UCI Adult dataset
├── frontend/
│   ├── index.html       # Single-page app
│   ├── style.css        # Premium dark theme with glassmorphism
│   └── app.js           # Client-side logic, Chart.js visualizations
├── tests/
│   ├── test_analyzer.py # Unit tests for fairness metrics
│   └── test_explainer.py# Unit tests for LLM explanation
├── requirements.txt
└── README.md
```

---

## Generate a Demo Dataset

```bash
python -m backend.create_demo
```

This downloads the UCI Adult Income dataset, trains an intentionally biased model, and saves `demo_adult.csv`.

Then in the app:
- Ground truth column → `income_label`
- Predictions column → `prediction`
- Sensitive attributes → `sex`, `race`

---

## Get a Gemini API Key

1. Go to [ai.google.dev](https://ai.google.dev)
2. Click "Get API key" (free tier available)
3. Click the 🔑 button in the app navbar and paste your key

Your key is stored in your browser's localStorage only — it's never sent to our server.

---

## Features

| Feature | Description |
|---------|-------------|
| **Fairness Metrics** | Demographic Parity, Equalized Odds, Disparate Impact per sensitive attribute |
| **Intersectional Analysis** | Cross-group analysis (e.g., Female × Black) when 2+ attributes selected |
| **AI Explanations** | Gemini-powered plain-language impact, root cause, and fix recommendations |
| **Visualizations** | Bar charts, radar charts with Chart.js |
| **PDF Report** | Downloadable bias report card for stakeholders |
| **Input Validation** | Column checks, binary value enforcement, duplicate detection |

---

## What the Metrics Mean

| Metric | Formula | Fair Range |
|--------|---------|------------|
| Demographic Parity Difference | max(positive rate) − min(positive rate) across groups | < 0.05 |
| Equalized Odds Difference | max(TPR diff, FPR diff) across groups | < 0.05 |
| Disparate Impact Ratio | min(positive rate) / max(positive rate) | > 0.8 |

---

## Running Tests

```bash
pytest tests/ -v
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/columns` | POST | Read CSV headers + preview |
| `/api/analyze` | POST | Run fairness analysis |
| `/api/analyze-intersectional` | POST | Intersectional cross-group analysis |
| `/api/explain` | POST | Get Gemini AI explanation |
| `/api/report` | POST | Generate PDF report |
