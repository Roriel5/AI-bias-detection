import os
import io
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.analyzer import compute_fairness_metrics, compute_intersectional_metrics, AnalysisError
from backend.explainer import get_llm_explanation
from backend.report import generate_report

app = FastAPI(title="Bias Autopsy", version="2.0.0")

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    truth_col: str = Form(...),
    pred_col: str = Form(...),
    sensitive_cols: str = Form(...)  # comma-separated
):
    """Run fairness analysis on uploaded CSV."""
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {str(e)}")

    cols = [c.strip() for c in sensitive_cols.split(",") if c.strip()]
    if not cols:
        raise HTTPException(status_code=400, detail="At least one sensitive attribute is required.")

    try:
        metrics = compute_fairness_metrics(df, truth_col, pred_col, cols)
    except AnalysisError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    return {
        "status": "ok",
        "rows": len(df),
        "columns": list(df.columns),
        "metrics": metrics,
    }


@app.post("/api/analyze-intersectional")
async def analyze_intersectional(
    file: UploadFile = File(...),
    truth_col: str = Form(...),
    pred_col: str = Form(...),
    sensitive_cols: str = Form(...)
):
    """Run intersectional fairness analysis."""
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {str(e)}")

    cols = [c.strip() for c in sensitive_cols.split(",") if c.strip()]
    if len(cols) < 2:
        raise HTTPException(status_code=400, detail="Intersectional analysis requires at least 2 sensitive attributes.")

    try:
        metrics = compute_intersectional_metrics(df, truth_col, pred_col, cols)
    except AnalysisError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    return {
        "status": "ok",
        "metrics": metrics,
    }


@app.post("/api/explain")
async def explain(
    metrics: dict = None,
    sensitive_cols: list = None,
    api_key: str = None
):
    """Get LLM explanation for the provided metrics."""
    if not api_key:
        raise HTTPException(status_code=400, detail="Gemini API key is required.")
    if not metrics:
        raise HTTPException(status_code=400, detail="Metrics data is required.")
    if not sensitive_cols:
        raise HTTPException(status_code=400, detail="Sensitive columns are required.")

    explanation = get_llm_explanation(metrics, sensitive_cols, api_key)
    return {"status": "ok", "explanation": explanation}


@app.post("/api/report")
async def report(
    metrics: dict = None,
    explanation: dict = None,
    sensitive_cols: list = None
):
    """Generate and return a PDF bias report."""
    if not metrics or not explanation or not sensitive_cols:
        raise HTTPException(status_code=400, detail="metrics, explanation, and sensitive_cols are all required.")

    pdf_bytes = generate_report(metrics, explanation, sensitive_cols)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=bias_report_card.pdf"}
    )


@app.post("/api/columns")
async def get_columns(file: UploadFile = File(...)):
    """Read CSV headers and return column names + preview."""
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {str(e)}")

    return {
        "status": "ok",
        "columns": list(df.columns),
        "rows": len(df),
        "preview": df.head(5).to_dict(orient="records"),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
    }


# Serve frontend static files — must be LAST so it doesn't override API routes
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(FRONTEND_DIR):
    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
