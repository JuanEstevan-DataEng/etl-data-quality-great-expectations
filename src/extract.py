"""
extract.py - Task a: Data Extraction.

Responsibility: load the raw source file into a DataFrame and apply
the minimum type casts needed so downstream tasks can work with it.

This is the ONLY place in the pipeline that reads the raw CSV.
All other scripts receive the DataFrame as a parameter — they do not
read the file themselves.

Deliverable: a pandas DataFrame returned by run()
"""

import pandas as pd
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).parent.parent
RAW_PATH = ROOT / "data" / "raw" / "retail_etl_dataset.csv"


def run(raw_path=None) -> pd.DataFrame:
    """
    Load the raw retail dataset and apply initial type casts.

    All columns are first read as strings (dtype=str) to avoid pandas
    silently converting or discarding values during load.  Numeric
    columns are then cast explicitly so GE and downstream logic can
    evaluate them correctly.

    Returns the raw DataFrame — no rows are dropped or modified here.
    """
    path = raw_path or RAW_PATH

    print("\n" + "=" * 70)
    print("TASK a — EXTRACTION")
    print("=" * 70)

    # Read everything as string first to preserve the original values
    # (e.g. "N/A" in invoice_date stays as a string, not converted to NaN)
    df = pd.read_csv(path, dtype=str)

    # Cast integer-like columns — errors="coerce" turns unparseable values into NaN
    for col in ["invoice_id", "quantity"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Cast float columns
    for col in ["customer_id", "price", "total_revenue"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    print(f"\nSource file : {path}")
    print(f"Shape       : {df.shape[0]:,} rows × {df.shape[1]} columns")
    print(f"Columns     : {list(df.columns)}")
    print(f"\nSample (first 3 rows):")
    print(df.head(3).to_string(index=False))

    return df


if __name__ == "__main__":
    run()
