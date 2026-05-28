"""
gliner_extraction.py
--------------------
Extracts structured risk entities from SAR narratives using GLiNER,
producing a populated risk register CSV ready for analyst review.

When Hugging Face is unreachable, uses a regex fallback so the pipeline
can still finish (set GLINER_ALLOW_FALLBACK=False to require GLiNER).
"""

from __future__ import annotations

import os
import re
from typing import Any

import pandas as pd

import config

# Lazy import — GLiNER pulls torch/transformers and may hit the network on load.
GLiNER = None

# ── Entity labels ─────────────────────────────────────────────────────────────
ENTITY_LABELS = [
    "account identifier",
    "transaction amount",
    "transaction type",
    "country or jurisdiction",
    "time or hour",
    "risk indicator",
    "balance amount",
    "report identifier",
]

_ACCOUNT_RE = re.compile(
    r"(?:account|beneficiary account|agent account|via)\s+([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(r"\$[\d,]+(?:\.\d{2})?")
_COUNTRY_RE = re.compile(
    r"(?:from|originated from|Geographic origin|Country of origin|origin)\s*:?\s*([A-Z]{2})\b",
    re.IGNORECASE,
)
_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b|late night|between\s+00:00")
_TX_TYPES = ("TRANSFER", "CASH_OUT", "PAYMENT", "DEBIT", "CASH_IN")


def _import_gliner():
    global GLiNER
    if GLiNER is None:
        from gliner import GLiNER as _GLiNER
        GLiNER = _GLiNER
    return GLiNER


def model_is_cached(model_name: str | None = None) -> bool:
    """True if model weights appear in the local Hugging Face cache."""
    model_name = model_name or config.GLINER_MODEL
    try:
        from huggingface_hub import try_to_load_from_cache
        for filename in ("config.json", "model.safetensors", "pytorch_model.bin"):
            if try_to_load_from_cache(model_name, filename) is not None:
                return True
    except Exception:
        pass
    return False


def load_model(model_name=None, *, local_only: bool | None = None):
    """
    Load GLiNER from cache when possible; otherwise download from Hugging Face.

    Raises on failure unless caller handles it and uses fallback extraction.
    """
    model_name = model_name or config.GLINER_MODEL
    gliner_cls = _import_gliner()

    if local_only is None:
        local_only = config.GLINER_PREFER_LOCAL_CACHE

    attempts: list[str] = []

    if local_only:
        print(f"Loading GLiNER model (local cache only): {model_name}")
        prev_hf = os.environ.get("HF_HUB_OFFLINE")
        prev_tf = os.environ.get("TRANSFORMERS_OFFLINE")
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        try:
            model = gliner_cls.from_pretrained(model_name, local_files_only=True)
            print("Model loaded from local cache.")
            return model
        except Exception as exc:
            attempts.append(f"offline cache: {exc}")
        finally:
            for key, val in (("HF_HUB_OFFLINE", prev_hf), ("TRANSFORMERS_OFFLINE", prev_tf)):
                if val is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = val

    print(f"Loading GLiNER model: {model_name}")
    try:
        model = gliner_cls.from_pretrained(model_name)
        print("Model loaded.")
        return model
    except Exception as exc:
        attempts.append(f"download: {exc}")
        msg = (
            "Could not load GLiNER. Common causes: no internet/DNS, firewall, or model not cached yet.\n"
            f"  Model: {model_name}\n"
            "  Fix (once online): python -c \"from gliner import GLiNER; "
            f"GLiNER.from_pretrained('{model_name}')\"\n"
            "  Or set GLINER_ALLOW_FALLBACK=True to build the register with regex extraction."
        )
        if attempts:
            msg += "\n  Details: " + " | ".join(attempts)
        raise RuntimeError(msg) from exc


def extract_entities(model, text, threshold=None):
    threshold = threshold if threshold is not None else config.GLINER_THRESHOLD
    entities = model.predict_entities(text, ENTITY_LABELS, threshold=threshold)
    return entities


def fallback_extract_entities(text: str, row: pd.Series | None = None) -> list[dict[str, Any]]:
    """
    Regex-based entity extraction when GLiNER cannot load (offline / no cache).
    """
    entities: list[dict[str, Any]] = []
    if not text or not isinstance(text, str):
        return entities

    seen: set[tuple[str, str]] = set()

    def add(span: str, label: str):
        key = (label, span.strip())
        if key in seen or not span.strip():
            return
        seen.add(key)
        entities.append({"text": span.strip(), "label": label, "score": 0.5})

    for m in _ACCOUNT_RE.finditer(text):
        add(m.group(1), "account identifier")

    for m in _AMOUNT_RE.finditer(text):
        add(m.group(0), "transaction amount")

    for m in _COUNTRY_RE.finditer(text):
        add(m.group(1).upper(), "country or jurisdiction")

    for m in _TIME_RE.finditer(text):
        add(m.group(0), "time or hour")

    for tx in _TX_TYPES:
        if tx in text:
            add(tx, "transaction type")

    if "Risk indicators:" in text:
        tail = text.split("Risk indicators:")[-1].strip().rstrip(".")
        for part in tail.split(","):
            add(part.strip(), "risk indicator")

    if row is not None:
        if pd.notna(row.get("type")):
            add(str(row["type"]), "transaction type")
        if pd.notna(row.get("country")):
            add(str(row["country"]), "country or jurisdiction")
        if pd.notna(row.get("amount")):
            add(f"${float(row['amount']):,.2f}", "transaction amount")
        if pd.notna(row.get("sar_id")):
            add(str(row["sar_id"]), "report identifier")

    return entities


def _amount_in_extractions(amount, extracted_amounts, narrative):
    if pd.isna(amount):
        return False
    amount_str = f"{float(amount):,.2f}"
    amount_plain = str(int(amount)) if float(amount) == int(amount) else str(amount)
    haystack = f"{extracted_amounts} {narrative}".replace(",", "")
    return amount_str.replace(",", "") in haystack or amount_plain in haystack


def _country_in_extractions(country, extracted_countries, narrative):
    if pd.isna(country) or not str(country).strip():
        return False
    c = str(country).strip()
    haystack = f"{extracted_countries} {narrative}"
    return c in haystack


def entities_to_dict(entities):
    fields = {
        "extracted_accounts": [],
        "extracted_amounts": [],
        "extracted_tx_types": [],
        "extracted_countries": [],
        "extracted_time_flags": [],
        "extracted_risk_factors": [],
        "extracted_balances": [],
    }

    label_map = {
        "account identifier": "extracted_accounts",
        "transaction amount": "extracted_amounts",
        "transaction type": "extracted_tx_types",
        "country or jurisdiction": "extracted_countries",
        "time or hour": "extracted_time_flags",
        "risk indicator": "extracted_risk_factors",
        "balance amount": "extracted_balances",
    }

    for ent in entities:
        label = ent["label"]
        text = ent["text"]
        if label in label_map:
            fields[label_map[label]].append(text)

    return {k: " | ".join(sorted(set(v))) if v else "" for k, v in fields.items()}


def _resolve_model(allow_fallback: bool):
    """Return (model, extraction_method) or (None, 'regex_fallback')."""
    cached = model_is_cached()
    if config.GLINER_PREFER_LOCAL_CACHE and not cached:
        if allow_fallback:
            print(
                "  GLiNER model is not in the local Hugging Face cache and offline mode is enabled.\n"
                "  Using regex fallback. To use GLiNER once: connect to the internet and run:\n"
                f"    python -c \"from gliner import GLiNER; GLiNER.from_pretrained('{config.GLINER_MODEL}')\"\n"
            )
            return None, "regex_fallback"
        raise RuntimeError(
            f"GLiNER model '{config.GLINER_MODEL}' is not cached. "
            "Download it once while online, or set GLINER_ALLOW_FALLBACK=True."
        )

    try:
        return load_model(local_only=config.GLINER_PREFER_LOCAL_CACHE or cached), "gliner"
    except Exception as exc:
        if not allow_fallback:
            raise
        print(f"\n  WARNING: {exc}")
        print("  Continuing with regex fallback extraction (no GLiNER model).\n")
        return None, "regex_fallback"


def run_gliner_extraction(
    narratives_path=None,
    output_path=None,
    sample_size=None,
    allow_fallback: bool | None = None,
):
    narratives_path = narratives_path or config.SAR_NARRATIVES_CSV
    output_path = output_path or config.RISK_REGISTER_CSV
    allow_fallback = (
        config.GLINER_ALLOW_FALLBACK if allow_fallback is None else allow_fallback
    )

    df = pd.read_csv(narratives_path)

    if sample_size:
        df = df.head(sample_size)
        print(f"Running on sample of {sample_size} narratives...")
    else:
        print(f"Running GLiNER on {len(df)} narratives...")

    model, extraction_method = _resolve_model(allow_fallback)

    results = []
    for i, row in df.iterrows():
        if (i + 1) % 10 == 0:
            print(f"  Processing {i+1}/{len(df)}...")

        narrative = row["sar_narrative"]
        if model is not None:
            entities = extract_entities(model, narrative)
        else:
            entities = fallback_extract_entities(narrative, row)

        entity_dict = entities_to_dict(entities)
        extracted_amounts = entity_dict.get("extracted_amounts", "")
        extracted_countries = entity_dict.get("extracted_countries", "")

        result = {
            "sar_id": row.get("sar_id", f"SAR-{i:05d}"),
            "transaction_id": row.get("transaction_id", ""),
            "risk_score": row.get("risk_score", ""),
            "risk_tier": row.get("risk_tier", ""),
            "transaction_type": row.get("type", ""),
            "amount": row.get("amount", ""),
            "country": row.get("country", ""),
            "is_labeled_fraud": row.get("isFraud", ""),
            "extraction_method": extraction_method,
            "sar_narrative": narrative,
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
    print(f"  Extraction method: {extraction_method}")
    print(f"Columns: {list(register.columns)}")

    print(f"\nSample extraction:")
    print(register[[
        "sar_id", "risk_score", "extracted_accounts",
        "extracted_amounts", "extracted_countries", "extraction_method",
    ]].head(3).to_string())

    return register


if __name__ == "__main__":
    run_gliner_extraction(sample_size=config.GLINER_SAMPLE_SIZE)
