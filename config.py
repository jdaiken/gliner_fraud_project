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
RISK_REGISTER_CSV = OUTPUTS_DIR / "risk_register.csv"

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
