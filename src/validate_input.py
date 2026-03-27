"""
validate_input.py - Task b: Input Data Validation with Great Expectations.

This suite runs against the RAW (uncleaned) data.
The purpose is to measure current data quality, so most expectations
are expected to FAIL. The failure rate becomes our quality baseline
(DQ Score input).

Covers all 6 quality dimensions:
  - Completeness  (null values)
  - Uniqueness    (duplicate records)
  - Validity      (valid ranges and catalogs)
  - Accuracy      (total_revenue consistency)
  - Consistency   (standardized formats)
  - Timeliness    (dates within expected range)
"""

import datetime
import pandas as pd
import great_expectations as gx
from great_expectations.core.expectation_configuration import ExpectationConfiguration
from great_expectations.core.run_identifier import RunIdentifier
from great_expectations.data_context.types.resource_identifiers import (
    ExpectationSuiteIdentifier,
    ValidationResultIdentifier,
)
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).parent.parent          # project root
RAW     = ROOT / "data" / "raw" / "retail_etl_dataset.csv"
GX_ROOT = ROOT / "gx"                          # Great Expectations folder

# ── Domain constants ──────────────────────────────────────────────────────────
SUITE_NAME = "retail_input_suite"

PRODUCT_CATALOG = [
    "Mouse", "Printer", "Monitor", "Phone",
    "Laptop", "Headphones", "Keyboard", "Tablet"
]
VALID_COUNTRIES = ["Colombia", "Ecuador", "Peru", "Chile"]
DATE_REGEX      = r"^\d{4}-\d{2}-\d{2}$"       # expected format: YYYY-MM-DD


# ── Step 1: Load raw data ─────────────────────────────────────────────────────
def load_raw(raw_path=None):
    """Load the original CSV without any modifications."""
    path = raw_path or RAW
    df = pd.read_csv(path, dtype=str)
    # Cast numeric columns so GE can evaluate them correctly
    for col in ["invoice_id", "quantity"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["customer_id", "price", "total_revenue"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ── Step 2: Register the DataFrame in GE ─────────────────────────────────────
def register_datasource(context, df):
    """
    Register the DataFrame as a GE in-memory Pandas datasource.
    GE needs this step to know which data to run the expectations against.
    """
    # Check if datasource already exists to avoid duplicates
    existing = [ds["name"] for ds in context.list_datasources()]
    if "retail_in_memory" not in existing:
        datasource = context.sources.add_pandas(name="retail_in_memory")
    else:
        datasource = context.get_datasource("retail_in_memory")

    # Register the DataFrame as a data asset
    try:
        asset = datasource.add_dataframe_asset(name="retail_raw")
    except Exception:
        asset = datasource.get_asset("retail_raw")

    # batch_request tells GE: "use this specific DataFrame for validation"
    batch_request = asset.build_batch_request(dataframe=df)
    return batch_request


# ── Step 3: Build the Expectation Suite ───────────────────────────────────────
def build_suite(context):
    """
    Create the expectation suite for the RAW data.

    An Expectation Suite is a list of data quality rules.
    Each rule (ExpectationConfiguration) defines:
      - what check to perform (expectation_type)
      - on which column and with what parameters (kwargs)
      - which quality dimension it belongs to (meta)

    EXPECTED RESULT: most expectations FAIL because the raw data has known issues.
    This is intentional — it measures how bad the data is before cleaning.
    """
    # Delete existing suite to start fresh
    existing_suites = [s.expectation_suite_name for s in context.list_expectation_suites()]
    if SUITE_NAME in existing_suites:
        context.delete_expectation_suite(SUITE_NAME)

    suite = context.add_expectation_suite(expectation_suite_name=SUITE_NAME)

    expectations = [

        # ── COMPLETENESS: are there nulls where there shouldn't be? ────────────
        # customer_id must not be null (we need to know who made the purchase)
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_not_be_null",
            kwargs={"column": "customer_id"},
            meta={"dimension": "Completeness", "business_objective": "BO-3"}
        ),
        # invoice_date must not be null (we need the transaction date)
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_not_be_null",
            kwargs={"column": "invoice_date"},
            meta={"dimension": "Completeness", "business_objective": "BO-2"}
        ),

        # ── UNIQUENESS: are there duplicate IDs? ───────────────────────────────
        # Each invoice must have a unique ID
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_be_unique",
            kwargs={"column": "invoice_id"},
            meta={"dimension": "Uniqueness", "business_objective": "BO-1, BO-4"}
        ),

        # ── VALIDITY: are values within valid ranges? ──────────────────────────
        # quantity must be >= 1 (cannot be zero or negative)
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_be_between",
            kwargs={"column": "quantity", "min_value": 1},
            meta={"dimension": "Validity", "business_objective": "BO-1"}
        ),
        # price must be > 0.01 (cannot be negative or zero)
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_be_between",
            kwargs={"column": "price", "min_value": 0.01},
            meta={"dimension": "Validity", "business_objective": "BO-1"}
        ),
        # product must belong to the official 8-item catalog
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_be_in_set",
            kwargs={"column": "product", "value_set": PRODUCT_CATALOG},
            meta={"dimension": "Validity", "business_objective": "BO-3"}
        ),

        # ── ACCURACY: is total_revenue consistent with quantity x price? ───────
        # Using total_revenue > 0 as a proxy. The exact check
        # (qty x price ≈ total_revenue) is done in quality_analysis.py
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_be_between",
            kwargs={"column": "total_revenue", "min_value": 0.01},
            meta={"dimension": "Accuracy", "business_objective": "BO-1"}
        ),

        # ── CONSISTENCY: is country in the canonical format? ───────────────────
        # Only these 4 values should exist (title case, no abbreviations)
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_be_in_set",
            kwargs={"column": "country", "value_set": VALID_COUNTRIES},
            meta={"dimension": "Consistency", "business_objective": "BO-3"}
        ),

        # ── TIMELINESS: are dates valid and within the expected range? ─────────
        # Dates must follow YYYY-MM-DD format
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_match_regex",
            kwargs={"column": "invoice_date", "regex": DATE_REGEX},
            meta={"dimension": "Timeliness", "business_objective": "BO-2"}
        ),
        # Dates must fall within the year 2023
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_be_between",
            kwargs={
                "column": "invoice_date",
                "min_value": "2023-01-01",
                "max_value": "2023-12-31"
            },
            meta={"dimension": "Timeliness", "business_objective": "BO-2"}
        ),
    ]

    for exp in expectations:
        suite.add_expectation(exp)

    context.save_expectation_suite(suite)
    print(f"Suite '{SUITE_NAME}' saved with {len(suite.expectations)} expectations.")
    return suite


# ── Step 4: Run the validation ────────────────────────────────────────────────
def run_validation(context, batch_request):
    """
    Run the suite against the data batch and build a summary table.
    Computes the DQ Score: percentage of expectations that pass.
    """
    validator = context.get_validator(
        batch_request=batch_request,
        expectation_suite_name=SUITE_NAME
    )

    result = validator.validate()

    # Persist the result to the GE validations store so Data Docs can display it.
    # validator.validate() runs in-memory only; without this step the web UI
    # shows the suite page but no validation run results.
    run_id = RunIdentifier(
        run_name=SUITE_NAME,
        run_time=datetime.datetime.now(datetime.timezone.utc),
    )
    result_id = ValidationResultIdentifier(
        expectation_suite_identifier=ExpectationSuiteIdentifier(SUITE_NAME),
        run_id=run_id,
        batch_identifier="retail_raw",
    )
    context.validations_store.set(result_id, result)

    # Build a summary table with each expectation's result
    rows = []
    for r in result.results:
        exp_type      = r.expectation_config.expectation_type
        col           = r.expectation_config.kwargs.get("column", "—")
        dimension     = r.expectation_config.meta.get("dimension", "—")
        passed        = r.success
        element_count = r.result.get("element_count", 0)
        unexpected    = r.result.get("unexpected_count", 0)

        if element_count > 0:
            pass_pct = round((1 - unexpected / element_count) * 100, 2)
        else:
            pass_pct = 100.0 if passed else 0.0

        rows.append({
            "expectation":      exp_type,
            "column":           col,
            "dimension":        dimension,
            "passed":           passed,
            "pass_pct (%)":     pass_pct,
            "unexpected_count": unexpected,
        })

    summary = pd.DataFrame(rows)

    print("\n" + "=" * 70)
    print("RESULTS — INPUT VALIDATION (raw data)")
    print("=" * 70)
    print(summary.to_string(index=False))

    # DQ Score = how many expectations passed / total expectations
    n_passed = int(summary["passed"].sum())
    n_total  = len(summary)
    dq_score = round(n_passed / n_total * 100, 2)
    print(f"\nDQ Score (input) = {n_passed}/{n_total} expectations passed = {dq_score}%")

    return summary, dq_score


# ── Step 5: Generate Data Docs ────────────────────────────────────────────────
def generate_data_docs(context):
    """
    Generate the HTML report (Data Docs).
    Output: gx/uncommitted/data_docs/local_site/index.html
    Open that file in a browser to see a visual dashboard of the results.
    """
    context.build_data_docs()
    print("Data Docs generated → gx/uncommitted/data_docs/local_site/index.html")


# ── Entry point ───────────────────────────────────────────────────────────────
def run(df=None, raw_path=None, gx_root=None):
    """
    Run the full input validation flow.
    If df is provided (from extract.py via main.py), uses it directly.
    Otherwise loads the raw CSV itself (standalone usage).
    """
    print("\n" + "=" * 70)
    print("TASK b — INPUT DATA VALIDATION (Great Expectations)")
    print("=" * 70)

    if df is None:
        df = load_raw(raw_path)
    print(f"Dataset loaded: {len(df):,} rows x {df.shape[1]} columns")

    # Initialize GE context — use passed path or fall back to module constant
    context_root = str(gx_root or GX_ROOT)
    context = gx.get_context(context_root_dir=context_root)

    batch_request = register_datasource(context, df)
    build_suite(context)
    summary, dq_score = run_validation(context, batch_request)
    generate_data_docs(context)

    return summary, dq_score, context


if __name__ == "__main__":
    run()
