from __future__ import annotations

from typing import Any

import pandas as pd


def _safe_float(value: Any) -> float | None:
    """Convert pandas/numpy numeric values to JSON-safe Python floats."""
    if pd.isna(value):
        return None
    return float(value)


def validate_dataframe(df: pd.DataFrame, file_name: str) -> dict[str, Any]:
    """Analyze a DataFrame and return a JSON-serializable data-quality report."""
    total_rows = len(df)
    total_columns = len(df.columns)
    total_cells = total_rows * total_columns

    duplicate_rows = int(df.duplicated().sum())
    missing_values = {col: int(count) for col, count in df.isnull().sum().to_dict().items()}
    total_missing = sum(missing_values.values())

    numeric_columns = df.select_dtypes(include=["number"]).columns.tolist()
    numeric_stats: dict[str, dict[str, float | None]] = {}

    for col in numeric_columns:
        numeric_stats[col] = {
            "min": _safe_float(df[col].min()),
            "max": _safe_float(df[col].max()),
            "mean": _safe_float(df[col].mean()),
        }

    invalid_rules: dict[str, int] = {}
    total_checked_values = 0
    total_invalid_values = 0

    if "age" in df.columns:
        numeric_age = pd.to_numeric(df["age"], errors="coerce")
        invalid_age_count = int((numeric_age < 0).fillna(False).sum())
        checked_age_values = int(numeric_age.notna().sum())
        invalid_rules["age_less_than_zero"] = invalid_age_count
        total_invalid_values += invalid_age_count
        total_checked_values += checked_age_values

    if "salary" in df.columns:
        numeric_salary = pd.to_numeric(df["salary"], errors="coerce")
        invalid_salary_count = int((numeric_salary < 0).fillna(False).sum())
        checked_salary_values = int(numeric_salary.notna().sum())
        invalid_rules["salary_less_than_zero"] = invalid_salary_count
        total_invalid_values += invalid_salary_count
        total_checked_values += checked_salary_values

    completeness_score = 100.0 if total_cells == 0 else ((total_cells - total_missing) / total_cells) * 100
    uniqueness_score = 100.0 if total_rows == 0 else ((total_rows - duplicate_rows) / total_rows) * 100
    validity_score = (
        100.0
        if total_checked_values == 0
        else ((total_checked_values - total_invalid_values) / total_checked_values) * 100
    )

    overall_quality_score = (
        0.40 * completeness_score
        + 0.30 * uniqueness_score
        + 0.30 * validity_score
    )

    columns_with_missing = [col for col, count in missing_values.items() if count > 0]

    return {
        "file_name": file_name,
        "dataset_summary": {
            "total_rows": total_rows,
            "total_columns": total_columns,
            "columns": list(df.columns),
        },
        "quality_metrics": {
            "overall_quality_score": round(overall_quality_score, 2),
            "completeness_score": round(completeness_score, 2),
            "uniqueness_score": round(uniqueness_score, 2),
            "validity_score": round(validity_score, 2),
        },
        "issues": {
            "duplicate_rows": duplicate_rows,
            "total_missing_values": total_missing,
            "missing_values_by_column": missing_values,
            "columns_with_missing_values": columns_with_missing,
            "custom_validation_rules": invalid_rules,
        },
        "numeric_column_stats": numeric_stats,
    }
