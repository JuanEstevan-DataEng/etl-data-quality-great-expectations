"""
validate_output.py - Task f: Post-Transformation Validation.

This suite runs against the TRANSFORMED (clean) data.
Unlike Task b where most expectations failed, here ALL expectations
must PASS. If any fail, the pipeline should not proceed to loading.

Two types of expectations are included:
  - Core expectations: same rules as the input suite (to verify cleaning worked)
  - New expectations:  rules specific to the new columns added in transformation
                       (month, revenue_bin, day_of_week)

Deliverable: comparison table (raw pass % vs clean pass %) + DQ Scores
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
ROOT           = Path(__file__).parent.parent
TRANSFORM_PATH = ROOT / "data" / "processed" / "retail_transformed.csv"
GX_ROOT        = ROOT / "gx"

# ── Constants ─────────────────────────────────────────────────────────────────
OUTPUT_SUITE    = "retail_output_suite"
PRODUCT_CATALOG = ["Mouse", "Printer", "Monitor", "Phone",
                   "Laptop", "Headphones", "Keyboard", "Tablet"]
VALID_COUNTRIES = ["Colombia", "Ecuador", "Peru", "Chile"]
DATE_REGEX      = r"^\d{4}-\d{2}-\d{2}$"


def load_transformed(transform_path=None):
    """Load the transformed CSV and cast numeric columns."""
    df = pd.read_csv(transform_path or TRANSFORM_PATH)
    for col in ["invoice_id", "quantity", "year", "month", "day_of_week", "customer_id"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["price", "total_revenue"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def register_datasource(context, df):
    """Register the transformed DataFrame as a new GE in-memory datasource."""
    existing = [ds["name"] for ds in context.list_datasources()]
    if "retail_output" not in existing:
        datasource = context.sources.add_pandas(name="retail_output")
    else:
        datasource = context.get_datasource("retail_output")

    try:
        asset = datasource.add_dataframe_asset(name="retail_transformed")
    except Exception:
        asset = datasource.get_asset("retail_transformed")

    return asset.build_batch_request(dataframe=df)


def build_output_suite(context):
    """
    Build the output expectation suite.
    All expectations must PASS — this is a quality contract, not a measurement.
    """
    existing = [s.expectation_suite_name for s in context.list_expectation_suites()]
    if OUTPUT_SUITE in existing:
        context.delete_expectation_suite(OUTPUT_SUITE)

    suite = context.add_expectation_suite(expectation_suite_name=OUTPUT_SUITE)

    expectations = [
        # ── Core expectations (same as input suite) ───────────────────────────
        # These verify that cleaning actually resolved the issues found in Task b

        # Completeness: no nulls in critical columns
        ExpectationConfiguration("expect_column_values_to_not_be_null",
                                 {"column": "customer_id"},
                                 meta={"dimension": "Completeness"}),
        ExpectationConfiguration("expect_column_values_to_not_be_null",
                                 {"column": "invoice_date"},
                                 meta={"dimension": "Completeness"}),
        ExpectationConfiguration("expect_column_values_to_not_be_null",
                                 {"column": "invoice_id"},
                                 meta={"dimension": "Completeness"}),

        # Uniqueness: no duplicate invoice IDs
        ExpectationConfiguration("expect_column_values_to_be_unique",
                                 {"column": "invoice_id"},
                                 meta={"dimension": "Uniqueness"}),

        # Validity: values within valid ranges
        ExpectationConfiguration("expect_column_values_to_be_between",
                                 {"column": "quantity", "min_value": 1},
                                 meta={"dimension": "Validity"}),
        ExpectationConfiguration("expect_column_values_to_be_between",
                                 {"column": "price", "min_value": 0.01},
                                 meta={"dimension": "Validity"}),
        ExpectationConfiguration("expect_column_values_to_be_in_set",
                                 {"column": "product", "value_set": PRODUCT_CATALOG},
                                 meta={"dimension": "Validity"}),

        # Accuracy: total_revenue is positive
        ExpectationConfiguration("expect_column_values_to_be_between",
                                 {"column": "total_revenue", "min_value": 0.01},
                                 meta={"dimension": "Accuracy"}),

        # Consistency: only canonical country names
        ExpectationConfiguration("expect_column_values_to_be_in_set",
                                 {"column": "country", "value_set": VALID_COUNTRIES},
                                 meta={"dimension": "Consistency"}),

        # Timeliness: correct date format and within 2023
        ExpectationConfiguration("expect_column_values_to_match_regex",
                                 {"column": "invoice_date", "regex": DATE_REGEX},
                                 meta={"dimension": "Timeliness"}),
        ExpectationConfiguration("expect_column_values_to_be_between",
                                 {"column": "invoice_date",
                                  "min_value": "2023-01-01", "max_value": "2023-12-31"},
                                 meta={"dimension": "Timeliness"}),

        # ── New expectations for transformation-specific columns ───────────────
        # These validate that the new columns added in Task e are correct

        # month must be between 1 and 12
        ExpectationConfiguration("expect_column_values_to_be_between",
                                 {"column": "month", "min_value": 1, "max_value": 12},
                                 meta={"dimension": "Validity (derived)"}),

        # month must have no nulls (every row must have a valid date)
        ExpectationConfiguration("expect_column_values_to_not_be_null",
                                 {"column": "month"},
                                 meta={"dimension": "Completeness (derived)"}),

        # revenue_bin must only contain the three expected categories
        ExpectationConfiguration("expect_column_values_to_be_in_set",
                                 {"column": "revenue_bin",
                                  "value_set": ["Low", "Medium", "High"]},
                                 meta={"dimension": "Validity (derived)"}),
    ]

    for exp in expectations:
        suite.add_expectation(exp)

    context.save_expectation_suite(suite)
    print(f"Output suite '{OUTPUT_SUITE}' saved with {len(suite.expectations)} expectations.")
    return suite


def run_and_compare(context, batch_request, input_summary, dq_score_input):
    """
    Run the output suite and build a comparison table:
    raw pass % vs clean pass % for each expectation.
    """
    validator = context.get_validator(
        batch_request=batch_request,
        expectation_suite_name=OUTPUT_SUITE
    )
    result = validator.validate()

    # Persist to validations store so Data Docs shows the run results page.
    run_id = RunIdentifier(
        run_name=OUTPUT_SUITE,
        run_time=datetime.datetime.now(datetime.timezone.utc),
    )
    result_id = ValidationResultIdentifier(
        expectation_suite_identifier=ExpectationSuiteIdentifier(OUTPUT_SUITE),
        run_id=run_id,
        batch_identifier="retail_transformed",
    )
    context.validations_store.set(result_id, result)

    # Build a dict of output results keyed by (expectation_type, column)
    output_results = {}
    for r in result.results:
        exp_type  = r.expectation_config.expectation_type
        col       = r.expectation_config.kwargs.get("column", "—")
        dim       = r.expectation_config.meta.get("dimension", "—")
        elem      = r.result.get("element_count", 0)
        unexpected = r.result.get("unexpected_count", 0)
        pass_pct  = round((1 - unexpected / elem) * 100, 2) if elem > 0 else (100.0 if r.success else 0.0)
        output_results[(exp_type, col)] = {
            "dimension":     dim,
            "passed":        r.success,
            "clean_pass_pct": pass_pct,
        }

    # Build comparison table matching input vs output expectations
    rows = []
    for _, row in input_summary.iterrows():
        key = (row["expectation"], row["column"])
        out = output_results.get(key, {})
        clean_pct = out.get("clean_pass_pct", None)

        if clean_pct is not None:
            if clean_pct == 100.0 and row["pass_pct (%)"] < 100.0:
                status = "RESOLVED"
            elif clean_pct == 100.0:
                status = "PASS"
            else:
                status = "FAIL"
        else:
            status = "N/A"

        rows.append({
            "expectation":    row["expectation"],
            "column":         row["column"],
            "dimension":      row["dimension"],
            "raw_pass_%":     row["pass_pct (%)"],
            "clean_pass_%":   clean_pct,
            "status":         status,
        })

    # Add transformation-specific expectations (not in input suite)
    for (exp_type, col), data in output_results.items():
        already_in = any(r["expectation"] == exp_type and r["column"] == col for r in rows)
        if not already_in:
            rows.append({
                "expectation":  exp_type,
                "column":       col,
                "dimension":    data["dimension"],
                "raw_pass_%":   "N/A (new)",
                "clean_pass_%": data["clean_pass_pct"],
                "status":       "NEW — PASS" if data["passed"] else "NEW — FAIL",
            })

    comparison = pd.DataFrame(rows)

    print("\n" + "=" * 70)
    print("RESULTS — OUTPUT VALIDATION (transformed data)")
    print("=" * 70)
    print(comparison.to_string(index=False))

    # DQ Scores
    dq_score_output = round(
        sum(1 for d in output_results.values() if d["clean_pass_pct"] == 100.0)
        / len(output_results) * 100, 2
    )

    print(f"\nDQ Score (input)  = {dq_score_input}%   ← raw data, before cleaning")
    print(f"DQ Score (output) = {dq_score_output}%  ← transformed data, after cleaning")

    if result.success:
        print("\nAll output expectations PASSED — pipeline can proceed to loading.")
    else:
        failing = [r.expectation_config.expectation_type for r in result.results if not r.success]
        print(f"\nWARNING: {len(failing)} expectation(s) failed: {failing}")

    context.build_data_docs()
    print("Data Docs updated → gx/uncommitted/data_docs/local_site/index.html")

    return comparison, dq_score_output


def run(transform_path=None, gx_root=None, context=None, input_summary=None, dq_score_input=None):
    """
    Run the full output validation flow.
    Accepts optional paths so main.py can pass them centrally.
    When called standalone, falls back to module-level constants.
    """
    print("\n" + "=" * 70)
    print("TASK f — POST-TRANSFORMATION VALIDATION (Great Expectations)")
    print("=" * 70)

    df = load_transformed(transform_path)
    print(f"Transformed dataset loaded: {len(df):,} rows x {df.shape[1]} columns")

    if context is None:
        context = gx.get_context(context_root_dir=str(gx_root or GX_ROOT))

    batch_request = register_datasource(context, df)
    build_output_suite(context)

    # If no input_summary is provided, run validate_input first to get it
    if input_summary is None:
        print("\nNo input summary provided — running validate_input first...")
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        from validate_input import run as vi_run
        input_summary, dq_score_input, context = vi_run(gx_root=gx_root)

    comparison, dq_score_output = run_and_compare(
        context, batch_request, input_summary, dq_score_input
    )

    return comparison, dq_score_output


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from validate_input import run as vi_run

    input_summary, dq_score_input, ctx = vi_run()
    run(context=ctx, input_summary=input_summary, dq_score_input=dq_score_input)
