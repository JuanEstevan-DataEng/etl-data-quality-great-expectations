"""
transform.py - Task e: Transformation pipeline.

Definition: Transformation restructures valid data to prepare it for the
analytical model. Unlike cleaning, this step NEVER drops rows — it only
adds, converts, or standardizes values.

Transformations applied:
  1. Standardize country names  (map all variants to canonical title case)
  2. Parse invoice_date         (convert string to datetime)
  3. Extract temporal features  (year, month, day_of_week, day_name)
  4. Cast customer_id           (float64 -> Int64 nullable integer)
  5. Normalize product names    (strip whitespace + title case)
  6. Feature engineering        (revenue_bin: Low / Medium / High)

Deliverable: data/processed/retail_transformed.csv
"""

import pandas as pd
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT           = Path(__file__).parent.parent
CLEAN_PATH     = ROOT / "data" / "processed" / "retail_clean.csv"
TRANSFORM_PATH = ROOT / "data" / "processed" / "retail_transformed.csv"

# Lookup map: all known raw country variants → canonical title-case name
COUNTRY_MAP = {
    "colombia": "Colombia", "CO": "Colombia", "co": "Colombia", "Colombia": "Colombia",
    "ecuador":  "Ecuador",  "EC": "Ecuador",  "Ecuador":  "Ecuador",
    "peru":     "Peru",     "PE": "Peru",     "Peru":     "Peru",
    "chile":    "Chile",    "CL": "Chile",    "Chile":    "Chile",
}


def run(clean_path=None, transform_path=None):
    df = pd.read_csv(clean_path or CLEAN_PATH)

    print("\n" + "=" * 70)
    print("TASK e — TRANSFORMATION")
    print("=" * 70)
    print(f"Rows entering transformation: {len(df):,}")

    df = df.copy()

    # ── Step 1: Standardize country names ────────────────────────────────────
    # Map every variant (lowercase, abbreviation) to its canonical form.
    # .fillna keeps any value not in the map unchanged (safety net).
    df["country"] = df["country"].map(COUNTRY_MAP).fillna(df["country"])
    print(f"\n  [1] country — unique values after standardization:")
    print(f"      {sorted(df['country'].unique())}")

    # ── Step 2: Parse invoice_date to datetime ────────────────────────────────
    # After cleaning, all dates are already in YYYY-MM-DD format.
    df["invoice_date"] = pd.to_datetime(df["invoice_date"], format="%Y-%m-%d")

    # ── Step 3: Extract temporal features ────────────────────────────────────
    # These columns are needed by dim_date and by BO-2 time-series charts.
    df["year"]        = df["invoice_date"].dt.year.astype("Int64")
    df["month"]       = df["invoice_date"].dt.month.astype("Int64")   # 1 = January, 12 = December
    df["day_of_week"] = df["invoice_date"].dt.dayofweek.astype("Int64")  # 0 = Monday, 6 = Sunday
    df["day_name"]    = df["invoice_date"].dt.day_name()
    print(f"\n  [2] Temporal columns added: year, month, day_of_week, day_name")

    # ── Step 4: Cast customer_id to nullable integer ──────────────────────────
    # After cleaning, customer_id has no nulls, but it is stored as float64
    # (e.g. 1102.0). Casting to Int64 removes the decimal and keeps it clean.
    df["customer_id"] = pd.to_numeric(df["customer_id"], errors="coerce").astype("Int64")
    print(f"  [3] customer_id cast from float64 to Int64")

    # ── Step 5: Normalize product names ──────────────────────────────────────
    # Strip leading/trailing whitespace and apply title case to ensure
    # uniform casing across all records (e.g. "laptop" → "Laptop").
    df["product"] = df["product"].str.strip().str.title()
    print(f"  [4] product values after normalization:")
    print(f"      {sorted(df['product'].unique())}")

    # ── Step 6: Fix numeric types ─────────────────────────────────────────────
    df["invoice_id"]    = pd.to_numeric(df["invoice_id"],    errors="coerce").astype("Int64")
    df["quantity"]      = pd.to_numeric(df["quantity"],      errors="coerce").astype("Int64")
    df["price"]         = pd.to_numeric(df["price"],         errors="coerce").astype(float)
    df["total_revenue"] = pd.to_numeric(df["total_revenue"], errors="coerce").astype(float)

    # ── Step 7: Feature engineering — revenue_bin ────────────────────────────
    # Divide total_revenue into three equal groups (tertiles) based on the
    # 33rd and 67th percentiles of the cleaned data.
    # Low: bottom third | Medium: middle third | High: top third
    q33 = df["total_revenue"].quantile(0.333)
    q67 = df["total_revenue"].quantile(0.667)

    df["revenue_bin"] = df["total_revenue"].apply(
        lambda v: "Low" if v <= q33 else ("Medium" if v <= q67 else "High")
    )

    print(f"\n  [5] revenue_bin thresholds:")
    print(f"      Low  : total_revenue <= {q33:.2f}")
    print(f"      Medium: total_revenue <= {q67:.2f}")
    print(f"      High : total_revenue >  {q67:.2f}")
    print(f"      Distribution: {df['revenue_bin'].value_counts().to_dict()}")

    print(f"\nRows after transformation: {len(df):,}  (no rows dropped)")
    print(f"Columns: {list(df.columns)}")

    # Save — write invoice_date back as YYYY-MM-DD string for CSV compatibility
    out = df.copy()
    out["invoice_date"] = out["invoice_date"].dt.strftime("%Y-%m-%d")
    out_path = transform_path or TRANSFORM_PATH
    out.to_csv(out_path, index=False)
    print(f"\nTransformed dataset saved → {out_path}")

    return df   # return with datetime invoice_date for downstream use


if __name__ == "__main__":
    run()
