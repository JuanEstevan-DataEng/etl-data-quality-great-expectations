"""
analysis.py - Task i: Business Analysis & KPIs.

Queries the SQLite data warehouse built in Task h and produces
7 PNG charts saved to reports/.

Each chart answers a business question (BO = Business Objective):
  Chart 1 — Monthly revenue trend (BO-2)
  Chart 2 — Total revenue by product (BO-3)
  Chart 3 — Total revenue by country (BO-3)
  Chart 4 — Average transaction value (price) by product (BO-1)
  Chart 5 — Number of sales by day of the week (BO-2)
  Chart 6 — Distribution of sales by revenue bin (BO-1 / BO-4)
  Chart 7 — Top 10 customers by total revenue (BO-4)

All queries are plain SQL joining fact_sales with the relevant dimension.
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT         = Path(__file__).parent.parent
DB_PATH      = ROOT / "data" / "processed" / "data_warehouse.db"
REPORTS_DIR  = ROOT / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# Consistent style for all charts
plt.rcParams.update({
    "figure.dpi":      120,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.titlesize":    13,
    "axes.labelsize":    11,
})

BLUE   = "#4C72B0"
COLORS = ["#4C72B0", "#DD8452", "#55A868", "#C44E52"]


# ── Helper ────────────────────────────────────────────────────────────────────
def query(conn: sqlite3.Connection, sql: str) -> pd.DataFrame:
    """Run a SQL query and return the result as a DataFrame."""
    return pd.read_sql_query(sql, conn)


def save(fig: plt.Figure, filename: str) -> None: # type: ignore
    """Save the figure to reports/ and close it to free memory."""
    path = REPORTS_DIR / filename
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {path.name}")


# ── Chart 1: Monthly revenue trend ───────────────────────────────────────────
def chart_monthly_revenue(conn: sqlite3.Connection) -> None:
    """
    Bar chart showing total revenue per month.
    Joins fact_sales with dim_date to get the month number.
    Answers: Which months had the highest revenue? (BO-2)
    """
    df = query(conn, """
        SELECT
            d.month,
            ROUND(SUM(f.total_revenue), 2) AS total_revenue
        FROM fact_sales f
        JOIN dim_date d ON f.date_sk = d.date_sk
        GROUP BY d.month
        ORDER BY d.month
    """)

    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(df["month"], df["total_revenue"], color=BLUE, edgecolor="white", width=0.7)

    # Add value labels on top of each bar
    for bar in bars:
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 20_000,
            f"${bar.get_height():,.0f}",
            ha="center", va="bottom", fontsize=8
        )

    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(month_labels)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x/1e6:.1f}M"))
    ax.set_title("Monthly Revenue — 2023")
    ax.set_xlabel("Month")
    ax.set_ylabel("Total Revenue (USD)")

    save(fig, "chart1_monthly_revenue.png")


# ── Chart 2: Revenue by product ───────────────────────────────────────────────
def chart_revenue_by_product(conn: sqlite3.Connection) -> None:
    """
    Horizontal bar chart — total revenue per product category.
    Joins fact_sales with dim_product.
    Answers: Which products generate the most revenue? (BO-3)
    """
    df = query(conn, """
        SELECT
            p.product_name,
            ROUND(SUM(f.total_revenue), 2) AS total_revenue
        FROM fact_sales f
        JOIN dim_product p ON f.product_sk = p.product_sk
        GROUP BY p.product_name
        ORDER BY total_revenue DESC
    """)

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.barh(df["product_name"], df["total_revenue"], color=BLUE, edgecolor="white")

    for bar in bars:
        ax.text(
            bar.get_width() + 10_000,
            bar.get_y() + bar.get_height() / 2,
            f"${bar.get_width():,.0f}",
            va="center", fontsize=9
        )

    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x/1e6:.1f}M"))
    ax.set_title("Total Revenue by Product")
    ax.set_xlabel("Total Revenue (USD)")
    ax.invert_yaxis()   # highest value at the top

    save(fig, "chart2_revenue_by_product.png")


# ── Chart 3: Revenue by country ───────────────────────────────────────────────
def chart_revenue_by_country(conn: sqlite3.Connection) -> None:
    """
    Pie chart — revenue share per country.
    Joins fact_sales with dim_location.
    Answers: How is revenue distributed across markets? (BO-3)
    """
    df = query(conn, """
        SELECT
            l.country,
            ROUND(SUM(f.total_revenue), 2) AS total_revenue
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

    ax.set_title("Revenue Share by Country")

    save(fig, "chart3_revenue_by_country.png")


# ── Chart 4: Average price by product ────────────────────────────────────────
def chart_avg_price_by_product(conn: sqlite3.Connection) -> None:
    """
    Bar chart — average unit price per product.
    Answers: What is the average transaction value per product? (BO-1)
    """
    df = query(conn, """
        SELECT
            p.product_name,
            ROUND(AVG(f.price), 2) AS avg_price
        FROM fact_sales f
        JOIN dim_product p ON f.product_sk = p.product_sk
        GROUP BY p.product_name
        ORDER BY avg_price DESC
    """)

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(df["product_name"], df["avg_price"], color=BLUE, edgecolor="white", width=0.6)

    for bar in bars:
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 3,
            f"${bar.get_height():,.2f}",
            ha="center", va="bottom", fontsize=9
        )

    ax.set_title("Average Unit Price by Product")
    ax.set_xlabel("Product")
    ax.set_ylabel("Average Price (USD)")
    ax.set_ylim(0, df["avg_price"].max() * 1.15)

    save(fig, "chart4_avg_price_by_product.png")


# ── Chart 5: Sales count by day of week ──────────────────────────────────────
def chart_sales_by_day_of_week(conn: sqlite3.Connection) -> None:
    """
    Bar chart — number of transactions per day of the week.
    Joins fact_sales with dim_date.
    Answers: On which days do most sales occur? (BO-2)
    """
    df = query(conn, """
        SELECT
            d.day_of_week,
            d.day_name,
            COUNT(f.sale_sk) AS num_sales
        FROM fact_sales f
        JOIN dim_date d ON f.date_sk = d.date_sk
        GROUP BY d.day_of_week, d.day_name
        ORDER BY d.day_of_week
    """)

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(df["day_name"], df["num_sales"], color=BLUE, edgecolor="white", width=0.6)

    for bar in bars:
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1,
            str(int(bar.get_height())),
            ha="center", va="bottom", fontsize=9
        )

    ax.set_title("Number of Sales by Day of the Week")
    ax.set_xlabel("Day")
    ax.set_ylabel("Number of Sales")

    save(fig, "chart5_sales_by_day_of_week.png")


# ── Chart 6: Sales distribution by revenue bin ───────────────────────────────
def chart_revenue_bin_distribution(conn: sqlite3.Connection) -> None:
    """
    Bar chart — how many sales fall into each revenue bin (Low/Medium/High).
    Answers: What proportion of transactions are high-value? (BO-1 / BO-4)
    """
    df = query(conn, """
        SELECT
            revenue_bin,
            COUNT(sale_sk)              AS num_sales,
            ROUND(SUM(total_revenue), 2) AS total_revenue
        FROM fact_sales
        GROUP BY revenue_bin
        ORDER BY
            CASE revenue_bin
                WHEN 'Low'    THEN 1
                WHEN 'Medium' THEN 2
                WHEN 'High'   THEN 3
            END
    """)

    bin_colors = {"Low": "#4C72B0", "Medium": "#DD8452", "High": "#55A868"}
    colors = [bin_colors[b] for b in df["revenue_bin"]]

    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(df["revenue_bin"], df["num_sales"], color=colors, edgecolor="white", width=0.5)

    for bar, revenue in zip(bars, df["total_revenue"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 5,
            f"{int(bar.get_height())} sales\n${revenue/1e6:.2f}M",
            ha="center", va="bottom", fontsize=9
        )

    ax.set_title("Sales Distribution by Revenue Bin")
    ax.set_xlabel("Revenue Bin")
    ax.set_ylabel("Number of Sales")

    save(fig, "chart6_revenue_bin_distribution.png")


# ── Chart 7: Top 10 customers by revenue ─────────────────────────────────────
def chart_top10_customers(conn: sqlite3.Connection) -> None:
    """
    Horizontal bar chart — top 10 customers ranked by total revenue.
    Joins fact_sales with dim_customer.
    Answers: Who are our most valuable customers? (BO-4)
    """
    df = query(conn, """
        SELECT
            c.customer_id,
            ROUND(SUM(f.total_revenue), 2) AS total_revenue,
            COUNT(f.sale_sk)               AS num_purchases
        FROM fact_sales f
        JOIN dim_customer c ON f.customer_sk = c.customer_sk
        GROUP BY c.customer_id
        ORDER BY total_revenue DESC
        LIMIT 10
    """)
    df["label"] = "Customer " + df["customer_id"].astype(int).astype(str)

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.barh(df["label"], df["total_revenue"], color=BLUE, edgecolor="white")

    for bar, purchases in zip(bars, df["num_purchases"]):
        ax.text(
            bar.get_width() + 500,
            bar.get_y() + bar.get_height() / 2,
            f"${bar.get_width():,.0f}  ({purchases} purchases)",
            va="center", fontsize=9
        )

    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax.set_title("Top 10 Customers by Total Revenue")
    ax.set_xlabel("Total Revenue (USD)")
    ax.invert_yaxis()

    save(fig, "chart7_top10_customers.png")


# ── run ───────────────────────────────────────────────────────────────────────
def run(db_path=None, reports_dir=None) -> None:
    """
    Connect to the data warehouse and generate all 7 charts.
    Accepts optional paths so main.py can pass them centrally.
    """
    # global must be declared before any use of the variable in this scope
    global REPORTS_DIR

    print("\n" + "=" * 70)
    print("TASK i — BUSINESS ANALYSIS & KPIs")
    print("=" * 70)

    target_db      = Path(db_path)      if db_path      else DB_PATH
    target_reports = Path(reports_dir)  if reports_dir  else REPORTS_DIR
    target_reports.mkdir(exist_ok=True)

    # Override the module-level REPORTS_DIR so save() writes charts to the right folder
    REPORTS_DIR = target_reports

    conn = sqlite3.connect(target_db)
    print(f"\nConnected to: {target_db.name}")
    print(f"Output directory: {target_reports}\n")

    chart_monthly_revenue(conn)
    chart_revenue_by_product(conn)
    chart_revenue_by_country(conn)
    chart_avg_price_by_product(conn)
    chart_sales_by_day_of_week(conn)
    chart_revenue_bin_distribution(conn)
    chart_top10_customers(conn)

    conn.close()
    print("\nAll 7 charts generated successfully.")


if __name__ == "__main__":
    run()
