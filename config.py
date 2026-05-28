"""
config.py
---------
Central configuration for paths, model parameters, and risk thresholds.
All paths are resolved relative to the project root (this file's directory).
"""

from pathlib import Path

# ── Project root ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent

# ── Data & outputs ────────────────────────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
EDA_DIR = OUTPUTS_DIR / "eda"
ARTIFACTS_DIR = OUTPUTS_DIR / "model_artifacts"

TRANSACTIONS_CSV = DATA_DIR / "transactions.csv"
SCORED_CSV = OUTPUTS_DIR / "scored_transactions.csv"
SAR_NARRATIVES_CSV = OUTPUTS_DIR / "sar_narratives.csv"
SAR_TOPICS_CSV = OUTPUTS_DIR / "sar_topic_summary.csv"
SAR_TOPIC_ASSIGNMENTS_CSV = OUTPUTS_DIR / "sar_topic_assignments.csv"
SAR_WORD_FREQ_CSV = OUTPUTS_DIR / "sar_word_frequencies.csv"
SAR_TOPIC_META_JSON = OUTPUTS_DIR / "sar_topic_model_meta.json"
RISK_REGISTER_CSV = OUTPUTS_DIR / "risk_register.csv"
WORKPAPER_XLSX = OUTPUTS_DIR / "fraud_risk_workpaper.xlsx"
PROFIT_SUMMARY_CSV = OUTPUTS_DIR / "profit_summary.csv"
PROFIT_DETAIL_CSV = OUTPUTS_DIR / "profit_transaction_detail.csv"
PROFIT_BY_TIER_CSV = OUTPUTS_DIR / "profit_by_tier.csv"
PROFIT_BY_TYPE_CSV = OUTPUTS_DIR / "profit_by_type.csv"
PROFIT_BY_COUNTRY_CSV = OUTPUTS_DIR / "profit_by_country.csv"
PROFIT_TOP_ACCOUNTS_CSV = OUTPUTS_DIR / "profit_top_accounts.csv"

RISK_CALIBRATION_JSON = ARTIFACTS_DIR / "risk_calibration.json"
TYPE_ENCODING_JSON = ARTIFACTS_DIR / "type_encoding.json"

# ── Data generation ───────────────────────────────────────────────────────────
RANDOM_SEED = 42
N_TRANSACTIONS = 5000

TRANSACTION_TYPES = ["PAYMENT", "TRANSFER", "CASH_OUT", "DEBIT", "CASH_IN"]
TRANSACTION_WEIGHTS = [30, 20, 25, 15, 10]
FRAUD_TYPES = ["TRANSFER", "CASH_OUT"]

COUNTRIES = ["US", "NG", "RU", "CN", "BR", "MX", "GB", "DE", "UA", "KE"]
COUNTRY_WEIGHTS = [40, 8, 8, 8, 6, 6, 6, 6, 6, 6]
FRAUD_COUNTRIES = ["NG", "RU", "UA", "KE"]
HIGH_RISK_COUNTRIES = FRAUD_COUNTRIES  # used in feature engineering

# Fixed ordinal encoding for transaction types (stable across runs)
TYPE_ENCODING = {t: i for i, t in enumerate(TRANSACTION_TYPES)}
UNKNOWN_TYPE_CODE = len(TRANSACTION_TYPES)

# ── Anomaly detection ─────────────────────────────────────────────────────────
ISOLATION_FOREST = {
    "n_estimators": 200,
    "contamination": 0.02,
    "random_state": RANDOM_SEED,
    "n_jobs": -1,
}

# Percentiles used to calibrate risk_score (stable across batches)
RISK_SCORE_PERCENTILES = (2, 98)

RISK_TIER_HIGH = 75
RISK_TIER_MEDIUM = 45

LARGE_TRANSACTION_THRESHOLD = 100_000
FRAUD_AMOUNT_THRESHOLD = 200_000
LATE_NIGHT_HOURS = range(0, 5)

# ── SAR & GLiNER ──────────────────────────────────────────────────────────────
SAR_RISK_THRESHOLD = "HIGH"
SAR_MAX_NARRATIVES = 100
GLINER_MODEL = "urchade/gliner_medium-v2.1"
GLINER_THRESHOLD = 0.4
GLINER_SAMPLE_SIZE = 50  # set to None for full extraction in pipeline
# Try Hugging Face cache first (no network). If load fails, use regex fallback so pipeline completes.
GLINER_PREFER_LOCAL_CACHE = True
GLINER_ALLOW_FALLBACK = True

FEATURE_COLS = [
    "amount",
    "balance_delta",
    "balance_drained",
    "amount_to_balance_ratio",
    "is_high_risk_type",
    "is_late_night",
    "is_high_risk_country",
    "is_large_transaction",
    "type_encoded",
    "step",
]


def ensure_dirs():
    """Create output directories if they do not exist."""
    for d in (DATA_DIR, OUTPUTS_DIR, EDA_DIR, ARTIFACTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
