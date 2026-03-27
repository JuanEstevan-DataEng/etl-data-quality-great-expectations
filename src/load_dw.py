"""
load_dw.py - Task h: Load Star Schema into SQLite Data Warehouse.

Reads the five CSVs from data/star_schema/ and writes them into a single
SQLite database file (data/processed/data_warehouse.db).

SQLite is a file-based relational database — no server required.
Python's built-in `sqlite3` module handles the connection, and pandas
`to_sql()` writes each DataFrame as a table.

After loading, this script runs a quick verification query for each table
to confirm the row counts match what we saved in Task g.

Deliverable: data/processed/data_warehouse.db
"""

import sqlite3
import pandas as pd
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).parent.parent
STAR_DIR = ROOT / "data" / "star_schema"
DB_PATH  = ROOT / "data" / "processed" / "data_warehouse.db"


def load_tables(star_dir=None) -> dict:
    """Read all five star schema CSVs into DataFrames."""
    source_dir = Path(star_dir) if star_dir else STAR_DIR
    tables = {}
    for name in ["dim_product", "dim_customer", "dim_location", "dim_date", "fact_sales"]:
        path = source_dir / f"{name}.csv"
        tables[name] = pd.read_csv(path)
    return tables


def write_to_sqlite(tables: dict, db_path: Path) -> None:
    """
    Write each DataFrame to a table in the SQLite database.

    if_exists="replace" — drops and recreates the table on every run,
    so the pipeline is idempotent (safe to run multiple times).

    index=False — we don't want pandas to add an extra unnamed column.
    """
    # connect() creates the file if it doesn't exist yet
    conn = sqlite3.connect(db_path)

    # Load dimensions first, then fact table (referential integrity order)
    load_order = ["dim_date", "dim_product", "dim_customer", "dim_location", "fact_sales"]
    for name in load_order:
        df = tables[name]
        df.to_sql(name, conn, if_exists="replace", index=False)
        print(f"  Loaded {len(df):>5} rows → table '{name}'")

    conn.close()


def verify(db_path: Path) -> None:
    """
    Run a SELECT COUNT(*) on each table and print the results.
    This is a quick sanity check: if the counts match Task g output,
    the load was successful.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n  Verification — row counts in database:")
    for table in ["dim_product", "dim_customer", "dim_location", "dim_date", "fact_sales"]:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")   # noqa: S608 (safe, no user input)
        count = cursor.fetchone()[0]
        print(f"    {table:<15} : {count:,} rows")

    # Also show the schema (column names + types) of fact_sales
    print("\n  Schema of fact_sales:")
    cursor.execute("PRAGMA table_info(fact_sales)")
    for row in cursor.fetchall():
        # row = (cid, name, type, notnull, dflt_value, pk)
        print(f"    {row[1]:<18} {row[2]}")

    conn.close()


def run(tables: dict | None = None, star_dir=None, db_path=None) -> None:
    """
    Full load flow.
    Accepts optional paths so main.py can pass them centrally.
    When called standalone, falls back to module-level constants.
    """
    print("\n" + "=" * 70)
    print("TASK h — LOAD TO SQLITE DATA WAREHOUSE")
    print("=" * 70)

    if tables is None:
        print("\nLoading star schema CSVs from disk...")
        tables = load_tables(star_dir)

    target = Path(db_path) if db_path else DB_PATH
    print(f"\nTarget database: {target}")
    write_to_sqlite(tables, target)
    verify(target)

    print(f"\nData warehouse ready → {target}")


if __name__ == "__main__":
    run()
