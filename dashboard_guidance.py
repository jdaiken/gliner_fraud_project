"""Tab-level guidance copy for the dashboard."""

from __future__ import annotations

import streamlit as st

from dashboard_content import TAB_INTROS


def render_tab_intro(page: str) -> None:
    """Show a short analyst paragraph for the active sidebar section."""
    text = TAB_INTROS.get(page)
    if text:
        st.markdown(f'<p class="tab-intro">{text}</p>', unsafe_allow_html=True)
