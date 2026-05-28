"""
run_pipeline.py
---------------
Master pipeline runner — executes all steps in order.

PIPELINE STEPS:
  1. generate_data.py          — Synthetic PaySim-style transactions
  2. anomaly_detection.py      — Isolation Forest scoring + risk tiering
  3. eda.py                    — Exploratory data analysis + diagnostic charts
  4. sar_narrative_generator.py — SAR-style narrative text for HIGH-risk flags
  5. gliner_extraction.py      — GLiNER entity extraction → risk register

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

    # ── Step 3: Exploratory Data Analysis ───────────────────────────────────
    step(3, "Exploratory Data Analysis")
    run_eda()

    # ── Step 4: SAR narrative generation ────────────────────────────────────
    step(4, "SAR Narrative Generation")
    generate_sar_narratives(
        scored_path=config.SCORED_CSV,
        output_path=config.SAR_NARRATIVES_CSV,
        risk_threshold=config.SAR_RISK_THRESHOLD,
        max_narratives=config.SAR_MAX_NARRATIVES,
    )

    # ── Step 5: GLiNER entity extraction ────────────────────────────────────
    step(5, "GLiNER Entity Extraction → Risk Register")
    run_gliner_extraction(
        narratives_path=config.SAR_NARRATIVES_CSV,
        output_path=config.RISK_REGISTER_CSV,
        sample_size=config.GLINER_SAMPLE_SIZE,
    )

    print(f"\n{'='*60}")
    print("  PIPELINE COMPLETE")
    print(f"{'='*60}")
    print("  Outputs:")
    print(f"    {config.TRANSACTIONS_CSV}")
    print(f"    {config.SCORED_CSV}")
    print(f"    {config.EDA_DIR}/")
    print(f"    {config.SAR_NARRATIVES_CSV}")
    print(f"    {config.RISK_REGISTER_CSV}")
    print("\n  Launch dashboard:")
    print("    streamlit run dashboard.py")


if __name__ == "__main__":
    main()
