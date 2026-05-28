"""
generate_data.py
----------------
Generates a synthetic PaySim-style transaction dataset for fraud detection.

PaySim simulates mobile money transactions based on a real anonymized dataset
from a multinational mobile financial service company. This generator mirrors
PaySim's statistical properties — lognormal amount distribution, transaction
type weights, and fraud-positive logic — without requiring the full 6M-row
Kaggle download during development.

To use the real PaySim dataset instead:
  1. Download from https://www.kaggle.com/datasets/ealaxi/paysim1
  2. Place PS_20174392719_1491204439457_log.csv in data/
  3. Skip this script and point anomaly_detection.py at that file directly.
"""

import random

import numpy as np
import pandas as pd

import config

random.seed(config.RANDOM_SEED)
np.random.seed(config.RANDOM_SEED)


def generate_account_id(prefix="C"):
    """
    Generate a random account ID.

    Prefix conventions mirror PaySim:
      "C" = customer account (origin of most transactions)
      "M" = merchant account (destination for PAYMENT transactions)
    """
    return f"{prefix}{random.randint(1_000_000, 9_999_999)}"


def generate_transaction(i):
    """
    Generate a single synthetic transaction record.

    Fraud probability is additive across risk factors, which mirrors how
    real AML rule engines assign risk scores before escalating to analysts.

    Args:
        i: Row index, used for transaction ID and time step calculation.

    Returns:
        dict: One row of transaction data matching the PaySim schema.
    """
    tx_type = random.choices(
        config.TRANSACTION_TYPES, weights=config.TRANSACTION_WEIGHTS
    )[0]

    amount = round(np.random.lognormal(mean=5.5, sigma=2.0), 2)
    amount = min(amount, 2_000_000)

    origin = generate_account_id("C")
    dest = generate_account_id("M" if tx_type == "PAYMENT" else "C")

    origin_balance_before = round(random.uniform(0, 500_000), 2)
    origin_balance_after = max(0, origin_balance_before - amount)

    country = random.choices(config.COUNTRIES, weights=config.COUNTRY_WEIGHTS)[0]
    hour = random.randint(0, 23)
    step = i % 744

    is_fraud = 0
    if tx_type in config.FRAUD_TYPES:
        fraud_prob = 0.003

        if amount > config.FRAUD_AMOUNT_THRESHOLD:
            fraud_prob += 0.05

        if country in config.FRAUD_COUNTRIES:
            fraud_prob += 0.04

        if hour in config.LATE_NIGHT_HOURS:
            fraud_prob += 0.02

        if origin_balance_before > 0 and origin_balance_after == 0:
            fraud_prob += 0.06

        is_fraud = int(random.random() < fraud_prob)

    return {
        "step": step,
        "transaction_id": f"TXN{i:07d}",
        "type": tx_type,
        "amount": amount,
        "nameOrig": origin,
        "oldbalanceOrg": origin_balance_before,
        "newbalanceOrig": origin_balance_after,
        "nameDest": dest,
        "oldbalanceDest": round(random.uniform(0, 200_000), 2),
        "newbalanceDest": round(random.uniform(0, 200_000), 2),
        "country": country,
        "hour": hour,
        "isFraud": is_fraud,
    }


def generate_transactions(n=None):
    """Generate n transaction records (default from config)."""
    n = n or config.N_TRANSACTIONS
    return [generate_transaction(i) for i in range(n)]


def main(n=None, output_path=None):
    """
    Generate synthetic data and write to CSV.

    Args:
        n: Number of transactions (default: config.N_TRANSACTIONS).
        output_path: Output CSV path (default: config.TRANSACTIONS_CSV).

    Returns:
        pd.DataFrame: Generated transactions.
    """
    n = n or config.N_TRANSACTIONS
    output_path = output_path or config.TRANSACTIONS_CSV

    print("Generating synthetic transaction data...")
    transactions = generate_transactions(n)
    df = pd.DataFrame(transactions)

    config.ensure_dirs()
    df.to_csv(output_path, index=False)

    print(f"Generated {len(df):,} transactions")
    print(f"Fraud cases: {df['isFraud'].sum()} ({df['isFraud'].mean():.2%})")
    print(f"Saved to {output_path}")
    return df


if __name__ == "__main__":
    main()
