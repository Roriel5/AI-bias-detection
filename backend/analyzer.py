import pandas as pd
import numpy as np
from itertools import combinations


class AnalysisError(Exception):
    """Raised when input validation fails."""
    pass


def validate_inputs(df: pd.DataFrame, truth_col: str, pred_col: str, sensitive_cols: list):
    """Validate that columns exist, are binary, and make sense."""
    # Check columns exist
    missing = [c for c in [truth_col, pred_col] + sensitive_cols if c not in df.columns]
    if missing:
        raise AnalysisError(f"Columns not found in dataset: {missing}")

    # Check truth ≠ prediction
    if truth_col == pred_col:
        raise AnalysisError("Ground truth and prediction columns must be different.")

    # Check sensitive cols aren't truth/pred
    overlap = [c for c in sensitive_cols if c in (truth_col, pred_col)]
    if overlap:
        raise AnalysisError(f"Sensitive columns cannot be the same as truth/prediction columns: {overlap}")

    # Check binary values
    for col_name, col in [(truth_col, "Ground truth"), (pred_col, "Prediction")]:
        unique_vals = set(df[col_name].dropna().unique())
        if not unique_vals.issubset({0, 1, 0.0, 1.0, True, False}):
            raise AnalysisError(
                f"{col} column '{col_name}' must contain only 0/1 values. "
                f"Found: {sorted(str(v) for v in unique_vals)[:10]}"
            )

    # Check for empty sensitive groups
    for attr in sensitive_cols:
        if df[attr].nunique() < 2:
            raise AnalysisError(f"Sensitive attribute '{attr}' has fewer than 2 groups — nothing to compare.")


def _compute_group_metrics(df: pd.DataFrame, y_true: pd.Series, y_pred: pd.Series, group_col: pd.Series) -> dict:
    """
    Core metric computation for a given grouping column.
    Returns metrics dict with group breakdown.
    """
    groups = group_col.unique()
    group_stats = []
    positive_rates = {}
    tpr_by_group = {}
    fpr_by_group = {}

    for group in sorted(groups, key=str):
        mask = group_col == group
        n = mask.sum()
        if n == 0:
            continue

        gt = y_true[mask]
        pr = y_pred[mask]

        # Positive rate (selection rate)
        positive_rate = float(pr.mean())
        positive_rates[str(group)] = positive_rate

        # True positive rate (sensitivity / recall)
        actual_positives = gt == 1
        tpr = float(pr[actual_positives].mean()) if actual_positives.sum() > 0 else 0.0
        tpr_by_group[str(group)] = tpr

        # False positive rate
        actual_negatives = gt == 0
        fpr = float(pr[actual_negatives].mean()) if actual_negatives.sum() > 0 else 0.0
        fpr_by_group[str(group)] = fpr

        # Accuracy
        accuracy = float((gt == pr).mean())

        # Precision
        predicted_positives = pr == 1
        precision = float(gt[predicted_positives].mean()) if predicted_positives.sum() > 0 else 0.0

        group_stats.append({
            "group": str(group),
            "n": int(n),
            "positive_rate": round(positive_rate, 4),
            "true_positive_rate": round(tpr, 4),
            "false_positive_rate": round(fpr, 4),
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
        })

    group_df = pd.DataFrame(group_stats)

    # -- Demographic Parity Difference --
    rates = list(positive_rates.values())
    dp_diff = float(max(rates) - min(rates)) if rates else 0.0

    # -- Equalized Odds Difference (max of TPR diff and FPR diff) --
    tprs = list(tpr_by_group.values())
    fprs = list(fpr_by_group.values())
    tpr_diff = float(max(tprs) - min(tprs)) if tprs else 0.0
    fpr_diff = float(max(fprs) - min(fprs)) if fprs else 0.0
    eo_diff = max(tpr_diff, fpr_diff)

    # -- Disparate Impact Ratio --
    di_ratio = float(min(rates) / max(rates)) if rates and max(rates) > 0 else 1.0

    # -- Most / least favoured --
    max_group = max(positive_rates, key=positive_rates.get) if positive_rates else "N/A"
    min_group = min(positive_rates, key=positive_rates.get) if positive_rates else "N/A"

    return {
        "demographic_parity_difference": round(dp_diff, 4),
        "equalized_odds_difference": round(eo_diff, 4),
        "disparate_impact_ratio": round(di_ratio, 4),
        "group_breakdown": group_df.to_dict(orient="records"),
        "most_favoured_group": str(max_group),
        "least_favoured_group": str(min_group),
        "positive_rates": {str(k): round(float(v), 4) for k, v in positive_rates.items()},
        "tpr_by_group": {str(k): round(float(v), 4) for k, v in tpr_by_group.items()},
        "fpr_by_group": {str(k): round(float(v), 4) for k, v in fpr_by_group.items()},
    }


def compute_fairness_metrics(df: pd.DataFrame, truth_col: str, pred_col: str, sensitive_cols: list) -> dict:
    """
    Compute fairness metrics for each sensitive attribute.
    Returns a dict keyed by attribute name.
    """
    validate_inputs(df, truth_col, pred_col, sensitive_cols)

    y_true = df[truth_col].astype(int)
    y_pred = df[pred_col].astype(int)
    results = {}

    for attr in sensitive_cols:
        results[attr] = _compute_group_metrics(df, y_true, y_pred, df[attr])

    return results


def compute_intersectional_metrics(df: pd.DataFrame, truth_col: str, pred_col: str, sensitive_cols: list) -> dict:
    """
    Compute intersectional fairness metrics by combining sensitive attributes.
    E.g., for ['sex', 'race'], creates cross-groups like 'Male_White', 'Female_Black', etc.
    """
    if len(sensitive_cols) < 2:
        return {}

    validate_inputs(df, truth_col, pred_col, sensitive_cols)

    y_true = df[truth_col].astype(int)
    y_pred = df[pred_col].astype(int)
    results = {}

    # Generate all pairs and the full combination
    combos = []
    for r in range(2, len(sensitive_cols) + 1):
        combos.extend(combinations(sensitive_cols, r))

    for combo in combos:
        label = " × ".join(combo)
        # Create combined group column
        combined = df[list(combo)].astype(str).agg("_".join, axis=1)

        # Skip if too many groups (would be meaningless)
        if combined.nunique() > 50:
            results[label] = {"error": f"Too many cross-groups ({combined.nunique()}). Skipped."}
            continue

        # Skip groups with very few members
        min_group_size = combined.value_counts().min()
        if min_group_size < 10:
            # Still compute but add a warning
            metrics = _compute_group_metrics(df, y_true, y_pred, combined)
            metrics["warning"] = f"Some cross-groups have very few members (min: {min_group_size}). Results may be unreliable."
            results[label] = metrics
        else:
            results[label] = _compute_group_metrics(df, y_true, y_pred, combined)

    return results
