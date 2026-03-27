# Lab 4 — ETL Pipeline with Great Expectations

A complete Extract, Transform, Load (ETL) pipeline applied to a retail sales dataset for Latin America. Includes data quality validation with Great Expectations, dimensional modeling with a star schema, and business KPI analysis.

---

## Table of Contents

1. [System Requirements](#1-system-requirements)
2. [Installation and Setup](#2-installation-and-setup)
3. [Project Structure](#3-project-structure)
4. [How to Run the Pipeline](#4-how-to-run-the-pipeline)
5. [Pipeline — Step by Step](#5-pipeline--step-by-step)
6. [Data Quality Problems Found](#6-data-quality-problems-found)
7. [Results Summary](#7-results-summary)
8. [Output Files](#8-output-files)

---

## 1. System Requirements

- Python 3.10 or higher
- Linux, macOS, or Windows
- The raw data file `retail_etl_dataset.csv` must be placed in `data/raw/` before running the pipeline

---

## 2. Installation and Setup

Clone the repository and move into the project folder:

```bash
git clone <repository-url>
cd etl_lab4
```

Create a virtual environment. A virtual environment isolates this project's dependencies from the rest of your system — packages installed here will not conflict with other Python projects:

```bash
python3 -m venv .venv
```

Activate the virtual environment. Every `python` or `pip` command you run after this will use only the packages inside `.venv`:

```bash
# Linux / macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

Install all project dependencies. `requirements.txt` lists every package and its exact version so the pipeline can be reproduced identically on any machine:

```bash
pip install -r requirements.txt
```

Key dependencies and what they do:

| Package | Version | Purpose |
|---------|---------|---------|
| `pandas` | 3.0.1 | Data manipulation and transformation |
| `great-expectations` | 0.18.12 | Data quality validation and reporting |
| `matplotlib` | 3.10.8 | Chart generation |
| `seaborn` | 0.13.2 | Statistical data visualization (EDA) |
| `scipy` | 1.13.0 | Statistical functions (quantiles) |
| `sqlite3` | built-in | SQLite database (no installation needed) |

> **The raw dataset is downloaded automatically from Google Drive** the first time you run `python src/main.py`. You can also trigger the download on its own:
>
> ```bash
> python src/download_data.py
> ```
>
> If the file is already present locally the script skips the download. The `gx/` folder structure is also created automatically if missing — no manual setup needed beyond the steps above.

---

## 3. Project Structure

```
etl_lab4/
│
├── data/
│   ├── raw/                        # Source data — never modified by the pipeline
│   │   └── retail_etl_dataset.csv
│   ├── processed/                  # Pipeline intermediate outputs (auto-generated)
│   │   ├── retail_clean.csv
│   │   ├── retail_transformed.csv
│   │   └── data_warehouse.db
│   └── star_schema/                # Star schema tables as CSV (auto-generated)
│       ├── dim_product.csv
│       ├── dim_customer.csv
│       ├── dim_location.csv
│       ├── dim_date.csv
│       └── fact_sales.csv
│
├── gx/                             # Great Expectations workspace
│   ├── great_expectations.yml      # GE configuration (committed to git)
│   └── uncommitted/
│       ├── config_variables.yml    # GE environment variables (committed, contains {})
│       └── data_docs/              # Auto-generated HTML quality report
│
├── notebooks/
│   └── data_profiling.ipynb        # Task a — Exploratory Data Analysis (EDA)
│
├── reports/                        # Generated reports and charts
│   ├── quality_report.md           # Task c — Quality issues and policies
│   ├── model_description.md        # Task g — Star schema description
│   └── chart1_*.png … chart7_*.png # Task i — Business KPI charts
│
├── src/                            # Pipeline source code
│   ├── main.py                     # Orchestrator — single entry point
│   ├── extract.py                  # Task a — Load raw CSV into memory
│   ├── validate_input.py           # Task b — GE validation on raw data
│   ├── quality_analysis.py         # Task c — Quality report and policies
│   ├── clean.py                    # Task d — Drop and fix invalid records
│   ├── transform.py                # Task e — Standardize and enrich data
│   ├── validate_output.py          # Task f — GE validation on clean data
│   ├── dimensional_model.py        # Task g — Build star schema tables
│   ├── load_dw.py                  # Task h — Load tables into SQLite
│   └── analysis.py                 # Task i — Generate KPI charts
│
├── requirements.txt
├── .gitignore
└── README.md
```

> **Important about `gx/`:** It is Great Expectations' storage — GE writes the expectation suite JSONs and validation results there automatically when the pipeline runs.

---

## 4. How to Run the Pipeline

With the virtual environment active, run the orchestrator from the project root:

```bash
python src/main.py
```

This runs all 9 tasks in sequence. When finished you will see:

```
Pipeline complete. Outputs:
  Clean data    → data/processed/retail_clean.csv
  Transformed   → data/processed/retail_transformed.csv
  Star schema   → data/star_schema/
  Data warehouse→ data/processed/data_warehouse.db
  Quality report→ reports/quality_report.md
  Charts        → reports/chart*.png
  Data Docs     → gx/uncommitted/data_docs/local_site/index.html
```

To open the Great Expectations visual HTML report in your browser:

```bash
# Linux
xdg-open gx/uncommitted/data_docs/local_site/index.html

# macOS
open gx/uncommitted/data_docs/local_site/index.html
```

Each script can also be run independently. If a script needs data from a previous step it loads the corresponding CSV automatically:

```bash
python src/extract.py
python src/validate_input.py
python src/clean.py
python src/transform.py
python src/validate_output.py
python src/dimensional_model.py
python src/load_dw.py
python src/analysis.py
```

---

## 5. Pipeline — Step by Step

The pipeline follows the classic ETL flow with two data quality checkpoints:

```
Raw CSV
   │
   ▼
[a] extract          → loads the CSV once into memory as a DataFrame
   │
   ├──► [b] validate_input   → measures raw data quality  (DQ Score: 10%)
   ├──► [c] quality_analysis → documents problems and quality policies
   └──► [d] clean            → drops / fixes invalid records
                  └── writes retail_clean.csv
   ▼
[e] transform        → standardizes and enriches the clean data
          └── writes retail_transformed.csv
   │
   ▼
[f] validate_output  → verifies cleaning resolved all issues  (DQ Score: 100%)
   │
   ▼
[g] dimensional_model → builds the star schema (4 dims + 1 fact)
   │
   ▼
[h] load_dw          → loads all 5 tables into SQLite
   │
   ▼
[i] analysis         → generates 7 PNG KPI charts
```

---

### Task a — Extraction (`extract.py`)

**Single responsibility:** read the raw CSV file and return a DataFrame with correct data types. This is the only place in the entire pipeline where the source file is read.

The file is loaded with `dtype=str` first — this preserves every cell's exact original value. For example, the string `"N/A"` in `invoice_date` stays as the string `"N/A"` instead of being silently converted to Python `None`. Numeric columns are then cast explicitly using `pd.to_numeric(errors="coerce")`, which turns unparseable values into `NaN` rather than raising an error.

The resulting DataFrame is passed in memory to tasks b, c, and d — none of them re-read the file.

---

### Task b — Input Validation (`validate_input.py`)

**Responsibility:** measure the quality of the raw data using Great Expectations. The goal here is NOT for the rules to pass — most of them are expected to fail. This establishes a quality baseline called the **DQ Score**.

Ten expectations are defined covering all 6 data quality dimensions:

| Dimension | Expectation | Column |
|-----------|-------------|--------|
| Completeness | No nulls | `customer_id`, `invoice_date` |
| Uniqueness | Unique values | `invoice_id` |
| Validity | Valid range | `quantity >= 1`, `price > 0.01`, `product` in catalog |
| Accuracy | Positive value | `total_revenue > 0.01` |
| Consistency | Canonical values | `country` in {Colombia, Ecuador, Peru, Chile} |
| Timeliness | Format and date range | `invoice_date` in YYYY-MM-DD format, within 2023 |

**Input DQ Score: 10%** — only 1 of 10 expectations passes on raw data (`product` already has the correct catalog values).

Great Expectations works through an abstraction layer: a `Datasource` wraps the DataFrame, a `BatchRequest` selects a specific batch of data, and a `Validator` runs the expectations against it. After validation, GE automatically generates the HTML report under `gx/uncommitted/data_docs/`.

---

### Task c — Quality Analysis (`quality_analysis.py`)

**Responsibility:** produce written evidence of each problem and propose data quality policies for the future.

Outputs `reports/quality_report.md` with two sections:

**Section c.1 — Issues table:** 8 identified problems, each with the affected column, a real example from the data, its quality dimension, and its business impact.

**Section c.2 — Quality Policies (P-01 through P-08):** 8 proposed policies. The first 6 address the most critical problems (invoice_id uniqueness, quantity and price validity, country consistency, invoice_date timeliness, total_revenue accuracy). P-07 and P-08 are original policies: `customer_id` must not be null and `product` must belong to the official 8-item catalog.

Each policy includes the corresponding Great Expectations check that enforces it, its severity (Critical / High / Medium), and which business objectives it protects.

---

### Task d — Cleaning (`clean.py`)

**Responsibility:** remove or fix records that cannot be used reliably. This is the only script that can **delete rows** from the dataset.

Seven cleaning steps are applied in logical order — each step operates on the result of the previous one:

| Step | Action | Rows removed |
|------|--------|-------------|
| 1 | Drop duplicate `invoice_id` (keep first occurrence) | ~1,065 |
| 2 | Drop rows where `quantity < 1` (negative or zero units) | ~149 |
| 3 | Drop rows where `price <= 0` (impossible prices) | ~101 |
| 4 | Drop rows where `customer_id` is null (untraceable sales) | ~202 |
| 5 | Parse dates in 3 formats; drop only truly unreadable ones | ~15 |
| 6 | Drop future dates `> 2023-12-31` (data entry errors) | ~68 |
| 7 | **Recalculate** `total_revenue = quantity × price` where mismatched | 115 corrected (no rows dropped) |

**Result: 5,100 → 3,500 rows (1,600 removed).**

Step 5 is the most nuanced: instead of dropping every date that does not match YYYY-MM-DD, the `parse_date()` function tries three formats in sequence (`%Y-%m-%d`, `%Y/%m/%d`, `%d-%m-%Y`). A value like `"14-09-2023"` (DD-MM-YYYY format) is successfully parsed and converted to `2023-09-14` — it is kept, not dropped. Only values that fail all three formats (like `"N/A"` or empty strings) become `NaT` and are removed.

Step 7 never removes rows. `price` and `quantity` are the directly observed values (source of truth). `total_revenue` is a derived field — when it does not match `qty × price` within a ±$0.01 tolerance, it is recalculated rather than discarding the row.

---

### Task e — Transformation (`transform.py`)

**Responsibility:** standardize and enrich the clean dataset. This step **never drops rows** — it only adds or modifies values.

Six transformations are applied:

1. **Country standardization:** a `COUNTRY_MAP` dictionary maps all raw variants to the canonical title-case name (`"colombia"` → `"Colombia"`, `"CO"` → `"Colombia"`). The `.fillna(df["country"])` safety net ensures that any unexpected country value is left as-is rather than becoming `NaN`.

2. **Date parsing:** converts all dates (already in YYYY-MM-DD after cleaning) to Python `datetime` objects so their components can be extracted.

3. **Temporal feature extraction:** adds `year`, `month` (1–12), `day_of_week` (0=Monday, 6=Sunday), and `day_name` columns. These are required for time-series business analysis (BO-2).

4. **customer_id cast:** converts from `float64` (e.g. `1102.0`) to nullable `Int64` (e.g. `1102`), removing the unnecessary decimal.

5. **Product normalization:** `str.strip().str.title()` removes whitespace and ensures uniform capitalization.

6. **Feature engineering — `revenue_bin`:** classifies each sale into Low / Medium / High using tertiles (33rd and 67th percentiles of `total_revenue`). Using percentile-based thresholds instead of fixed ranges makes the categorization **relative to the dataset** — if prices change in the future, the bins adjust automatically.

**Result: 3,500 → 3,500 rows, 8 → 13 columns.**

---

### Task f — Output Validation (`validate_output.py`)

**Responsibility:** verify that cleaning and transformation resolved every quality problem. A 100% DQ Score is the minimum requirement here, not the goal.

Fourteen expectations are defined: the same 10 from the input suite (to verify the problems were fixed) plus 4 new ones for columns added during transformation:
- `month` is between 1 and 12
- `month` has no nulls
- `revenue_bin` only contains {Low, Medium, High}
- `invoice_id` has no nulls

A **comparison table** is built by matching input and output results on the key `(expectation_type, column)`:

| Status | Meaning |
|--------|---------|
| `RESOLVED` | Failed on raw data, now passes at 100% |
| `PASS` | Was already passing and still passes |
| `NEW — PASS` | New expectation for a transformation column |

**Output DQ Score: 100%** — all 14 expectations pass.

---

### Task g — Dimensional Model (`dimensional_model.py`)

**Responsibility:** reorganize the flat data (one table with everything) into a **star schema** optimized for analytical queries.

A star schema has one fact table in the center surrounded by dimension tables:

```
dim_product ──┐
              │
dim_customer ─┤
              ├── fact_sales
dim_location ─┤
              │
dim_date ─────┘
```

**Dimension tables:**

| Table | Rows | Description |
|-------|------|-------------|
| `dim_product` | 8 | One row per product in the catalog |
| `dim_customer` | 500 | One row per unique customer |
| `dim_location` | 4 | One row per country |
| `dim_date` | 365 | **One row per calendar day of 2023 — including days with no sales** |

**Fact table (`fact_sales`)** has 3,500 rows — one per sale — with:
- **Surrogate keys (SK):** integers referencing each dimension (`product_sk`, `customer_sk`, `location_sk`, `date_sk`). Storing `2` instead of `"Colombia"` in 875 rows makes JOINs faster and guarantees consistency.
- **Measures:** `quantity`, `price`, `total_revenue`
- **Degenerate dimensions:** `invoice_id` and `revenue_bin` — they describe the transaction but don't justify a separate table.

The `dim_date` covering all 365 days is a key design decision: it allows SQL queries to detect days with zero sales using a `LEFT JOIN` between `dim_date` and `fact_sales`.

The task also generates `reports/model_description.md` with a complete description of the schema, all column definitions, and the reasoning behind each design decision.

---

### Task h — Load to Data Warehouse (`load_dw.py`)

**Responsibility:** persist the 5 star schema tables into a SQLite database file.

SQLite is a file-based relational database — no server required. Python includes it natively via the `sqlite3` module.

`pandas.to_sql()` with `if_exists="replace"` makes the pipeline **idempotent**: running it multiple times always produces a correct result without accumulating duplicate data.

A verification query (`SELECT COUNT(*)`) is run on each table after loading to confirm the row counts match the star schema output from Task g.

The resulting file `data/processed/data_warehouse.db` can be opened with any SQL client (DBeaver, TablePlus, DB Browser for SQLite) and queried directly.

---

### Task i — Business Analysis (`analysis.py`)

**Responsibility:** answer the question *"How are sales evolving over time, across products, customers, and regions?"* by querying the SQLite data warehouse and producing KPI visualizations.

Charts 1–6 query `fact_sales` joined with the relevant dimension table. Chart 1 also loads the raw CSV to make the cleaning impact visible. Chart 7 uses the DQ scores returned directly by Tasks b and f.

Seven PNG charts are generated in `reports/`:

| Chart | BO | Type | KPI / Business Question |
|-------|----|------|-------------------------|
| `chart1_revenue_by_country_impact.png` | BO-1 | Grouped bar | Total revenue per country — Raw vs. Clean. Shows how duplicates and negative values inflated revenue before cleaning. |
| `chart2_revenue_boxplot_by_product.png` | BO-1 | Box plot | `total_revenue` distribution per product with outliers highlighted. Reveals the spread and anomalies within each category. |
| `chart3_monthly_revenue_trend.png` | BO-2 | Line chart | Monthly revenue trend Jan–Dec 2023. Uses the `month` column parsed from `dim_date`. |
| `chart4_transactions_by_day_of_week.png` | BO-2 | Bar chart | Transaction count by day of the week. Uses `day_of_week` from `dim_date`. |
| `chart5_top3_products_by_revenue.png` | BO-3 | Horizontal bar | Top 3 products by total revenue, sorted descending. |
| `chart6_revenue_share_by_country.png` | BO-3 | Pie chart | Revenue share by country using the standardized canonical names from `dim_location`. |
| `chart7_dq_score_comparison.png` | BO-4 | Side-by-side bar | DQ Score before cleaning (10%) vs. after cleaning (100%), sourced from the Task b and Task f validation results. |

---

## 6. Data Quality Problems Found

The raw input dataset (`retail_etl_dataset.csv`) had 8 documented quality problems:

| Column | Problem | Dimension | Rows affected |
|--------|---------|-----------|---------------|
| `invoice_id` | Duplicate IDs — same invoice appears multiple times | Uniqueness | 2,131 |
| `customer_id` | Null values — sale cannot be attributed to a customer | Completeness | 202 |
| `quantity` | Negative or zero values — physically impossible units | Validity | 149 |
| `price` | Negative or zero values — impossible unit price | Validity | 101 |
| `total_revenue` | Does not equal `quantity × price` (±$0.01 tolerance) | Accuracy | 148 |
| `country` | Inconsistent formats (`"colombia"`, `"CO"`, `"ecuador"`) | Consistency | 2,211 |
| `invoice_date` | Null-like strings (`"N/A"`, `""`, `"NULL"`) | Completeness | 13 |
| `invoice_date` | Future dates (2025–2027) and mixed formats | Timeliness | 304 |

---

## 7. Results Summary

| Metric | Value |
|--------|-------|
| Rows in raw dataset | 5,100 |
| Rows after cleaning | 3,500 |
| Rows removed | 1,600 (31.4%) |
| `total_revenue` values corrected | 115 |
| DQ Score — raw data (Task b) | **10%** (1 / 10 expectations passed) |
| DQ Score — transformed data (Task f) | **100%** (14 / 14 expectations passed) |
| Tables in the data warehouse | 5 (4 dimensions + 1 fact) |
| Days covered in `dim_date` | 365 (full year 2023) |
| Unique customers | 500 |
| Products in the catalog | 8 |

---

## 8. Output Files

All output files are excluded from version control (see `.gitignore`). They are regenerated every time `python src/main.py` is executed.

| File | Description |
|------|-------------|
| `data/processed/retail_clean.csv` | Dataset after cleaning (3,500 rows) |
| `data/processed/retail_transformed.csv` | Dataset after transformation (3,500 rows, 13 columns) |
| `data/processed/data_warehouse.db` | SQLite database with the star schema |
| `data/star_schema/*.csv` | The 5 star schema tables in CSV format |
| `reports/quality_report.md` | Quality issues and data quality policies |
| `reports/model_description.md` | Star schema description and design decisions |
| `reports/chart1_*.png … chart7_*.png` | Business KPI charts |
| `gx/uncommitted/data_docs/` | Great Expectations visual HTML report |
