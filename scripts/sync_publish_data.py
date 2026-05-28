"""Copy pipeline outputs into publish_data/ for Streamlit Cloud."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402

PUBLISH = config.PROJECT_ROOT / "publish_data"

FILES = [
    ("data/transactions.csv", config.TRANSACTIONS_CSV),
    ("outputs/scored_transactions.csv", config.SCORED_CSV),
    ("outputs/sar_narratives.csv", config.SAR_NARRATIVES_CSV),
    ("outputs/sar_topic_summary.csv", config.SAR_TOPICS_CSV),
    ("outputs/sar_topic_assignments.csv", config.SAR_TOPIC_ASSIGNMENTS_CSV),
    ("outputs/risk_register.csv", config.RISK_REGISTER_CSV),
    ("outputs/profit_summary.csv", config.PROFIT_SUMMARY_CSV),
    ("outputs/profit_by_tier.csv", config.PROFIT_BY_TIER_CSV),
    ("outputs/profit_by_type.csv", config.PROFIT_BY_TYPE_CSV),
    ("outputs/profit_top_accounts.csv", config.PROFIT_TOP_ACCOUNTS_CSV),
    ("outputs/model_artifacts/risk_calibration.json", config.RISK_CALIBRATION_JSON),
    ("outputs/model_artifacts/type_encoding.json", config.TYPE_ENCODING_JSON),
]


def main() -> None:
    missing = []
    for rel, src in FILES:
        if not src.is_file():
            missing.append(str(src))
    if missing:
        raise SystemExit(
            "Missing pipeline outputs. Run: python run_pipeline.py\n  " + "\n  ".join(missing)
        )

    for rel, src in FILES:
        dest = PUBLISH / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"  {rel}")

    print(f"\nSynced {len(FILES)} files to {PUBLISH}")


if __name__ == "__main__":
    main()
