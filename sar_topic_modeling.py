"""
Topic modeling for SAR narrative corpus (TF-IDF + NMF, z-score term filtering).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
from sklearn.feature_extraction.text import TfidfVectorizer

import config

DEFAULT_N_TOPICS = 5
TOKEN_RE = re.compile(r"[a-z][a-z0-9]{2,}")


def _normalize_stop_words(extra: list[str] | None) -> list[str]:
    base = set(ENGLISH_STOP_WORDS)
    if extra:
        for w in extra:
            w = str(w).strip().lower()
            if w:
                base.add(w)
    return sorted(base)


def _tokenize_corpus(texts: list[str], stop_words: set[str]) -> list[list[str]]:
    tokens_per_doc = []
    for text in texts:
        toks = [
            t for t in TOKEN_RE.findall(str(text).lower())
            if t not in stop_words and len(t) > 2
        ]
        tokens_per_doc.append(toks)
    return tokens_per_doc


def corpus_word_weights(
    texts: list[str],
    extra_stop_words: list[str] | None = None,
    z_threshold: float = 0.0,
    top_n: int = 80,
) -> pd.DataFrame:
    """
    Aggregate token counts across narratives and rank by z-score of log-count.
    """
    stop = set(_normalize_stop_words(extra_stop_words))
    counts: dict[str, int] = {}
    for doc_tokens in _tokenize_corpus(texts, stop):
        for tok in doc_tokens:
            counts[tok] = counts.get(tok, 0) + 1

    if not counts:
        return pd.DataFrame(columns=["word", "count", "z_score", "weight"])

    words = list(counts.keys())
    vals = np.array([counts[w] for w in words], dtype=float)
    log_vals = np.log1p(vals)
    mu, sigma = log_vals.mean(), log_vals.std()
    if sigma < 1e-9:
        z = np.zeros_like(log_vals)
    else:
        z = (log_vals - mu) / sigma

    df = pd.DataFrame({
        "word": words,
        "count": vals.astype(int),
        "z_score": np.round(z, 3),
        "weight": vals,
    })
    if z_threshold > 0:
        df = df[df["z_score"] >= z_threshold]
    return df.sort_values("weight", ascending=False).head(top_n).reset_index(drop=True)


def suggest_topic_count(
    texts: list[str],
    extra_stop_words: list[str] | None = None,
    z_threshold: float = 1.0,
) -> tuple[int, int]:
    """Suggest topic count from count of terms above z-threshold."""
    weights = corpus_word_weights(texts, extra_stop_words, z_threshold=z_threshold, top_n=500)
    n_sig = len(weights)
    if n_sig <= 2:
        return max(1, min(2, len(texts))), n_sig
    suggested = int(np.clip(round(np.sqrt(n_sig) / 1.4), 2, min(10, max(2, n_sig // 2))))
    return min(suggested, len(texts)), n_sig


def _topic_labels(top_terms_per_topic: list[list[str]]) -> list[str]:
    labels = []
    for terms in top_terms_per_topic:
        label = ", ".join(terms[:3]) if terms else "General"
        if len(label) > 48:
            label = label[:45] + "..."
        labels.append(label)
    return labels


def _feature_max_vector(X) -> np.ndarray:
    """Per-feature max TF-IDF as a 1-D float64 vector (scipy sparse .max can return a matrix)."""
    try:
        from scipy.sparse import spmatrix
    except ImportError:
        spmatrix = ()  # type: ignore[misc, assignment]

    if isinstance(X, spmatrix):
        row = X.max(axis=0)
        if hasattr(row, "toarray"):
            return np.asarray(row.toarray(), dtype=np.float64).ravel()
        if hasattr(row, "todense"):
            return np.asarray(row.todense(), dtype=np.float64).ravel()

    return np.asarray(X.max(axis=0), dtype=np.float64).ravel()


def _filter_tfidf_by_z(X, feature_names: np.ndarray, z_threshold: float):
    if z_threshold <= 0 or X.shape[1] == 0:
        return X, feature_names

    max_tfidf = _feature_max_vector(X)
    mu, sigma = max_tfidf.mean(), max_tfidf.std()
    if sigma < 1e-9:
        mask = np.ones(len(feature_names), dtype=bool)
    else:
        z = (max_tfidf - mu) / sigma
        mask = z >= z_threshold

    if mask.sum() < 3:
        return X, feature_names

    col_idx = np.where(mask)[0]
    from scipy.sparse import csr_matrix
    return csr_matrix(X[:, col_idx]), feature_names[col_idx]


def fit_sar_topics(
    narratives: pd.DataFrame,
    n_topics: int = DEFAULT_N_TOPICS,
    text_col: str = "sar_narrative",
    extra_stop_words: list[str] | None = None,
    z_threshold: float = 0.0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Fit NMF topics on SAR narratives.

    Returns:
        topics_df, assignments_df, word_weights_df
    """
    if text_col not in narratives.columns or narratives.empty:
        empty = pd.DataFrame()
        return empty, empty, empty

    texts = narratives[text_col].fillna("").astype(str).tolist()
    n_docs = len(texts)
    n_topics = max(1, min(n_topics, n_docs))

    stop_list = _normalize_stop_words(extra_stop_words)
    word_weights_df = corpus_word_weights(texts, extra_stop_words, z_threshold=z_threshold)

    min_df = 1 if n_docs < 8 else 2
    vectorizer = TfidfVectorizer(
        max_df=0.9,
        min_df=min_df,
        stop_words=stop_list,
        ngram_range=(1, 2),
        max_features=500,
    )
    X = vectorizer.fit_transform(texts)
    if X.shape[1] == 0:
        return pd.DataFrame(), pd.DataFrame(), word_weights_df

    terms = vectorizer.get_feature_names_out()
    X, terms = _filter_tfidf_by_z(X, terms, z_threshold)

    if X.shape[1] == 0:
        return pd.DataFrame(), pd.DataFrame(), word_weights_df

    n_comp = min(n_topics, X.shape[1], n_docs)
    model = NMF(n_components=n_comp, random_state=config.RANDOM_SEED, max_iter=400)
    doc_topic = model.fit_transform(X)
    components = model.components_

    top_terms_per_topic: list[list[str]] = []
    for row in components:
        idx = np.argsort(row)[::-1][:8]
        top_terms_per_topic.append([terms[i] for i in idx if row[i] > 0])

    labels = _topic_labels(top_terms_per_topic)
    dominant = doc_topic.argmax(axis=1)
    strength = doc_topic.max(axis=1)

    assignments = narratives.copy()
    assignments["dominant_topic"] = dominant
    assignments["topic_label"] = [labels[i] for i in dominant]
    assignments["topic_score"] = np.round(strength, 4)
    assignments["topic_top_terms"] = [
        ", ".join(top_terms_per_topic[i]) for i in dominant
    ]

    keep = [
        c for c in [
            "sar_id", "transaction_id", "risk_score", "risk_tier", "type", "amount", "country",
        ]
        if c in assignments.columns
    ]
    assignments_df = assignments[keep + ["dominant_topic", "topic_label", "topic_score", "topic_top_terms"]]

    counts = pd.Series(dominant).value_counts().sort_index()
    topics_rows = []
    for tid in range(n_comp):
        topics_rows.append({
            "topic_id": tid,
            "topic_label": labels[tid],
            "top_terms": ", ".join(top_terms_per_topic[tid]),
            "document_count": int(counts.get(tid, 0)),
            "share_pct": round(100 * counts.get(tid, 0) / n_docs, 1),
        })
    topics_df = pd.DataFrame(topics_rows)
    topics_df["z_threshold"] = z_threshold
    topics_df["n_topics"] = n_comp
    topics_df["stop_words"] = "|".join(extra_stop_words or [])

    return topics_df, assignments_df, word_weights_df


def persist_topic_outputs(
    topics_df: pd.DataFrame,
    assignments_df: pd.DataFrame,
    word_weights_df: pd.DataFrame,
    *,
    z_threshold: float,
    n_topics: int,
    stop_words: list[str],
) -> None:
    """Write topic artifacts for dashboard and Excel workpaper."""
    config.ensure_dirs()
    meta = {
        "z_threshold": z_threshold,
        "n_topics": n_topics,
        "stop_words": stop_words,
    }
    config.SAR_TOPIC_META_JSON.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    if not topics_df.empty:
        out_topics = topics_df.copy()
        for k, v in meta.items():
            if k not in out_topics.columns:
                out_topics[k] = v
        out_topics.to_csv(config.SAR_TOPICS_CSV, index=False)
    if not assignments_df.empty:
        assignments_df.to_csv(config.SAR_TOPIC_ASSIGNMENTS_CSV, index=False)
    if word_weights_df is not None and not word_weights_df.empty:
        out_w = word_weights_df.copy()
        out_w["z_threshold"] = z_threshold
        out_w.to_csv(config.SAR_WORD_FREQ_CSV, index=False)


def run_sar_topic_modeling(
    narratives_path: Path | None = None,
    topics_path: Path | None = None,
    assignments_path: Path | None = None,
    n_topics: int = DEFAULT_N_TOPICS,
    z_threshold: float = 0.0,
    extra_stop_words: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load narratives, fit topics, save CSVs."""
    narratives_path = narratives_path or config.SAR_NARRATIVES_CSV

    if not narratives_path.exists():
        raise FileNotFoundError(f"SAR narratives not found at {narratives_path}")

    narratives = pd.read_csv(narratives_path)
    topics_df, assignments_df, word_weights_df = fit_sar_topics(
        narratives,
        n_topics=n_topics,
        extra_stop_words=extra_stop_words,
        z_threshold=z_threshold,
    )
    persist_topic_outputs(
        topics_df,
        assignments_df,
        word_weights_df,
        z_threshold=z_threshold,
        n_topics=n_topics,
        stop_words=extra_stop_words or [],
    )
    return topics_df, assignments_df


if __name__ == "__main__":
    topics, assigns = run_sar_topic_modeling()
    print(f"Topics: {len(topics)} | Assignments: {len(assigns)}")
