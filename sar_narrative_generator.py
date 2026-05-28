"""
sar_narrative_generator.py
--------------------------
Generates synthetic SAR-style (Suspicious Activity Report) narratives
for transactions flagged as HIGH risk by the anomaly detection module.

WHY GENERATE NARRATIVES?
Real SAR narratives are confidential FinCEN filings and are not publicly
available. However, GLiNER is a text-based NLP model — it needs unstructured
prose to extract entities from. This module bridges that gap by producing
synthetic narratives that mirror the structure FinCEN actually requires:

  - Subject/account identifiers
  - Transaction amounts and balance changes
  - Geographic risk indicators
  - Time-of-activity details
  - Named risk factors and behavioral anomalies

The generated text is realistic enough that GLiNER can extract the same
entity types it would from a real SAR narrative. This makes the pipeline
a credible prototype for SAR pre-population automation.

HOW THIS APPLIES IN PRODUCTION:
In a real financial institution, this module would be replaced by actual
investigation memos, case notes, or AML system alert descriptions — the
unstructured text that compliance analysts write before filing a SAR.
GLiNER would then extract the structured fields automatically, reducing
manual data entry and improving SAR quality and consistency.
"""

import random

import pandas as pd

import config

# Fix seed so the same transactions always produce the same narratives.
# This ensures reproducibility when comparing pipeline runs.
random.seed(config.RANDOM_SEED)


# ── Narrative templates ───────────────────────────────────────────────────────
# Two templates per transaction type provide variation so the corpus doesn't
# look obviously synthetic. In production, more templates (or LLM generation)
# would improve diversity further.

# TRANSFER templates: focus on layering and structuring language that mirrors
# how real AML analysts describe suspicious wire/transfer activity.
TRANSFER_TEMPLATES = [
    (
        "Account {orig} initiated {n_tx} TRANSFER transaction(s) totaling ${amount:,.2f} "
        "within a {window}-hour window to account {dest}. The originating account balance "
        "was depleted from ${old_bal:,.2f} to ${new_bal:,.2f}. Activity originated from "
        "{country} and occurred during {time_desc}. Transaction pattern is inconsistent "
        "with established account behavior and may indicate layering or structuring activity. "
        "Risk indicators: {indicators}."
    ),
    (
        "Suspicious TRANSFER activity detected on account {orig}. A total of ${amount:,.2f} "
        "was moved to beneficiary account {dest} in {n_tx} transaction(s). Originating "
        "account balance reduced to ${new_bal:,.2f} from ${old_bal:,.2f}. Geographic origin: "
        "{country}. Time of activity: {time_desc}. "
        "This account has not previously transacted with the destination account. "
        "Risk indicators: {indicators}."
    ),
]

# CASH_OUT templates: focus on integration-phase language — cash extraction
# following prior electronic movement is a classic three-stage laundering pattern.
CASH_OUT_TEMPLATES = [
    (
        "Account {orig} conducted {n_tx} CASH_OUT transaction(s) totaling ${amount:,.2f} "
        "through agent account {dest}. Origin balance decreased from ${old_bal:,.2f} to "
        "${new_bal:,.2f}. Activity logged from {country} at {time_desc}. "
        "Rapid cash extraction following prior electronic transfers suggests possible "
        "integration phase of money laundering. Risk indicators: {indicators}."
    ),
    (
        "Elevated CASH_OUT activity flagged for account {orig}. Amount: ${amount:,.2f} "
        "via {dest}. Balance drained: ${old_bal:,.2f} \u2192 ${new_bal:,.2f}. "
        "Country of origin: {country}. Transaction time: {time_desc}. "
        "Cash-out volume is anomalous relative to 90-day account history. "
        "Risk indicators: {indicators}."
    ),
]

# Default template for other transaction types (PAYMENT, DEBIT, CASH_IN).
# These are rare in the HIGH-risk pool but need coverage.
DEFAULT_TEMPLATES = [
    (
        "Account {orig} flagged for anomalous {tx_type} activity. Transaction amount: "
        "${amount:,.2f} to account {dest}. Account balance changed from ${old_bal:,.2f} "
        "to ${new_bal:,.2f}. Activity originated from {country} at {time_desc}. "
        "Automated risk scoring system assigned HIGH risk tier based on behavioral "
        "deviation from account baseline. Risk indicators: {indicators}."
    ),
]


# ── Risk indicator library ────────────────────────────────────────────────────
# Each key maps to a human-readable indicator description that gets embedded
# in the narrative. These mirror the feature flags created in anomaly_detection.py,
# making the narrative text directly traceable back to the model's reasoning.
ALL_INDICATORS = {
    "balance_drained":      "account balance fully depleted in single transaction",
    "is_large_transaction": "transaction amount exceeds $100,000 threshold",
    "is_late_night":        "activity occurred between 00:00\u201305:00 local time",
    "is_high_risk_country": "transaction originated from high-risk jurisdiction",
    "is_high_risk_type":    "transaction type associated with elevated layering risk",
    "high_ratio":           "transaction amount represents >80% of available balance",
}


def build_indicators(row):
    """
    Build a human-readable risk indicator string for a transaction row.

    Checks each binary risk flag on the row and assembles a list of plain-
    English descriptions. This becomes the {indicators} field in the narrative
    template, making it auditable — an analyst reading the SAR can trace each
    indicator back to the underlying data field.

    If no specific flags are set (rare for HIGH-risk transactions), falls back
    to a generic model-based indicator to ensure the narrative is never empty.

    Args:
        row: A pandas Series or dict representing one scored transaction.

    Returns:
        str: Semicolon-delimited list of active risk indicator descriptions.
    """
    active = []

    if row.get("balance_drained", 0):
        active.append(ALL_INDICATORS["balance_drained"])
    if row.get("is_large_transaction", 0):
        active.append(ALL_INDICATORS["is_large_transaction"])
    if row.get("is_late_night", 0):
        active.append(ALL_INDICATORS["is_late_night"])
    if row.get("is_high_risk_country", 0):
        active.append(ALL_INDICATORS["is_high_risk_country"])
    # amount_to_balance_ratio > 0.8 means the transaction consumed >80% of the account
    if row.get("amount_to_balance_ratio", 0) > 0.8:
        active.append(ALL_INDICATORS["high_ratio"])

    # Fallback: if no named flags triggered, note the model flagged it statistically
    if not active:
        active.append("statistical anomaly detected by Isolation Forest model")

    return "; ".join(active)


def time_description(hour):
    """
    Convert a 24-hour integer to a human-readable time description.

    The description is embedded in SAR narratives and extracted by GLiNER
    as a "time or hour" entity. Buckets mirror how compliance analysts
    typically categorize transaction timing in AML investigations.

    Args:
        hour: Integer 0–23 representing the hour of the transaction.

    Returns:
        str: e.g. "03:00 (late night / off-hours)"
    """
    if 0 <= hour <= 5:
        return f"{hour:02d}:00 (late night / off-hours)"
    elif 6 <= hour <= 11:
        return f"{hour:02d}:00 (morning)"
    elif 12 <= hour <= 17:
        return f"{hour:02d}:00 (business hours)"
    else:
        return f"{hour:02d}:00 (evening)"


def generate_narrative(row):
    """
    Generate a single SAR-style narrative for one flagged transaction.

    Selects the appropriate template set based on transaction type, then
    randomly picks one template and fills in the named placeholders.
    The randomization in n_tx and window adds surface variation while
    keeping all factual fields (amount, balances, accounts) accurate.

    Args:
        row: A pandas Series representing one HIGH-risk transaction with
             all engineered feature columns present.

    Returns:
        str: A formatted SAR narrative string.
    """
    tx_type    = row["type"]
    indicators = build_indicators(row)
    time_desc  = time_description(row.get("hour", 12))

    # n_tx and window are narrative flavor — not derived from real data.
    # In production these would come from actual transaction cluster counts.
    n_tx   = random.randint(1, 4)
    window = random.choice([4, 6, 12, 24])

    # All factual fields pulled directly from the scored transaction row
    params = dict(
        orig     = row["nameOrig"],
        dest     = row["nameDest"],
        amount   = row["amount"],
        old_bal  = row["oldbalanceOrg"],
        new_bal  = row["newbalanceOrig"],
        country  = row["country"],
        time_desc= time_desc,
        n_tx     = n_tx,
        window   = window,
        tx_type  = tx_type,
        indicators = indicators,
    )

    # Select template set by transaction type
    if tx_type == "TRANSFER":
        template = random.choice(TRANSFER_TEMPLATES)
    elif tx_type == "CASH_OUT":
        template = random.choice(CASH_OUT_TEMPLATES)
    else:
        template = random.choice(DEFAULT_TEMPLATES)

    return template.format(**params)


def generate_sar_narratives(
    scored_path=None,
    output_path=None,
    risk_threshold=None,
    max_narratives=None,
):
    """
    Load scored transactions, filter to HIGH risk, generate SAR narratives.

    Only HIGH-risk transactions get narratives — this mirrors real workflows
    where analysts write SAR drafts only for cases that pass initial triage.
    If more than max_narratives qualify, take the top-scoring ones (most
    anomalous first) to prioritize analyst review time.

    Args:
        scored_path:    Path to scored_transactions.csv from anomaly_detection.py.
        output_path:    Where to write the output CSV with narratives added.
        risk_threshold: Risk tier to generate narratives for (default "HIGH").
        max_narratives: Cap on narratives to generate (controls GLiNER runtime).

    Returns:
        pd.DataFrame: Flagged transactions with sar_narrative and sar_id columns.
    """
    scored_path = scored_path or config.SCORED_CSV
    output_path = output_path or config.SAR_NARRATIVES_CSV
    risk_threshold = risk_threshold or config.SAR_RISK_THRESHOLD
    max_narratives = max_narratives if max_narratives is not None else config.SAR_MAX_NARRATIVES

    df = pd.read_csv(scored_path)

    # All HIGH-tier transactions get narratives (tier aligns with risk_score thresholds)
    flagged = df[df["risk_tier"] == risk_threshold].copy()

    # If more transactions qualify than the cap, keep the most anomalous ones
    if len(flagged) > max_narratives:
        flagged = flagged.nlargest(max_narratives, "risk_score")

    print(f"Generating SAR narratives for {len(flagged)} {risk_threshold}-risk transactions...")

    # Apply generate_narrative row-by-row via pandas apply
    flagged["sar_narrative"] = flagged.apply(generate_narrative, axis=1)

    # Assign sequential SAR IDs for reference in the risk register and dashboard
    flagged["sar_id"] = [f"SAR-{i+1:05d}" for i in range(len(flagged))]

    config.ensure_dirs()
    flagged.to_csv(output_path, index=False)
    print(f"SAR narratives saved to {output_path}")

    # Print one example so the operator can visually verify narrative quality
    print("\nSample narrative:")
    print("-" * 60)
    print(flagged["sar_narrative"].iloc[0])
    print("-" * 60)

    return flagged


if __name__ == "__main__":
    generate_sar_narratives()
