"""
analysis.py - Task i: Business Analysis & KPIs.

Answers: "How are sales evolving over time, across products,
customers, and regions?"

Seven visualizations mapped to Business Objectives (BO-1 to BO-4):

  Chart 1 — BO-1: Total revenue per country  (bar, raw vs clean comparison)
  Chart 2 — BO-1: total_revenue distribution by product  (box plot + outliers)
  Chart 3 — BO-2: Monthly revenue trend Jan–Dec 2023  (line chart)
  Chart 4 — BO-2: Transaction count by day of week  (bar chart)
  Chart 5 — BO-3: Top 3 products by total revenue  (horizontal bar, sorted desc)
  Chart 6 — BO-3: Revenue share by country  (pie chart, canonical names)
  Chart 7 — BO-4: DQ Score before vs. after cleaning  (side-by-side bar)

All charts query the SQLite data warehouse except Chart 1 (which also
loads the raw CSV to show the impact of cleaning) and Chart 7 (which
uses the DQ scores returned by validate_input and validate_output).
"""

import sqlite3
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent.parent
DB_PATH     = ROOT / "data" / "processed" / "data_warehouse.db"
RAW_PATH    = ROOT / "data" / "raw" / "retail_etl_dataset.csv"
REPORTS_DIR = ROOT / "reports"

# Consistent visual style
plt.rcParams.update({
    "figure.dpi":        120,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.titlesize":    13,
    "axes.labelsize":    11,
})

BLUE    = "#4C72B0"
ORANGE  = "#DD8452"
COLORS  = ["#4C72B0", "#DD8452", "#55A868", "#C44E52"]


# ── Helpers ───────────────────────────────────────────────────────────────────
def query(conn: sqlite3.Connection, sql: str) -> pd.DataFrame:
    """Run a SQL query and return the result as a DataFrame."""
    return pd.read_sql_query(sql, conn)


def save(fig: plt.Figure, filename: str) -> None: # type: ignore
    """Save the figure to reports/ and close it to free memory."""
    path = REPORTS_DIR / filename
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {path.name}")


# ── Chart 1 — BO-1: Revenue per country (raw vs clean) ───────────────────────
def chart_revenue_by_country_impact(conn: sqlite3.Connection, raw_path=None) -> None:
    """
    Grouped bar chart showing total revenue per country BEFORE and AFTER cleaning.

    The raw data contains duplicates and negative values that inflate revenue.
    This chart makes the cleaning impact visible: each country gets two bars —
    the raw (inflated) number and the clean (reliable) number.

    Answers: How much does data quality affect reported revenue? (BO-1)
    """
    # ── Clean revenue: from the data warehouse ────────────────────────────────
    clean = query(conn, """
        SELECT l.country, ROUND(SUM(f.total_revenue), 2) AS revenue
        FROM fact_sales f
        JOIN dim_location l ON f.location_sk = l.location_sk
        GROUP BY l.country
        ORDER BY l.country
    """)

    # ── Raw revenue: load raw CSV and sum without any cleaning ────────────────
    source = raw_path or RAW_PATH
    raw_df = pd.read_csv(source)
    raw_df["total_revenue"] = pd.to_numeric(raw_df["total_revenue"], errors="coerce")

    # Map country variants to canonical names (same dict as transform.py)
    country_map = {
        "colombia": "Colombia", "CO": "Colombia", "co": "Colombia",
        "ecuador":  "Ecuador",  "EC": "Ecuador",
        "peru":     "Peru",     "PE": "Peru",
        "chile":    "Chile",    "CL": "Chile",
    }
    raw_df["country"] = raw_df["country"].map(
        lambda v: country_map.get(str(v), v)
    )
    raw = (
        raw_df.groupby("country")["total_revenue"]
        .sum().round(2).reset_index()
        .rename(columns={"total_revenue": "revenue"})
    )
    # Keep only the 4 canonical countries
    canonical = ["Chile", "Colombia", "Ecuador", "Peru"]
    raw  = raw[raw["country"].isin(canonical)].set_index("country")
    clean = clean.set_index("country")

    # ── Build grouped bar ─────────────────────────────────────────────────────
    x      = range(len(canonical))
    width  = 0.35
    fig, ax = plt.subplots(figsize=(10, 6))

    bars_raw   = ax.bar([i - width/2 for i in x],
                        [raw.loc[c, "revenue"] / 1e6 for c in canonical], # type: ignore
                        width, label="Raw (before cleaning)", color=ORANGE, alpha=0.85)
    bars_clean = ax.bar([i + width/2 for i in x],
                        [clean.loc[c, "revenue"] / 1e6 for c in canonical], # type: ignore
                        width, label="Clean (after cleaning)", color=BLUE, alpha=0.85)

    # Value labels on top of each bar
    for bar in bars_raw:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f"${bar.get_height():.2f}M", ha="center", va="bottom", fontsize=8, color=ORANGE)
    for bar in bars_clean:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f"${bar.get_height():.2f}M", ha="center", va="bottom", fontsize=8, color=BLUE)

    ax.set_xticks(list(x))
    ax.set_xticklabels(canonical)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:.1f}M"))
    ax.set_title("Total Revenue per Country — Raw vs. Clean Data (BO-1)")
    ax.set_xlabel("Country")
    ax.set_ylabel("Total Revenue (USD)")
    ax.legend()

    save(fig, "chart1_revenue_by_country_impact.png")


# ── Chart 2 — BO-1: Box plot of total_revenue by product ─────────────────────
def chart_revenue_boxplot_by_product(conn: sqlite3.Connection) -> None:
    """
    Box plot showing the distribution of total_revenue for each product.

    A box plot reveals five statistics at once: minimum, Q1, median, Q3,
    and maximum. Points beyond the whiskers are outliers.

    Answers: How is revenue distributed within each product category? (BO-1)
    """
    df = query(conn, """
        SELECT p.product_name, f.total_revenue
        FROM fact_sales f
        JOIN dim_product p ON f.product_sk = p.product_sk
        ORDER BY p.product_name
    """)

    products = sorted(df["product_name"].unique())
    data     = [df[df["product_name"] == p]["total_revenue"].values for p in products]

    fig, ax = plt.subplots(figsize=(11, 6))
    bp = ax.boxplot(
        data,
        tick_labels=products,
        patch_artist=True,    # fills the boxes with color
        showfliers=True,      # show outlier points
        flierprops=dict(marker="o", markersize=4, linestyle="none",
                        markerfacecolor=ORANGE, alpha=0.6),
        medianprops=dict(color="white", linewidth=2),
    )
    # Fill each box with the same blue
    for patch in bp["boxes"]:
        patch.set_facecolor(BLUE)
        patch.set_alpha(0.75)

    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_title("total_revenue Distribution by Product — Outliers Highlighted (BO-1)")
    ax.set_xlabel("Product")
    ax.set_ylabel("Total Revenue per Sale (USD)")

    save(fig, "chart2_revenue_boxplot_by_product.png")


# ── Chart 3 — BO-2: Monthly revenue trend (line chart) ───────────────────────
def chart_monthly_revenue_trend(conn: sqlite3.Connection) -> None:
    """
    Line chart showing total revenue for each month of 2023 (Jan–Dec).

    A line chart emphasizes continuity and trend over time, making it easier
    to spot growth, seasonality, or sudden drops compared to a bar chart.

    Answers: How is monthly revenue evolving throughout 2023? (BO-2)
    """
    df = query(conn, """
        SELECT d.month, ROUND(SUM(f.total_revenue), 2) AS total_revenue
        FROM fact_sales f
        JOIN dim_date d ON f.date_sk = d.date_sk
        GROUP BY d.month
        ORDER BY d.month
    """)

    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["month"], df["total_revenue"] / 1e6,
            marker="o", linewidth=2.5, color=BLUE, markersize=7)

    # Value label on each point
    for _, row in df.iterrows():
        ax.annotate(
            f"${row['total_revenue']/1e6:.2f}M",
            xy=(row["month"], row["total_revenue"] / 1e6),
            xytext=(0, 10), textcoords="offset points",
            ha="center", fontsize=8
        )

    ax.fill_between(df["month"], df["total_revenue"] / 1e6, alpha=0.1, color=BLUE)
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(month_labels)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:.1f}M"))
    ax.set_title("Monthly Revenue Trend — 2023 (BO-2)")
    ax.set_xlabel("Month")
    ax.set_ylabel("Total Revenue (USD)")

    save(fig, "chart3_monthly_revenue_trend.png")


# ── Chart 4 — BO-2: Transaction count by day of week ─────────────────────────
def chart_transactions_by_day_of_week(conn: sqlite3.Connection) -> None:
    """
    Bar chart showing the number of sales transactions per day of the week.

    Uses the day_of_week column from dim_date (0 = Monday, 6 = Sunday),
    which was extracted from invoice_date during the transformation step.

    Answers: On which days do most sales occur? (BO-2)
    """
    df = query(conn, """
        SELECT d.day_of_week, d.day_name, COUNT(f.sale_sk) AS num_transactions
        FROM fact_sales f
        JOIN dim_date d ON f.date_sk = d.date_sk
        GROUP BY d.day_of_week, d.day_name
        ORDER BY d.day_of_week
    """)

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(df["day_name"], df["num_transactions"],
                  color=BLUE, edgecolor="white", width=0.6)

    for bar in bars:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                str(int(bar.get_height())),
                ha="center", va="bottom", fontsize=9)

    ax.set_title("Transaction Count by Day of the Week (BO-2)")
    ax.set_xlabel("Day of the Week")
    ax.set_ylabel("Number of Transactions")

    save(fig, "chart4_transactions_by_day_of_week.png")


# ── Chart 5 — BO-3: Top 3 products by revenue (horizontal bar) ───────────────
def chart_top3_products_by_revenue(conn: sqlite3.Connection) -> None:
    """
    Horizontal bar chart showing the top 3 products ranked by total revenue,
    sorted in descending order.

    Answers: Which three products drive the most revenue? (BO-3)
    """
    df = query(conn, """
        SELECT p.product_name, ROUND(SUM(f.total_revenue), 2) AS total_revenue
        FROM fact_sales f
        JOIN dim_product p ON f.product_sk = p.product_sk
        GROUP BY p.product_name
        ORDER BY total_revenue DESC
        LIMIT 3
    """)

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.barh(df["product_name"], df["total_revenue"],
                   color=COLORS[:3], edgecolor="white")

    for bar in bars:
        ax.text(bar.get_width() + 8_000,
                bar.get_y() + bar.get_height()/2,
                f"${bar.get_width():,.0f}",
                va="center", fontsize=10)

    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v/1e6:.1f}M"))
    ax.set_title("Top 3 Products by Total Revenue (BO-3)")
    ax.set_xlabel("Total Revenue (USD)")
    ax.invert_yaxis()   # highest value at the top

    save(fig, "chart5_top3_products_by_revenue.png")


# ── Chart 6 — BO-3: Revenue share by country (pie) ───────────────────────────
def chart_revenue_share_by_country(conn: sqlite3.Connection) -> None:
    """
    Pie chart showing each country's share of total revenue.
    Uses the standardized country names from dim_location (Colombia, Ecuador,
    Peru, Chile) — the inconsistent raw variants were resolved in Task e.

    Answers: How is revenue distributed across markets? (BO-3)
    """
    df = query(conn, """
        SELECT l.country, ROUND(SUM(f.total_revenue), 2) AS total_revenue
        FROM fact_sales f
        JOIN dim_location l ON f.location_sk = l.location_sk
        GROUP BY l.country
        ORDER BY total_revenue DESC
    """)

    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, texts, autotexts = ax.pie( # type: ignore
        df["total_revenue"],
        labels=df["country"].tolist(),
        autopct="%1.1f%%",
        colors=COLORS,
        startangle=140,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
    )
    for at in autotexts:
        at.set_fontsize(10)

    ax.set_title("Revenue Share by Country — Standardized Names (BO-3)")

    save(fig, "chart6_revenue_share_by_country.png")


# ── Chart 7 — BO-4: DQ Score before vs. after cleaning ───────────────────────
def chart_dq_score_comparison(dq_score_input: float, dq_score_output: float) -> None:
    """
    Side-by-side bar chart comparing the Data Quality Score before and after
    the cleaning + transformation pipeline.

    The DQ Score is the percentage of Great Expectations expectations that
    passed: 10% on raw data (Task b) vs 100% on transformed data (Task f).
    This chart provides transparent evidence of the pipeline's impact (BO-4).

    Answers: How much did the cleaning pipeline improve data quality? (BO-4)
    """
    labels = ["Input\n(raw data)", "Output\n(transformed data)"]
    scores = [dq_score_input, dq_score_output]
    colors = [ORANGE, BLUE]

    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(labels, scores, color=colors, width=0.4, edgecolor="white")

    for bar, score in zip(bars, scores):
        ax.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + 1.5,
                f"{score:.0f}%",
                ha="center", va="bottom", fontsize=14, fontweight="bold")

    ax.set_ylim(0, 115)
    ax.axhline(100, linestyle="--", color="gray", linewidth=1, alpha=0.6)
    ax.set_title("Data Quality Score — Before vs. After Cleaning (BO-4)")
    ax.set_ylabel("DQ Score (% expectations passed)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))

    save(fig, "chart7_dq_score_comparison.png")


# ── run ───────────────────────────────────────────────────────────────────────
def run(db_path=None, reports_dir=None, raw_path=None,
        dq_score_input: float = 10.0,
        dq_score_output: float = 100.0) -> None:
    """
    Generate all 7 business analysis charts.

    Parameters
    ----------
    db_path         : path to the SQLite data warehouse
    reports_dir     : folder where PNG files will be saved
    raw_path        : path to the raw CSV (needed for Chart 1 cleaning comparison)
    dq_score_input  : DQ Score from Task b (% expectations passed on raw data)
    dq_score_output : DQ Score from Task f (% expectations passed on clean data)
    """
    global REPORTS_DIR

    print("\n" + "=" * 70)
    print("TASK i — BUSINESS ANALYSIS & KPIs")
    print("=" * 70)

    target_db      = Path(db_path)     if db_path     else DB_PATH
    target_reports = Path(reports_dir) if reports_dir else REPORTS_DIR
    target_reports.mkdir(exist_ok=True)
    REPORTS_DIR = target_reports

    conn = sqlite3.connect(target_db)
    print(f"\nConnected to : {target_db.name}")
    print(f"Output folder: {target_reports}\n")

    chart_revenue_by_country_impact(conn, raw_path)
    chart_revenue_boxplot_by_product(conn)
    chart_monthly_revenue_trend(conn)
    chart_transactions_by_day_of_week(conn)
    chart_top3_products_by_revenue(conn)
    chart_revenue_share_by_country(conn)
    chart_dq_score_comparison(dq_score_input, dq_score_output)

    conn.close()
    print(f"\nAll 7 charts generated.  DQ Score: {dq_score_input}% → {dq_score_output}%")


if __name__ == "__main__":
    run()
