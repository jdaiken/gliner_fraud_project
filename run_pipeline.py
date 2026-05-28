"""
run_pipeline.py
---------------
Master pipeline runner — executes all steps in order.

PIPELINE STEPS:
  1. generate_data.py           — Synthetic PaySim-style transactions
  2. anomaly_detection.py       — Isolation Forest scoring + risk tiering
  3. profit_analysis.py         — Financial impact (profit / loss rollups)
  4. eda.py                     — Exploratory data analysis + diagnostic charts
  5. sar_narrative_generator.py — SAR-style narrative text for HIGH-risk flags
  6. sar_topic_modeling.py      — Topic themes across SAR narrative corpus
  7. gliner_extraction.py       — GLiNER entity extraction → risk register
  8. build_workpaper.py         — Excel analyst workpaper

USING REAL DATA:
  1. Download PaySim from https://www.kaggle.com/datasets/ealaxi/paysim1
  2. Place the CSV in data/ as transactions.csv
  3. Comment out Step 1 below — everything else runs unchanged.
"""

import config
from generate_data import main as generate_main
from anomaly_detection import run_detection
from eda import run_eda
from sar_narrative_generator import generate_sar_narratives
from gliner_extraction import run_gliner_extraction
from build_workpaper import build_workpaper
from sar_topic_modeling import run_sar_topic_modeling


def step(n, name):
    """Print a formatted step header for easy log scanning."""
    print(f"\n{'='*60}")
    print(f"  STEP {n}: {name}")
    print(f"{'='*60}")


def main():
    config.ensure_dirs()

    # ── Step 1: Generate synthetic transaction data ───────────────────────────
    step(1, "Generate Synthetic Transaction Data")
    df_raw = generate_main(n=config.N_TRANSACTIONS)
    print(
        f"  {len(df_raw):,} transactions | "
        f"Fraud: {df_raw['isFraud'].sum()} ({df_raw['isFraud'].mean():.2%})"
    )

    # ── Step 2: Anomaly detection ───────────────────────────────────────────
    step(2, "Anomaly Detection — Isolation Forest")
    run_detection(path=config.TRANSACTIONS_CSV, refit_calibration=True)

    step(3, "Financial Impact (Profit / Loss)")
    from profit_analysis import run_profit_analysis
    run_profit_analysis()

    # ── Step 4: Exploratory Data Analysis ───────────────────────────────────
    step(4, "Exploratory Data Analysis")
    run_eda()

    # ── Step 5: SAR narrative generation ────────────────────────────────────
    step(5, "SAR Narrative Generation")
    generate_sar_narratives(
        scored_path=config.SCORED_CSV,
        output_path=config.SAR_NARRATIVES_CSV,
        risk_threshold=config.SAR_RISK_THRESHOLD,
        max_narratives=config.SAR_MAX_NARRATIVES,
    )

    step(6, "SAR Topic Modeling")
    run_sar_topic_modeling()

    # ── Step 7: GLiNER entity extraction ────────────────────────────────────
    step(7, "GLiNER Entity Extraction → Risk Register")
    run_gliner_extraction(
        narratives_path=config.SAR_NARRATIVES_CSV,
        output_path=config.RISK_REGISTER_CSV,
        sample_size=config.GLINER_SAMPLE_SIZE,
    )

    step(8, "Analyst Excel Workpaper")
    build_workpaper(config.WORKPAPER_XLSX)

    print(f"\n{'='*60}")
    print("  PIPELINE COMPLETE")
    print(f"{'='*60}")
    print("  Outputs:")
    print(f"    {config.TRANSACTIONS_CSV}")
    print(f"    {config.SCORED_CSV}")
    print(f"    {config.EDA_DIR}/")
    print(f"    {config.SAR_NARRATIVES_CSV}")
    print(f"    {config.SAR_TOPICS_CSV}")
    print(f"    {config.SAR_TOPIC_ASSIGNMENTS_CSV}")
    print(f"    {config.RISK_REGISTER_CSV}")
    print(f"    {config.WORKPAPER_XLSX}")
    print(f"    {config.PROFIT_SUMMARY_CSV}")
    print(f"    {config.PROFIT_DETAIL_CSV}")
    print("\n  Launch dashboard:")
    print("    python launch_dashboard.py")


if __name__ == "__main__":
    main()
