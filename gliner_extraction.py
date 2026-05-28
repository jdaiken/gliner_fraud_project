"""
gliner_extraction.py
--------------------
Extracts structured risk entities from SAR narratives using GLiNER,
producing a populated risk register CSV ready for analyst review.

WHY GLINER?
GLiNER (Generalist and Lightweight Named Entity Recognition) is a zero-shot
NLP model that can identify any entity type from unstructured text using only
a natural language label — no training data or fine-tuning required. This
makes it well-suited to financial risk use cases where:

  - Entity types change frequently (new risk frameworks, new taxonomies)
  - Labeled training data is scarce or confidential
  - Local CPU inference is required (data privacy — no API calls to third parties)
  - A single lightweight model replaces multiple specialized extractors

Architecture: GLiNER uses a bidirectional transformer encoder (DeBERTa-based)
with a span prediction head. Given a text and a list of entity labels, it
predicts which text spans correspond to which labels with a confidence score.

MODEL SELECTION:
  urchade/gliner_medium-v2.1 — good balance of speed and accuracy, ~300MB
  urchade/gliner_large-v2.1  — higher accuracy, slower, ~700MB
  urchade/gliner_small-v2.1  — fastest, smaller, lower accuracy

ENTITY LABELS:
Labels are natural language strings — they are not a fixed taxonomy.
Change them to match your risk framework without any retraining.
"""

import pandas as pd
from gliner import GLiNER

import config


# ── Entity labels ─────────────────────────────────────────────────────────────
# These are the entity types GLiNER will look for in each SAR narrative.
# They are natural language strings, not codes — the model uses semantic
# similarity to match spans in the text to these label descriptions.
# Add, remove, or rename labels to match your organization's risk taxonomy.
ENTITY_LABELS = [
    "account identifier",       # account numbers, customer IDs (e.g., "C7162857")
    "transaction amount",       # dollar values (e.g., "$19,553.53")
    "transaction type",         # TRANSFER, CASH_OUT, PAYMENT, etc.
    "country or jurisdiction",  # geographic risk indicators (e.g., "NG", "Ukraine")
    "time or hour",             # time-of-activity flags (e.g., "03:00 (late night)")
    "risk indicator",           # named risk factors from the indicator library
    "balance amount",           # account balance values
    "report identifier",        # SAR IDs (e.g., "SAR-00001")
]


def load_model(model_name=None):
    """
    Load the GLiNER model from Hugging Face Hub.

    First call downloads the model weights (~300MB) and caches them locally
    in ~/.cache/huggingface/. Subsequent calls load from cache instantly.
    No API key or internet connection required after first download.

    Args:
        model_name: Hugging Face model identifier. Options:
                    urchade/gliner_medium-v2.1 (default — balanced)
                    urchade/gliner_large-v2.1  (higher accuracy, slower)
                    urchade/gliner_small-v2.1  (fastest, lower accuracy)

    Returns:
        GLiNER: Loaded model ready for inference.
    """
    model_name = model_name or config.GLINER_MODEL
    print(f"Loading GLiNER model: {model_name}")
    model = GLiNER.from_pretrained(model_name)
    print("Model loaded.")
    return model


def extract_entities(model, text, threshold=None):
    """
    Run GLiNER entity extraction on a single narrative string.

    The threshold controls confidence cutoff — lower values return more
    entities with lower confidence; higher values return fewer but more
    precise extractions. 0.4 works well for financial text; tune up to
    0.5–0.6 if you see too many false positives.

    Args:
        model:     Loaded GLiNER model instance.
        text:      SAR narrative string to extract entities from.
        threshold: Minimum confidence score for an entity to be returned.

    Returns:
        list: Each element is a dict with keys:
              {"text": str, "label": str, "score": float}
    """
    threshold = threshold if threshold is not None else config.GLINER_THRESHOLD
    entities = model.predict_entities(text, ENTITY_LABELS, threshold=threshold)
    return entities


def _amount_in_extractions(amount, extracted_amounts, narrative):
    """Check whether structured amount appears in GLiNER output or narrative."""
    if pd.isna(amount):
        return False
    amount_str = f"{float(amount):,.2f}"
    amount_plain = str(int(amount)) if float(amount) == int(amount) else str(amount)
    haystack = f"{extracted_amounts} {narrative}".replace(",", "")
    return amount_str.replace(",", "") in haystack or amount_plain in haystack


def _country_in_extractions(country, extracted_countries, narrative):
    """Check whether structured country appears in GLiNER output or narrative."""
    if pd.isna(country) or not str(country).strip():
        return False
    c = str(country).strip()
    haystack = f"{extracted_countries} {narrative}"
    return c in haystack


def entities_to_dict(entities):
    """
    Flatten GLiNER's entity list into a structured dict for the risk register.

    GLiNER can return multiple entities of the same type (e.g., two account
    IDs in one narrative). This function deduplicates and joins them with ' | '
    so each output column contains a clean, readable string.

    The label_map below translates GLiNER's natural language labels to
    snake_case column names for the output DataFrame. Update the map if
    you change ENTITY_LABELS above.

    Args:
        entities: List of entity dicts from extract_entities().

    Returns:
        dict: Column-name → extracted value string mapping.
              Empty string "" for any label with no extractions.
    """
    # Initialize all output fields as empty lists
    fields = {
        "extracted_accounts":     [],
        "extracted_amounts":      [],
        "extracted_tx_types":     [],
        "extracted_countries":    [],
        "extracted_time_flags":   [],
        "extracted_risk_factors": [],
        "extracted_balances":     [],
    }

    # Map GLiNER label strings to output column names
    label_map = {
        "account identifier":      "extracted_accounts",
        "transaction amount":      "extracted_amounts",
        "transaction type":        "extracted_tx_types",
        "country or jurisdiction": "extracted_countries",
        "time or hour":            "extracted_time_flags",
        "risk indicator":          "extracted_risk_factors",
        "balance amount":          "extracted_balances",
        # Note: "report identifier" is intentionally not stored in a separate
        # column — it's carried through from the sar_id field directly.
    }

    # Accumulate all extracted spans by label
    for ent in entities:
        label = ent["label"]
        text  = ent["text"]
        if label in label_map:
            fields[label_map[label]].append(text)

    # Deduplicate (same span extracted twice) and join with pipe separator.
    # Empty lists become empty strings — preserves column structure in the CSV.
    return {
        k: " | ".join(sorted(set(v))) if v else ""
        for k, v in fields.items()
    }


def run_gliner_extraction(
    narratives_path=None,
    output_path=None,
    sample_size=None,
):
    """
    Run GLiNER extraction over all SAR narratives and write a risk register CSV.

    Iterates through each narrative row, extracts entities, and builds a
    structured output record that combines:
      - Key transaction metadata (ID, risk score, tier, type, amount, country)
      - GLiNER-extracted entities (accounts, amounts, countries, risk factors)
      - The original SAR narrative (for analyst review and audit trail)

    This output is the risk register — structured, searchable, and ready for
    analyst review without requiring manual SAR data entry.

    Args:
        narratives_path: Path to SAR narratives CSV from sar_narrative_generator.py.
        output_path:     Where to write the final risk register CSV.
        sample_size:     If set, only process the first N narratives.
                         Useful for quick testing before a full run.

    Returns:
        pd.DataFrame: Completed risk register with all structured fields.
    """
    narratives_path = narratives_path or config.SAR_NARRATIVES_CSV
    output_path = output_path or config.RISK_REGISTER_CSV

    df = pd.read_csv(narratives_path)

    # Optional sample mode for fast iteration during development
    if sample_size:
        df = df.head(sample_size)
        print(f"Running on sample of {sample_size} narratives...")
    else:
        print(f"Running GLiNER on {len(df)} narratives...")

    # Load model once outside the loop — reloading per row would be ~100x slower
    model = load_model()

    results = []
    for i, row in df.iterrows():
        # Progress indicator — GLiNER runs at ~1–3 seconds per narrative on CPU
        if (i + 1) % 10 == 0:
            print(f"  Processing {i+1}/{len(df)}...")

        # Extract entities from the SAR narrative text
        entities    = extract_entities(model, row["sar_narrative"])
        entity_dict = entities_to_dict(entities)

        # Build the output record: metadata + extracted entities + narrative
        extracted_amounts = entity_dict.get("extracted_amounts", "")
        extracted_countries = entity_dict.get("extracted_countries", "")
        narrative = row["sar_narrative"]

        result = {
            "sar_id":           row.get("sar_id", f"SAR-{i:05d}"),
            "transaction_id":   row.get("transaction_id", ""),
            "risk_score":       row.get("risk_score", ""),
            "risk_tier":        row.get("risk_tier", ""),
            "transaction_type": row.get("type", ""),
            "amount":           row.get("amount", ""),
            "country":          row.get("country", ""),
            "is_labeled_fraud": row.get("isFraud", ""),
            "sar_narrative":    narrative,
            **entity_dict,
            "amount_reconciled": _amount_in_extractions(
                row.get("amount"), extracted_amounts, narrative
            ),
            "country_reconciled": _country_in_extractions(
                row.get("country"), extracted_countries, narrative
            ),
        }
        results.append(result)

    register = pd.DataFrame(results)

    config.ensure_dirs()
    register.to_csv(output_path, index=False)

    if "amount_reconciled" in register.columns:
        amt_ok = register["amount_reconciled"].mean() * 100
        cty_ok = register["country_reconciled"].mean() * 100
        print(f"  Extraction reconciliation: amount {amt_ok:.0f}% | country {cty_ok:.0f}%")
    print(f"\nRisk register saved to {output_path}")
    print(f"Columns: {list(register.columns)}")

    # Print a quick sample so the operator can sanity-check extraction quality
    print(f"\nSample extraction:")
    print(register[[
        "sar_id", "risk_score", "extracted_accounts",
        "extracted_amounts", "extracted_countries"
    ]].head(3).to_string())

    return register


if __name__ == "__main__":
    run_gliner_extraction(sample_size=config.GLINER_SAMPLE_SIZE)
