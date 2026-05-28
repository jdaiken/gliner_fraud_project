"""Dashboard tabs: SAR narratives, exports, risk register."""

from __future__ import annotations

import time

import pandas as pd
import plotly.express as px
import streamlit as st

import config
from dashboard_tables import interactive_table, label_dataframe
from dashboard_theme import INTRAFI_BLUE, INTRAFI_CORAL, apply_plotly_theme, tier_color_discrete
from sar_narrative_ui import (
    chart_topic_distribution,
    chart_word_treemap,
    filter_narratives_df,
    render_narrative_previews,
)
from sar_topic_modeling import (
    corpus_word_weights,
    fit_sar_topics,
    persist_topic_outputs,
    suggest_topic_count,
)

SS_STOP_WORDS = "sar_stop_words"
SS_Z = "sar_z_threshold"
SS_N_TOPICS = "sar_n_topics"
SS_SEARCH = "sar_search"
SS_LAST_CLICK = "sar_treemap_last_click"
SS_AUTO_TOPICS = "sar_auto_topic_count"


def _init_sar_session() -> None:
    if SS_STOP_WORDS not in st.session_state:
        st.session_state[SS_STOP_WORDS] = []
    if SS_Z not in st.session_state:
        st.session_state[SS_Z] = 1.0
    if SS_N_TOPICS not in st.session_state:
        st.session_state[SS_N_TOPICS] = 5


def _parse_stop_input(raw: str) -> list[str]:
    if not raw:
        return []
    return [w.strip().lower() for w in raw.replace(";", ",").split(",") if w.strip()]


def _merge_stop_words(*sources: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for src in sources:
        for w in src:
            w = w.strip().lower()
            if w and w not in seen:
                seen.add(w)
                out.append(w)
    return out


def _word_from_selection_point(pt) -> str | None:
    if not isinstance(pt, dict):
        return None
    word = pt.get("label")
    custom = pt.get("customdata")
    if custom is not None:
        if isinstance(custom, (list, tuple)) and len(custom) > 0:
            word = custom[0] or word
    if word and str(word).lower() in ("narrative corpus", "corpus"):
        return None
    return str(word).lower().strip() if word else None


def _treemap_selection_to_stop_words(event, stop_key: str) -> bool:
    if event is None:
        return False
    try:
        points = event.selection.points  # type: ignore[attr-defined]
    except Exception:
        return False

    added = False
    now = time.time()
    for pt in points:
        w = _word_from_selection_point(pt)
        if not w or len(w) < 2:
            continue
        last = st.session_state.get(SS_LAST_CLICK, {})
        if last.get("word") == w and (now - float(last.get("t", 0))) < 0.55:
            if w not in st.session_state[stop_key]:
                st.session_state[stop_key].append(w)
                added = True
            st.session_state[SS_LAST_CLICK] = {}
        else:
            st.session_state[SS_LAST_CLICK] = {"word": w, "t": now}
    return added


def _render_topic_explorer(working: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    _init_sar_session()
    stops = list(st.session_state[SS_STOP_WORDS])
    texts = working["sar_narrative"].fillna("").astype(str).tolist() if "sar_narrative" in working.columns else []

    st.markdown("##### Topic model and word tree")
    st.caption(
        "Tune the z-score to keep stronger terms, set topic count (or use the suggestion), "
        "and double-click a word in the tree to add it as a stop word. Results update immediately."
    )

    c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1])
    with c1:
        z_val = st.slider(
            "Term z-score threshold",
            min_value=0.0,
            max_value=3.0,
            value=float(st.session_state[SS_Z]),
            step=0.1,
            key="sar_z_slider",
        )
        st.session_state[SS_Z] = z_val
    suggested, n_sig = suggest_topic_count(texts, stops, z_threshold=z_val)
    with c2:
        st.metric("Terms above z", n_sig)
        st.caption(f"Suggested topics: **{suggested}**")
    with c3:
        auto = st.checkbox(
            "Auto-set topic count from z-score",
            value=st.session_state.get(SS_AUTO_TOPICS, True),
            key="sar_auto_topics_cb",
        )
        st.session_state[SS_AUTO_TOPICS] = auto
        default_n = suggested if auto else int(st.session_state.get(SS_N_TOPICS, suggested))
        n_topics = st.number_input(
            "Number of topics",
            min_value=1,
            max_value=min(15, max(1, len(working))),
            value=min(default_n, max(1, len(working))),
            step=1,
            key="sar_n_topics_input",
        )
        st.session_state[SS_N_TOPICS] = int(n_topics)
    with c4:
        if st.button("Apply suggested topic count", width="stretch"):
            st.session_state[SS_N_TOPICS] = suggested
            st.rerun()

    new_stops = _parse_stop_input(
        st.text_input("Add stop words (comma-separated)", key="sar_stop_add")
    )
    stops = _merge_stop_words(stops, new_stops)
    st.session_state[SS_STOP_WORDS] = stops

    chip_options = sorted(set(stops))
    if chip_options:
        edited = st.multiselect(
            "Active stop words",
            options=chip_options,
            default=chip_options,
            key="sar_stop_chips",
        )
        st.session_state[SS_STOP_WORDS] = edited
    else:
        edited = []

    word_df = corpus_word_weights(texts, edited, z_threshold=z_val)
    fig_tree = chart_word_treemap(word_df)
    if fig_tree is not None:
        try:
            event = st.plotly_chart(
                fig_tree,
                width="stretch",
                on_select="rerun",
                selection_mode="points",
                key="sar_word_treemap",
            )
            if _treemap_selection_to_stop_words(event, SS_STOP_WORDS):
                st.rerun()
        except TypeError:
            st.plotly_chart(fig_tree, width="stretch", key="sar_word_treemap_fb")
            pick = st.selectbox("Add stop word", [""] + word_df["word"].tolist()[:30], key="sar_stop_pick")
            if pick and st.button("Add stop word"):
                if pick not in st.session_state[SS_STOP_WORDS]:
                    st.session_state[SS_STOP_WORDS].append(pick)
                    st.rerun()

    n_use = int(st.session_state[SS_N_TOPICS])
    try:
        topics_df, assigns_df, _ = fit_sar_topics(
            working,
            n_topics=n_use,
            extra_stop_words=edited,
            z_threshold=z_val,
        )
    except Exception as exc:
        st.warning(
            "Topic model could not run with the current settings. "
            "Try lowering the z-score threshold or reducing stop words. "
            "Narrative previews below are still available."
        )
        st.caption(f"Detail: {exc}")
        return pd.DataFrame(), pd.DataFrame()

    if not topics_df.empty:
        fig_topic = chart_topic_distribution(topics_df)
        if fig_topic:
            st.plotly_chart(fig_topic, width="stretch")
        interactive_table(
            topics_df,
            key_prefix="sar_topics",
            title="Topic summary",
            help_text="Themes discovered in the narrative corpus after stop words and z-score filtering.",
            tier_column=None,
            default_sort="document_count",
        )

    if st.button("Save topic model for Excel workpaper", type="primary", width="stretch"):
        persist_topic_outputs(
            topics_df, assigns_df, word_df,
            z_threshold=z_val, n_topics=n_use, stop_words=edited,
        )
        st.success("Topic outputs saved. Regenerate the workpaper on the Exports tab to include them.")
    else:
        st.caption("Topic charts update live. Click **Save topic model** when settings are final for the Excel workpaper.")

    return topics_df, assigns_df


def render_sar_narratives(narratives: pd.DataFrame | None) -> None:
    if narratives is None:
        st.info("Run `python sar_narrative_generator.py` or the full pipeline to create narratives.")
        return

    _init_sar_session()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("SAR records", f"{len(narratives):,}")
    if "risk_tier" in narratives.columns:
        c2.metric("HIGH tier", f"{(narratives['risk_tier'] == 'HIGH').sum():,}")
    if "amount" in narratives.columns:
        c3.metric("Total flagged amount", f"${narratives['amount'].sum():,.0f}")
    if "risk_score" in narratives.columns:
        c4.metric("Avg risk score", f"{narratives['risk_score'].mean():.1f}")

    search_query = st.text_input(
        "Search narratives",
        value=st.session_state.get(SS_SEARCH, ""),
        placeholder="Text, SAR ID, country, or type…",
        key="sar_search_box",
    )
    st.session_state[SS_SEARCH] = search_query
    working = filter_narratives_df(narratives, search_query)
    if working.empty:
        st.warning("No narratives match your search.")
        return
    if search_query:
        st.caption(f"**{len(working):,}** narratives in scope for topic model and previews.")

    topics_df, assigns_df = _render_topic_explorer(working)

    preview_df = working
    if not assigns_df.empty and "sar_id" in working.columns and "sar_id" in assigns_df.columns:
        preview_df = working.merge(
            assigns_df[["sar_id", "topic_label", "topic_top_terms"]],
            on="sar_id",
            how="left",
        )

    render_narrative_previews(
        preview_df, n=5, search_query=search_query, expanded_all=True, max_show=20,
    )


def render_risk_register(register: pd.DataFrame) -> None:
    from dashboard_risk_register import render_risk_register as _render
    _render(register)


def render_exports(scored: pd.DataFrame, profit_summary: pd.DataFrame | None) -> None:
    from dashboard_exports import (
        export_risk_assessment_html,
        export_risk_assessment_pdf,
        export_workpaper_bytes,
    )

    st.markdown("##### Excel workpaper")
    regen = st.checkbox("Regenerate workpaper from latest pipeline outputs", value=True)
    if st.button("Prepare workpaper", width="stretch"):
        with st.spinner("Building Excel workpaper…"):
            try:
                data, fname = export_workpaper_bytes(regenerate=regen)
                st.session_state["export_workpaper"] = (data, fname)
                st.success("Workpaper ready.")
            except Exception as e:
                st.error(f"Workpaper failed: {e}")
    if st.session_state.get("export_workpaper"):
        data, fname = st.session_state["export_workpaper"]
        st.download_button(
            "Download Excel workpaper",
            data=data,
            file_name=fname,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            width="stretch",
        )
    elif config.WORKPAPER_XLSX.exists():
        st.download_button(
            "Download existing workpaper",
            data=config.WORKPAPER_XLSX.read_bytes(),
            file_name=config.WORKPAPER_XLSX.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )

    st.divider()
    st.markdown("##### Risk assessment")
    st.caption("Open **Risk assessment** in the sidebar for the interactive report. Download copies below.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Prepare risk assessment (HTML)", width="stretch"):
            with st.spinner("Building HTML…"):
                data, fname = export_risk_assessment_html(scored, profit_summary)
                st.session_state["export_brief_html"] = (data, fname)
                st.success("HTML ready.")
        if st.session_state.get("export_brief_html"):
            d, f = st.session_state["export_brief_html"]
            st.download_button("Download HTML", data=d, file_name=f, mime="text/html", width="stretch")
    with c2:
        if st.button("Prepare risk assessment (PDF)", width="stretch"):
            with st.spinner("Building PDF…"):
                data, fname = export_risk_assessment_pdf(scored, profit_summary)
                st.session_state["export_brief_pdf"] = (data, fname)
                st.success("PDF ready.")
        if st.session_state.get("export_brief_pdf"):
            d, f = st.session_state["export_brief_pdf"]
            st.download_button(
                "Download PDF", data=d, file_name=f, mime="application/pdf",
                type="primary", width="stretch",
            )
