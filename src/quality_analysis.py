"""
quality_analysis.py - Task c: Data Quality Analysis and Policy Proposal.

Uses the actual counts from the raw DataFrame to document each issue found,
then proposes a set of data quality policies to address them.

Deliverable: reports/quality_report.md
"""

import pandas as pd
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
RAW = ROOT / "data" / "raw" / "retail_etl_dataset.csv"
REPORTS_DIR = ROOT / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# ── c.1 Data Quality Issues ───────────────────────────────────────────────────
# Each entry describes one issue found in the raw dataset.
# "Example" uses a real value from the data to make it concrete.
DQ_ISSUES = [
    {
        "Column":          "invoice_id",
        "Issue":           "Duplicate IDs — same invoice_id appears multiple times",
        "Example":         "22951 appears 3x",
        "Dimension":       "Uniqueness",
        "Business Impact": "Revenue is double/triple-counted in BO-1 financial KPIs.",
    },
    {
        "Column":          "customer_id",
        "Issue":           "NULL values — customer cannot be identified",
        "Example":         "NaN in ~202 rows",
        "Dimension":       "Completeness",
        "Business Impact": "Sales cannot be linked to customers, breaking BO-3 analysis.",
    },
    {
        "Column":          "quantity",
        "Issue":           "Negative values — physically impossible units sold",
        "Example":         "-3 in row 5421",
        "Dimension":       "Validity",
        "Business Impact": "Negative units corrupt total_revenue calculations (BO-1).",
    },
    {
        "Column":          "price",
        "Issue":           "Negative or zero values — impossible unit price",
        "Example":         "-83.02 in several rows",
        "Dimension":       "Validity",
        "Business Impact": "Impossible prices distort average transaction value (BO-1).",
    },
    {
        "Column":          "total_revenue",
        "Issue":           "Does not equal quantity x price (tolerance +/-0.01)",
        "Example":         "qty=2, price=100.0, total_revenue=150.0",
        "Dimension":       "Accuracy",
        "Business Impact": "Financial KPIs (total revenue, avg ticket) are unreliable (BO-1, BO-4).",
    },
    {
        "Column":          "country",
        "Issue":           "Inconsistent formats — mixed case and abbreviations",
        "Example":         "'colombia', 'CO', 'ecuador'",
        "Dimension":       "Consistency",
        "Business Impact": "One country split into multiple groups breaks regional analysis (BO-3).",
    },
    {
        "Column":          "invoice_date",
        "Issue":           "Null-like strings — not real NaN but unreadable values",
        "Example":         "'N/A', 'NULL', '' in ~15 rows",
        "Dimension":       "Completeness",
        "Business Impact": "Missing dates make time-series analysis impossible (BO-2).",
    },
    {
        "Column":          "invoice_date",
        "Issue":           "Future dates and mixed formats (YYYY/MM/DD, DD-MM-YYYY)",
        "Example":         "2027-01-01; 2023/05/15; 14-09-2023",
        "Dimension":       "Timeliness",
        "Business Impact": "Out-of-range dates distort monthly trends and seasonal peaks (BO-2).",
    },
]

# ── c.2 Data Quality Policy Proposal ─────────────────────────────────────────
# Minimum 8 policies. First 6 are required by the lab; P-07 and P-08 are original.
DQ_POLICIES = [
    {
        "#":               "P-01",
        "Policy":          "invoice_id must be unique across the entire dataset.",
        "GE Expectation":  "expect_column_values_to_be_unique('invoice_id')",
        "Severity":        "Critical",
        "Addresses":       "BO-1, BO-4",
    },
    {
        "#":               "P-02",
        "Policy":          "quantity must be a positive integer (>= 1).",
        "GE Expectation":  "expect_column_values_to_be_between('quantity', min_value=1)",
        "Severity":        "Critical",
        "Addresses":       "BO-1",
    },
    {
        "#":               "P-03",
        "Policy":          "price must be greater than zero (> 0.01 USD).",
        "GE Expectation":  "expect_column_values_to_be_between('price', min_value=0.01)",
        "Severity":        "Critical",
        "Addresses":       "BO-1",
    },
    {
        "#":               "P-04",
        "Policy":          "total_revenue must equal quantity x price within +/-0.01 tolerance.",
        "GE Expectation":  "expect_column_values_to_be_between('total_revenue', min_value=0.01) [proxy]",
        "Severity":        "Critical",
        "Addresses":       "BO-1, BO-4",
    },
    {
        "#":               "P-05",
        "Policy":          "country must be one of {Colombia, Ecuador, Peru, Chile} in title case.",
        "GE Expectation":  "expect_column_values_to_be_in_set('country', [...])",
        "Severity":        "High",
        "Addresses":       "BO-3",
    },
    {
        "#":               "P-06",
        "Policy":          "invoice_date must follow YYYY-MM-DD and fall within 2023-01-01 to 2023-12-31.",
        "GE Expectation":  "expect_column_values_to_match_regex + expect_column_values_to_be_between",
        "Severity":        "High",
        "Addresses":       "BO-2",
    },
    {
        "#":               "P-07",
        "Policy":          "[Original] customer_id must not be null — every sale must be traceable to a customer.",
        "GE Expectation":  "expect_column_values_to_not_be_null('customer_id')",
        "Severity":        "High",
        "Addresses":       "BO-3, BO-4",
    },
    {
        "#":               "P-08",
        "Policy":          "[Original] product must belong to the official 8-item catalog (no free-text variants).",
        "GE Expectation":  "expect_column_values_to_be_in_set('product', PRODUCT_CATALOG)",
        "Severity":        "Medium",
        "Addresses":       "BO-3",
    },
]


# ── Compute actual counts from the raw DataFrame ───────────────────────────────
def compute_counts(df):
    """
    Calculate the real number of affected rows for each issue.
    These numbers are used to enrich the quality report with concrete evidence.
    """
    counts = {
        "total_rows":           len(df),
        "dup_invoice_rows":     int(df.duplicated(subset=["invoice_id"], keep=False).sum()),
        "null_customer":        int(df["customer_id"].isnull().sum()),
        "neg_quantity":         int((df["quantity"] < 1).sum()),
        "neg_price":            int((df["price"] <= 0).sum()),
        "revenue_mismatch":     int(
            ((df["total_revenue"] - df["quantity"] * df["price"]).abs() > 0.01).sum()
        ),
        "country_inconsistent": int(
            (~df["country"].isin(["Colombia", "Ecuador", "Peru", "Chile"])).sum()
        ),
        "future_dates":         int(
            (pd.to_datetime(df["invoice_date"], errors="coerce") > pd.Timestamp("2023-12-31")).sum()
        ),
        "null_like_dates":      int(
            df["invoice_date"].fillna("").astype(str).str.strip()
            .isin(["N/A", "NULL", "", "nan", "NaN"]).sum()
        ),
    }
    return counts


# ── Build and save the Markdown report ───────────────────────────────────────
def save_report(counts, report_path=None):
    """Write the full quality report to the given path (or default reports/)."""
    report_path = report_path or (REPORTS_DIR / "quality_report.md")

    issues_df   = pd.DataFrame(DQ_ISSUES)
    policies_df = pd.DataFrame(DQ_POLICIES)

    md  = "# Data Quality Report — Retail ETL Pipeline\n\n"
    md += f"Total rows analysed: **{counts['total_rows']:,}**\n\n"
    md += "---\n\n"

    # c.1 Issues table
    md += "## c.1 Data Quality Issues\n\n"
    md += "| Column | Issue | Example | Dimension | Business Impact |\n"
    md += "|--------|-------|---------|-----------|----------------|\n"
    for _, row in issues_df.iterrows():
        md += f"| {row['Column']} | {row['Issue']} | {row['Example']} | {row['Dimension']} | {row['Business Impact']} |\n"

    # Quantified counts as evidence
    md += "\n### Quantified Counts\n\n"
    md += f"- Duplicate invoice_id rows   : {counts['dup_invoice_rows']:,}\n"
    md += f"- NULL customer_id            : {counts['null_customer']:,}\n"
    md += f"- Negative quantity (< 1)     : {counts['neg_quantity']:,}\n"
    md += f"- Negative/zero price (<= 0)  : {counts['neg_price']:,}\n"
    md += f"- Revenue mismatches          : {counts['revenue_mismatch']:,}\n"
    md += f"- Country inconsistencies     : {counts['country_inconsistent']:,}\n"
    md += f"- Future dates (> 2023-12-31) : {counts['future_dates']:,}\n"
    md += f"- Null-like date strings      : {counts['null_like_dates']:,}\n\n"
    md += "---\n\n"

    # c.2 Policy proposal table
    md += "## c.2 Data Quality Policy Proposal\n\n"

    # Severity classification criteria — makes the report self-contained
    md += "### Severity Classification Criteria\n\n"
    md += (
        "Each policy is assigned a severity level based on two factors: "
        "whether the issue **directly corrupts a numeric calculation**, "
        "and whether it **makes an entire analysis impossible** vs. degrading a subset.\n\n"
    )
    md += "| Severity | Classification Rule | Example consequence if violated |\n"
    md += "|----------|--------------------|---------------------------------|\n"
    md += (
        "| **Critical** | The issue produces mathematically wrong financial figures. "
        "The pipeline must not proceed if this fails. "
        "| Duplicate invoice inflates total revenue; negative price produces negative revenue. |\n"
    )
    md += (
        "| **High** | The issue makes an entire analytical dimension unreliable "
        "(regional, temporal, or customer analysis), but does not corrupt numeric totals. "
        "| Inconsistent country names split one market into multiple groups; "
        "future dates distort monthly trends. |\n"
    )
    md += (
        "| **Medium** | The issue degrades quality for a subset of records "
        "but does not invalidate the global analysis. "
        "| A misspelled product name loses those sales from product reports "
        "but does not affect total revenue. |\n\n"
    )

    md += "### Policies\n\n"
    md += "| # | Policy | GE Expectation | Severity | Addresses (BO) |\n"
    md += "|---|--------|----------------|----------|----------------|\n"
    for _, row in policies_df.iterrows():
        md += (
            f"| {row['#']} "
            f"| {row['Policy']} "
            f"| `{row['GE Expectation']}` "
            f"| **{row['Severity']}** "
            f"| {row['Addresses']} |\n"
        )

    report_path.write_text(md, encoding="utf-8")
    print(f"Quality report saved → {report_path}")


# ── Entry point ───────────────────────────────────────────────────────────────
def run(df=None, raw_path=None, report_path=None):
    """
    Run the full DQ analysis.
    Accepts an optional DataFrame; if not provided, loads the raw CSV directly.
    Accepts optional paths so main.py can pass them centrally.
    """
    print("\n" + "=" * 70)
    print("TASK c — DATA QUALITY ANALYSIS AND POLICY PROPOSAL")
    print("=" * 70)

    if df is None:
        df = pd.read_csv(raw_path or RAW)
        for col in ["invoice_id", "quantity", "price", "total_revenue", "customer_id"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    counts = compute_counts(df)

    print("\n--- c.1 Data Quality Issues ---")
    print(pd.DataFrame(DQ_ISSUES).to_string(index=False))

    print("\n--- c.2 Data Quality Policies ---")
    print(pd.DataFrame(DQ_POLICIES)[["#", "Policy", "Severity"]].to_string(index=False))

    save_report(counts, report_path)


if __name__ == "__main__":
    run()
