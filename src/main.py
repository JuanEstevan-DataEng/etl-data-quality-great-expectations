"""
main.py - Pipeline orchestrator.

Runs all 9 tasks in sequence:
  a. (EDA in notebook — no script)
  b. Input validation   (Great Expectations — raw data)
  c. Quality analysis   (issues table + policy report)
  d. Cleaning           (drop/fix invalid records)
  e. Transformation     (enrich and standardize)
  f. Output validation  (Great Expectations — transformed data)
  g. Dimensional model  (star schema: 4 dims + 1 fact)
  h. Load to SQLite     (data warehouse)
  i. Business analysis  (7 KPI charts)

All file paths are defined here and passed to each module.
No module needs to know where the project root is.
"""

import os
import sys
from pathlib import Path

# Add src/ to the Python path so we can import sibling modules
SRC = Path(__file__).parent
sys.path.insert(0, str(SRC))

# ── Central path registry ─────────────────────────────────────────────────────
# Every input/output path is defined once here and passed to each task.
ROOT = SRC.parent

RAW_PATH       = ROOT / "data" / "raw"       / "retail_etl_dataset.csv"
CLEAN_PATH     = ROOT / "data" / "processed" / "retail_clean.csv"
TRANSFORM_PATH = ROOT / "data" / "processed" / "retail_transformed.csv"
STAR_DIR       = ROOT / "data" / "star_schema"
DB_PATH        = ROOT / "data" / "processed" / "data_warehouse.db"
GX_ROOT        = ROOT / "gx"
REPORTS_DIR    = ROOT / "reports"
REPORT_PATH    = REPORTS_DIR / "quality_report.md"

# Ensure output directories exist before any task runs
(ROOT / "data" / "processed").mkdir(parents=True, exist_ok=True)
STAR_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


GX_YML = """\
config_version: 3.0

datasources: {}

config_variables_file_path: uncommitted/config_variables.yml

plugins_directory: plugins/

stores:
  expectations_store:
    class_name: ExpectationsStore
    store_backend:
      class_name: TupleFilesystemStoreBackend
      base_directory: expectations/

  validations_store:
    class_name: ValidationsStore
    store_backend:
      class_name: TupleFilesystemStoreBackend
      base_directory: uncommitted/validations/

  evaluation_parameter_store:
    class_name: EvaluationParameterStore

  checkpoint_store:
    class_name: CheckpointStore
    store_backend:
      class_name: TupleFilesystemStoreBackend
      suppress_store_backend_id: true
      base_directory: checkpoints/

  profiler_store:
    class_name: ProfilerStore
    store_backend:
      class_name: TupleFilesystemStoreBackend
      suppress_store_backend_id: true
      base_directory: profilers/

expectations_store_name: expectations_store
validations_store_name: validations_store
evaluation_parameter_store_name: evaluation_parameter_store
checkpoint_store_name: checkpoint_store

data_docs_sites:
  local_site:
    class_name: SiteBuilder
    show_how_to_buttons: true
    store_backend:
      class_name: TupleFilesystemStoreBackend
      base_directory: uncommitted/data_docs/local_site/
    site_index_builder:
      class_name: DefaultSiteIndexBuilder

anonymous_usage_statistics:
  enabled: false
"""


def setup_gx(gx_root: Path) -> None:
    """
    Create the Great Expectations folder structure if it does not exist.
    This is equivalent to running `great_expectations init` manually.
    """
    # Subdirectories required by the stores defined in great_expectations.yml
    for subdir in [
        "expectations",
        "checkpoints",
        "profilers",
        "plugins",
        "uncommitted/validations",
        "uncommitted/data_docs/local_site",
    ]:
        (gx_root / subdir).mkdir(parents=True, exist_ok=True)

    # Write the main config file only if it does not already exist
    yml_path = gx_root / "great_expectations.yml"
    if not yml_path.exists():
        yml_path.write_text(GX_YML, encoding="utf-8")
        print(f"  Created → {yml_path}")

    # GE requires this file to exist even when there are no variables
    config_vars = gx_root / "uncommitted" / "config_variables.yml"
    if not config_vars.exists():
        config_vars.write_text("{}\n", encoding="utf-8")
        print(f"  Created → {config_vars}")


def check_prerequisites() -> None:
    """
    Ensure the pipeline can run:
    - Raw data file is downloaded automatically from Google Drive if missing.
    - GE folder structure is created automatically if missing.
    """
    # Download the raw dataset if it is not already present locally
    if not RAW_PATH.exists():
        print("Raw data file not found — attempting to download from Google Drive...")
        from download_data import download
        try:
            download(dest_path=RAW_PATH)
        except Exception as exc:
            print(f"\nERROR — could not download the raw data: {exc}")
            raise SystemExit(1)

    # Auto-create GE structure if the folder or any required file is missing
    gx_yml = GX_ROOT / "great_expectations.yml"
    if not GX_ROOT.exists() or not gx_yml.exists():
        print("Great Expectations folder not found — creating it now...")
        setup_gx(GX_ROOT)
        print("GE folder ready.")
    else:
        # Ensure subdirectories exist even if the root was already there
        setup_gx(GX_ROOT)

    print("Prerequisites check passed.")

def main():
    print("=" * 70)
    print("RETAIL ETL PIPELINE — Full Run")
    print("=" * 70)

    check_prerequisites()

    # ── Task a: Extraction ────────────────────────────────────────────────────
    # Load the raw CSV once. The resulting DataFrame is passed to every step
    # that needs the raw data — no other script reads the file directly.
    from extract import run as task_a
    raw_df = task_a(raw_path=RAW_PATH)

    # ── Task b: Input validation ──────────────────────────────────────────────
    from validate_input import run as task_b
    input_summary, dq_score_input, gx_context = task_b(
        df=raw_df,
        gx_root=GX_ROOT,
    )

    # ── Task c: Quality analysis ──────────────────────────────────────────────
    from quality_analysis import run as task_c
    task_c(
        df=raw_df,
        report_path=REPORT_PATH,
    )

    # ── Task d: Cleaning ──────────────────────────────────────────────────────
    from clean import run as task_d
    task_d(
        df=raw_df,
        clean_path=CLEAN_PATH,
    )

    # ── Task e: Transformation ────────────────────────────────────────────────
    from transform import run as task_e
    task_e(
        clean_path=CLEAN_PATH,
        transform_path=TRANSFORM_PATH,
    )

    # ── Task f: Output validation ─────────────────────────────────────────────
    from validate_output import run as task_f
    _comparison, dq_score_output = task_f(
        transform_path=TRANSFORM_PATH,
        gx_root=GX_ROOT,
        context=gx_context,
        input_summary=input_summary,
        dq_score_input=dq_score_input,
    )

    # ── Task g: Dimensional model ─────────────────────────────────────────────
    from dimensional_model import run as task_g
    tables = task_g(
        transform_path=TRANSFORM_PATH,
        star_dir=STAR_DIR,
        reports_dir=REPORTS_DIR,
    )

    # ── Task h: Load to SQLite ────────────────────────────────────────────────
    from load_dw import run as task_h
    task_h(
        tables=tables,
        star_dir=STAR_DIR,
        db_path=DB_PATH,
    )

    # ── Task i: Business analysis ─────────────────────────────────────────────
    # raw_path is passed so Chart 1 can compare revenue before vs. after cleaning.
    # dq_score_input / dq_score_output come from Tasks b and f respectively.
    from analysis import run as task_i
    task_i(
        db_path=DB_PATH,
        reports_dir=REPORTS_DIR,
        raw_path=RAW_PATH,
        dq_score_input=dq_score_input,
        dq_score_output=dq_score_output,
    )

    print("\n" + "=" * 70)
    print("Pipeline complete. Outputs:")
    print(f"  Clean data    → {CLEAN_PATH}")
    print(f"  Transformed   → {TRANSFORM_PATH}")
    print(f"  Star schema   → {STAR_DIR}/")
    print(f"  Data warehouse→ {DB_PATH}")
    print(f"  Quality report→ {REPORT_PATH}")
    print(f"  Charts        → {REPORTS_DIR}/chart*.png")
    print(f"  Data Docs     → {GX_ROOT}/uncommitted/data_docs/local_site/index.html")
    print("=" * 70)

if __name__ == "__main__":
    main()
    os._exit(0)
