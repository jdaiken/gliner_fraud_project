"""
Copy bundled demo CSVs into data/ and outputs/ when running on Streamlit Cloud
(or any fresh clone) so the dashboard works without running the full pipeline.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import config

PUBLISH_DIR = config.PROJECT_ROOT / "publish_data"

# (source under publish_data/, destination under project root)
BUNDLE_MAP: list[tuple[str, Path]] = [
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


def bootstrap_published_data(force: bool = False) -> bool:
    """
    Hydrate local data/outputs from publish_data/ if scored transactions are missing.

    Returns True if bootstrap ran (files were copied).
    """
    if not PUBLISH_DIR.is_dir():
        return False

    if config.SCORED_CSV.exists() and not force:
        return False

    config.ensure_dirs()
    (config.OUTPUTS_DIR / "model_artifacts").mkdir(parents=True, exist_ok=True)

    copied = 0
    for rel_src, dest in BUNDLE_MAP:
        src = PUBLISH_DIR / rel_src
        if not src.is_file():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied += 1

    return copied > 0
