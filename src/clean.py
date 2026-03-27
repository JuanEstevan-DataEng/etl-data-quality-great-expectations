"""
clean.py - Task d: Cleaning pipeline.

Definition: Cleaning corrects or removes records that are broken or invalid.
A record that fails cleaning cannot safely enter the pipeline.
Unlike transformation, cleaning can DROP rows.

Cleaning steps applied:
  1. Remove duplicate invoice_id          (keep first occurrence)
  2. Drop rows with quantity < 1          (negative or zero units)
  3. Drop rows with price <= 0            (negative or zero price)
  4. Drop rows with NULL customer_id      (untraceable sales)
  5. Drop rows with invalid invoice_date  (null-like strings or unparseable)
  6. Drop rows with future invoice_date   (> 2023-12-31)
  7. Correct total_revenue               (recalculate qty x price where mismatched)

Deliverable: data/processed/retail_clean.csv
"""

import re
import re as _re
import pandas as pd
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).parent.parent
RAW        = ROOT / "data" / "raw" / "retail_etl_dataset.csv"
CLEAN_PATH = ROOT / "data" / "processed" / "retail_clean.csv"
(ROOT / "data" / "processed").mkdir(exist_ok=True)

# Pattern to detect null-like strings that are not real NaN
NULL_LIKE = re.compile(r"^(N/A|NULL|nan|NaN|)$")


def parse_date(val):
    """
    Try to parse a date string into a datetime object.
    Handles three known formats: YYYY-MM-DD, YYYY/MM/DD, DD-MM-YYYY.
    Returns NaT if the value is null-like or unparseable.
    """
    if pd.isna(val):
        return pd.NaT
    s = str(val).strip()
    if NULL_LIKE.match(s):
        return pd.NaT
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"]:
        try:
            return pd.to_datetime(s, format=fmt)
        except Exception:
            pass
    return pd.NaT


def run(df=None, raw_path=None, clean_path=None):
    # ── Load raw data (only if df was not provided by extract.py) ─────────────
    if df is None:
        df = pd.read_csv(raw_path or RAW, dtype=str)
        for col in ["invoice_id", "quantity"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        for col in ["customer_id", "price", "total_revenue"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Ensure integer types are correct whether df came from extract or from file
    for col in ["invoice_id", "quantity"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    print("\n" + "=" * 70)
    print("TASK d — CLEANING")
    print("=" * 70)

    # Snapshot before cleaning (for the before/after summary)
    rows_before   = len(df)
    nulls_before  = df.isnull().sum()
    print(f"\nRows before cleaning : {rows_before:,}")

    log = []  # track how many rows were removed at each step

    # ── Step 1: Remove duplicate invoice_id ───────────────────────────────────
    # Justification: duplicate rows inflate revenue in BO-1 KPIs.
    # Strategy: keep the first occurrence of each invoice_id.
    n_before = len(df)
    df = df.drop_duplicates(subset=["invoice_id"], keep="first")
    removed = n_before - len(df)
    log.append({"Step": 1, "Reason": "Duplicate invoice_id (keep first)", "Rows removed": removed})
    print(f"  [1] Duplicate invoice_id removed : {removed:,}")

    # ── Step 2: Drop rows with quantity < 1 ───────────────────────────────────
    # Justification: negative or zero units sold are physically impossible.
    n_before = len(df)
    df = df[~(df["quantity"].isna() | (df["quantity"] < 1))].copy()
    removed = n_before - len(df)
    log.append({"Step": 2, "Reason": "quantity < 1 or null", "Rows removed": removed})
    print(f"  [2] Negative/null quantity       : {removed:,}")

    # ── Step 3: Drop rows with price <= 0 ─────────────────────────────────────
    # Justification: negative or zero prices are impossible in a real sales system.
    n_before = len(df)
    df = df[~(df["price"].isna() | (df["price"] <= 0))].copy()
    removed = n_before - len(df)
    log.append({"Step": 3, "Reason": "price <= 0 or null", "Rows removed": removed})
    print(f"  [3] Negative/zero price          : {removed:,}")

    # ── Step 4: Drop rows with NULL customer_id ───────────────────────────────
    # Justification: sales without a customer ID cannot be attributed
    # to any customer, making BO-3 regional/product analysis impossible.
    n_before = len(df)
    df = df[df["customer_id"].notna()].copy()
    removed = n_before - len(df)
    log.append({"Step": 4, "Reason": "NULL customer_id", "Rows removed": removed})
    print(f"  [4] NULL customer_id             : {removed:,}")

    # ── Step 5: Parse and normalize invoice_date ─────────────────────────────
    # parse_date() handles all three known formats: YYYY-MM-DD, YYYY/MM/DD, DD-MM-YYYY.
    # Rows with those formats are CONVERTED (not dropped) — only truly unreadable
    # values (N/A, NULL, empty string, real NaN) become NaT and are removed.
    def _classify(val):
        if pd.isna(val): return "null_like"
        s = str(val).strip()
        if NULL_LIKE.match(s):           return "null_like"
        if _re.match(r"^\d{4}-\d{2}-\d{2}$", s): return "YYYY-MM-DD"
        if _re.match(r"^\d{4}/\d{2}/\d{2}$", s): return "YYYY/MM/DD"
        if _re.match(r"^\d{2}-\d{2}-\d{4}$", s): return "DD-MM-YYYY"
        return "other"

    fmt_counts = df["invoice_date"].apply(_classify).value_counts()
    print(f"\n  Date formats found before step 5:")
    for fmt, count in fmt_counts.items():
        action = "dropped" if fmt in ("null_like", "other") else "converted to YYYY-MM-DD"
        print(f"    {fmt:<15} : {count:>5} rows  → {action}")

    n_before = len(df)
    df["_parsed_date"] = df["invoice_date"].apply(parse_date) # type:ignore
    df = df[df["_parsed_date"].notna()].copy()
    removed = n_before - len(df)
    log.append({"Step": 5, "Reason": "Null-like invoice_date (N/A, NULL, empty)", "Rows removed": removed})
    print(f"  [5] Null-like invoice_date dropped : {removed:,}")

    # ── Step 6: Drop rows with future invoice_date ────────────────────────────
    # Justification: data is supposed to represent 2023 transactions only.
    # Future dates (2025, 2026, 2027...) are data entry errors.
    n_before = len(df)
    df = df[df["_parsed_date"] <= pd.Timestamp("2023-12-31")].copy()
    removed = n_before - len(df)
    log.append({"Step": 6, "Reason": "Future invoice_date (> 2023-12-31)", "Rows removed": removed})
    print(f"  [6] Future invoice_date          : {removed:,}")

    # Normalize invoice_date to YYYY-MM-DD string (required for CSV and GE)
    df["invoice_date"] = df["_parsed_date"].dt.strftime("%Y-%m-%d")
    df = df.drop(columns=["_parsed_date"])

    # ── Step 7: Correct total_revenue ─────────────────────────────────────────
    # Justification: price and quantity are directly observed values (source of truth).
    # total_revenue is a derived field — when it doesn't match qty x price,
    # we recalculate it rather than dropping the row.
    computed  = df["quantity"].astype(float) * df["price"]
    mismatch  = (df["total_revenue"] - computed).abs() > 0.01
    n_fixed   = int(mismatch.sum())
    df.loc[mismatch, "total_revenue"] = computed[mismatch].round(2)
    log.append({"Step": 7, "Reason": "total_revenue recalculated (qty x price)", "Rows removed": 0})
    print(f"  [7] total_revenue corrected      : {n_fixed:,} rows (not dropped)")

    # ── Before / After summary ────────────────────────────────────────────────
    rows_after  = len(df)
    nulls_after = df.isnull().sum()

    print(f"\nRows after cleaning  : {rows_after:,}")
    print(f"Total rows dropped   : {rows_before - rows_after:,}")

    print("\nNull counts — before vs after:")
    null_comparison = pd.DataFrame({
        "before": nulls_before,
        "after":  nulls_after,
    })
    print(null_comparison.to_string())

    print("\nRows dropped per step:")
    print(pd.DataFrame(log).to_string(index=False))

    # ── Save cleaned dataset ──────────────────────────────────────────────────
    out_path = clean_path or CLEAN_PATH
    df.to_csv(out_path, index=False)
    print(f"\nClean dataset saved → {out_path}")

    return df


if __name__ == "__main__":
    run()
