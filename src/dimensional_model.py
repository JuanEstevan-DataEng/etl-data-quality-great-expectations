"""
dimensional_model.py - Task g: Dimensional Modeling (Star Schema).

Reads the transformed dataset and produces five DataFrames that form a
star schema ready to be loaded into a data warehouse:

  Dimension tables (the "points" of the star):
    dim_product   — one row per unique product
    dim_customer  — one row per unique customer
    dim_location  — one row per unique country
    dim_date      — one row per calendar day of 2023 (all 365 days)

  Fact table (the "center" of the star):
    fact_sales    — one row per sale; numeric measures + FK references

Each dimension table has a surrogate key (SK) — a simple integer assigned
by us that acts as the primary key inside the warehouse.  The fact table
stores those SKs as foreign keys instead of the original text values.

Deliverable: DataFrames returned by run(); also saved to data/star_schema/
"""

import pandas as pd
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT            = Path(__file__).parent.parent
TRANSFORM_PATH  = ROOT / "data" / "processed" / "retail_transformed.csv"
STAR_DIR        = ROOT / "data" / "star_schema"
STAR_DIR.mkdir(parents=True, exist_ok=True)


# ── dim_product ───────────────────────────────────────────────────────────────
def build_dim_product(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per unique product name.

    Surrogate key: product_sk  (1, 2, 3, ...)
    Natural key:   product_name (e.g. 'Laptop', 'Mouse')
    """
    products = df["product"].drop_duplicates().sort_values().reset_index(drop=True)
    dim = pd.DataFrame({
        "product_sk":   products.index + 1,   # surrogate key starts at 1
        "product_name": products.values,
    })
    return dim


# ── dim_customer ──────────────────────────────────────────────────────────────
def build_dim_customer(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per unique customer.

    Surrogate key: customer_sk  (1, 2, 3, ...)
    Natural key:   customer_id  (the original numeric ID from the source system)
    """
    customers = (
        df["customer_id"]
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )
    dim = pd.DataFrame({
        "customer_sk": customers.index + 1,
        "customer_id": customers.values,
    })
    return dim


# ── dim_location ──────────────────────────────────────────────────────────────
def build_dim_location(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per country (already cleaned to canonical names by transform.py).

    Surrogate key: location_sk
    Natural key:   country
    """
    countries = df["country"].drop_duplicates().sort_values().reset_index(drop=True)
    dim = pd.DataFrame({
        "location_sk": countries.index + 1,
        "country":     countries.values,
    })
    return dim


# ── dim_date ──────────────────────────────────────────────────────────────────
def build_dim_date() -> pd.DataFrame:
    """
    One row per calendar day of 2023 — all 365 days, regardless of whether
    any sale occurred on that day.  This allows analysts to spot gaps (days
    with zero sales) in time-series queries.

    Surrogate key: date_sk  (integer in YYYYMMDD format, e.g. 20230101)
    Natural key:   full_date (datetime)
    """
    all_days = pd.date_range(start="2023-01-01", end="2023-12-31", freq="D")

    dim = pd.DataFrame({
        # YYYYMMDD integer is a common date SK format — easy to read and sort
        "date_sk":     all_days.strftime("%Y%m%d").astype(int),
        "full_date":   all_days.strftime("%Y-%m-%d"),   # stored as string in CSV
        "year":        all_days.year,
        "quarter":     all_days.quarter,
        "month":       all_days.month,
        "day_of_week": all_days.dayofweek,              # 0=Monday … 6=Sunday
        "day_name":    all_days.day_name(),
    })
    return dim


# ── fact_sales ────────────────────────────────────────────────────────────────
def build_fact_sales(
    df:           pd.DataFrame,
    dim_product:  pd.DataFrame,
    dim_customer: pd.DataFrame,
    dim_location: pd.DataFrame,
    dim_date:     pd.DataFrame,
) -> pd.DataFrame:
    """
    One row per sale.  Natural keys are replaced by the integer SKs
    from each dimension table so that joins in the warehouse are fast
    (integer comparisons, not string comparisons).

    Measures (numeric facts):
        quantity, price, total_revenue

    Degenerate dimension (no own table, stored directly in fact):
        invoice_id   — the original transaction ID from the source system
        revenue_bin  — Low / Medium / High category

    Foreign keys:
        product_sk, customer_sk, location_sk, date_sk
    """
    fact = df.copy()

    # ── Replace product name with product_sk ──────────────────────────────────
    # merge() acts like a SQL LEFT JOIN on the shared column
    fact = fact.merge(dim_product, left_on="product", right_on="product_name", how="left")

    # ── Replace customer_id with customer_sk ─────────────────────────────────
    fact = fact.merge(dim_customer, on="customer_id", how="left")

    # ── Replace country with location_sk ─────────────────────────────────────
    fact = fact.merge(dim_location, on="country", how="left")

    # ── Replace invoice_date with date_sk ────────────────────────────────────
    # dim_date uses "full_date" (string YYYY-MM-DD); fact uses "invoice_date"
    fact = fact.merge(
        dim_date[["date_sk", "full_date"]],
        left_on="invoice_date",
        right_on="full_date",
        how="left",
    )

    # ── Keep only the columns needed in the fact table ───────────────────────
    fact_sales = fact[[
        "invoice_id",    # degenerate dimension (transaction ID)
        "product_sk",    # FK → dim_product
        "customer_sk",   # FK → dim_customer
        "location_sk",   # FK → dim_location
        "date_sk",       # FK → dim_date
        "quantity",      # measure
        "price",         # measure
        "total_revenue", # measure
        "revenue_bin",   # degenerate dimension (categorical)
    ]].copy()

    # Add a surrogate primary key for the fact table itself
    fact_sales.insert(0, "sale_sk", range(1, len(fact_sales) + 1))

    return fact_sales


# ── run ───────────────────────────────────────────────────────────────────────
def run(transform_path=None, star_dir=None, reports_dir=None) -> dict:
    """
    Build all five star schema tables and save them to data/star_schema/.
    Accepts optional paths so main.py can pass them centrally.
    Returns a dict with all five DataFrames.
    """
    print("\n" + "=" * 70)
    print("TASK g — DIMENSIONAL MODELING (Star Schema)")
    print("=" * 70)

    # Load the transformed (clean) dataset
    df = pd.read_csv(transform_path or TRANSFORM_PATH)
    df["customer_id"] = pd.to_numeric(df["customer_id"], errors="coerce")
    print(f"\nTransformed dataset loaded: {len(df):,} rows × {df.shape[1]} columns")

    # Build each dimension
    dim_product  = build_dim_product(df)
    dim_customer = build_dim_customer(df)
    dim_location = build_dim_location(df)
    dim_date     = build_dim_date()

    # Build the fact table using the four dimensions
    fact_sales = build_fact_sales(df, dim_product, dim_customer, dim_location, dim_date)

    # ── Print summaries ───────────────────────────────────────────────────────
    print(f"\n  dim_product  : {len(dim_product):>4} rows  (unique products)")
    print(dim_product.to_string(index=False))

    print(f"\n  dim_location : {len(dim_location):>4} rows  (unique countries)")
    print(dim_location.to_string(index=False))

    print(f"\n  dim_customer : {len(dim_customer):>4} rows  (unique customers)")
    print(f"  dim_date     : {len(dim_date):>4} rows  (all 365 days of 2023)")
    print(f"  fact_sales   : {len(fact_sales):>4} rows  (one row per sale)")

    print(f"\n  fact_sales columns: {list(fact_sales.columns)}")
    print("\n  Sample rows from fact_sales:")
    print(fact_sales.head(5).to_string(index=False))

    # ── Check referential integrity ───────────────────────────────────────────
    # All FK columns must have zero nulls after the joins
    fk_cols = ["product_sk", "customer_sk", "location_sk", "date_sk"]
    missing_fks = {col: int(fact_sales[col].isna().sum()) for col in fk_cols}
    print("\n  Referential integrity check (missing FK values after join):")
    for col, n in missing_fks.items():
        status = "OK" if n == 0 else f"WARNING — {n} unmatched rows"
        print(f"    {col:<15} : {status}")

    # ── Save to CSV ───────────────────────────────────────────────────────────
    tables = {
        "dim_product":  dim_product,
        "dim_customer": dim_customer,
        "dim_location": dim_location,
        "dim_date":     dim_date,
        "fact_sales":   fact_sales,
    }
    output_dir = star_dir or STAR_DIR
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        path = output_dir / f"{name}.csv"
        table.to_csv(path, index=False)
        print(f"\n  Saved → {path}")

    write_model_description(tables, reports_dir=reports_dir)
    print("\nStar schema ready.")
    return tables


# ── model_description ─────────────────────────────────────────────────────────
def write_model_description(tables: dict, reports_dir=None) -> None:
    """
    Write a Markdown file describing the star schema: tables, columns,
    relationships, and design decisions.
    """
    out_dir = Path(reports_dir) if reports_dir else (ROOT / "reports")
    out_dir.mkdir(exist_ok=True)

    fact   = tables["fact_sales"]
    dp     = tables["dim_product"]
    dc     = tables["dim_customer"]
    dl     = tables["dim_location"]
    dd     = tables["dim_date"]

    md  = "# Dimensional Model Description — Retail ETL Pipeline\n\n"
    md += "## Schema type: Star Schema\n\n"
    md += (
        "A star schema organises data for analytical queries: one central **fact table** "
        "records measurable events (sales), while surrounding **dimension tables** provide "
        "descriptive context (who, what, where, when).  Joins are always between the fact "
        "table and one dimension — never between two dimensions.\n\n"
    )

    # ERD in text
    md += "## Entity-Relationship Diagram (text)\n\n"
    md += "```\n"
    md += "dim_product ──┐\n"
    md += "              │\n"
    md += "dim_customer ─┤\n"
    md += "              ├── fact_sales\n"
    md += "dim_location ─┤\n"
    md += "              │\n"
    md += "dim_date ─────┘\n"
    md += "```\n\n"

    # Table descriptions
    md += "## Tables\n\n"

    md += "### dim_product\n"
    md += f"Rows: {len(dp)}  \n"
    md += "One row per unique product in the catalog.\n\n"
    md += "| Column | Type | Description |\n"
    md += "|--------|------|-------------|\n"
    md += "| product_sk | INTEGER | Surrogate primary key |\n"
    md += "| product_name | TEXT | Official product name |\n\n"

    md += "### dim_customer\n"
    md += f"Rows: {len(dc)}  \n"
    md += "One row per unique customer.\n\n"
    md += "| Column | Type | Description |\n"
    md += "|--------|------|-------------|\n"
    md += "| customer_sk | INTEGER | Surrogate primary key |\n"
    md += "| customer_id | INTEGER | Natural key from source system |\n\n"

    md += "### dim_location\n"
    md += f"Rows: {len(dl)}  \n"
    md += "One row per country (already standardized by transform.py).\n\n"
    md += "| Column | Type | Description |\n"
    md += "|--------|------|-------------|\n"
    md += "| location_sk | INTEGER | Surrogate primary key |\n"
    md += "| country | TEXT | Canonical country name |\n\n"

    md += "### dim_date\n"
    md += f"Rows: {len(dd)}  \n"
    md += (
        "One row per calendar day of 2023 — **all 365 days**, regardless of whether "
        "a sale occurred.  This allows queries to detect days with zero sales.\n\n"
    )
    md += "| Column | Type | Description |\n"
    md += "|--------|------|-------------|\n"
    md += "| date_sk | INTEGER | Surrogate key in YYYYMMDD format (e.g. 20230115) |\n"
    md += "| full_date | TEXT | Date string YYYY-MM-DD |\n"
    md += "| year | INTEGER | Calendar year (2023) |\n"
    md += "| quarter | INTEGER | Quarter of the year (1–4) |\n"
    md += "| month | INTEGER | Month number (1–12) |\n"
    md += "| day_of_week | INTEGER | Day index: 0 = Monday, 6 = Sunday |\n"
    md += "| day_name | TEXT | Day name (e.g. Monday) |\n\n"

    md += "### fact_sales\n"
    md += f"Rows: {len(fact)}  \n"
    md += "One row per sale transaction.  Foreign keys reference the four dimensions.\n\n"
    md += "| Column | Type | Role | Description |\n"
    md += "|--------|------|------|-------------|\n"
    md += "| sale_sk | INTEGER | PK | Surrogate primary key |\n"
    md += "| invoice_id | INTEGER | Degenerate dim | Original transaction ID |\n"
    md += "| product_sk | INTEGER | FK → dim_product | Which product was sold |\n"
    md += "| customer_sk | INTEGER | FK → dim_customer | Who bought it |\n"
    md += "| location_sk | INTEGER | FK → dim_location | Country of the sale |\n"
    md += "| date_sk | INTEGER | FK → dim_date | When the sale occurred |\n"
    md += "| quantity | INTEGER | Measure | Units sold |\n"
    md += "| price | REAL | Measure | Unit price (USD) |\n"
    md += "| total_revenue | REAL | Measure | quantity × price (USD) |\n"
    md += "| revenue_bin | TEXT | Degenerate dim | Low / Medium / High category |\n\n"

    md += "## Design Decisions\n\n"
    md += (
        "- **Surrogate keys** (integer SKs) are used instead of natural keys for all "
        "dimension tables.  This decouples the warehouse from the source system and makes "
        "joins faster (integer comparison vs. string comparison).\n"
        "- **dim_date covers all 365 days** of 2023, not just days with sales.  This "
        "prevents implicit filtering when calculating daily averages or detecting gaps.\n"
        "- **date_sk uses YYYYMMDD format** (e.g. 20230325).  This integer is human-readable, "
        "sorts correctly, and is a standard convention in data warehousing.\n"
        "- **invoice_id and revenue_bin** are stored directly in fact_sales as *degenerate "
        "dimensions* — they describe the transaction but do not warrant a separate table.\n"
        "- **Cleaning drops rows; transformation never drops rows**.  The fact table "
        "therefore has exactly as many rows as the cleaned dataset (3,500).\n"
    )

    path = out_dir / "model_description.md"
    path.write_text(md, encoding="utf-8")
    print(f"\n  Model description saved → {path}")


if __name__ == "__main__":
    run()
