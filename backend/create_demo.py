"""
Generate a demo dataset for Bias Autopsy.
Downloads the UCI Adult Income dataset, trains an intentionally biased model,
and saves the output CSV for upload to the app.

Usage:
    python -m backend.create_demo
"""
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
import os


def create_demo_dataset(output_path: str = "demo_adult.csv") -> str:
    """Download UCI Adult dataset, train biased model, save demo CSV."""
    print("Downloading UCI Adult Income dataset...")
    url = "https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.data"
    cols = [
        "age", "workclass", "fnlwgt", "education", "education_num", "marital_status",
        "occupation", "relationship", "race", "sex", "capital_gain", "capital_loss",
        "hours_per_week", "native_country", "income"
    ]
    df = pd.read_csv(url, names=cols, skipinitialspace=True)
    print(f"  Downloaded {len(df):,} rows")

    # Clean
    df["income_label"] = (df["income"] == ">50K").astype(int)
    df["sex_encoded"] = LabelEncoder().fit_transform(df["sex"])
    df["race_encoded"] = LabelEncoder().fit_transform(df["race"])

    # Train a simple (intentionally biased) model — sex_encoded as a feature introduces bias
    features = ["age", "education_num", "hours_per_week", "capital_gain", "sex_encoded"]
    X = df[features].fillna(0)
    y = df["income_label"]
    model = LogisticRegression(max_iter=500)
    model.fit(X, y)

    # Predictions
    df["prediction"] = model.predict(X)

    # Save output
    output_cols = ["age", "sex", "race", "education_num", "hours_per_week", "income_label", "prediction"]
    df[output_cols].to_csv(output_path, index=False)
    print(f"  Saved to {output_path}")
    print(f"  Rows: {len(df):,}")
    print()
    print("Upload this CSV to Bias Autopsy with:")
    print("  • Ground truth column → income_label")
    print("  • Predictions column  → prediction")
    print("  • Sensitive attributes → sex, race")
    return output_path


if __name__ == "__main__":
    create_demo_dataset()
