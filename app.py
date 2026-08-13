"""Entrypoint Streamlit Cloud / local: `streamlit run app.py`."""
import streamlit as st

st.set_page_config(
    page_title="Sistema Integral de Exportación",
    page_icon="📊",
    layout="wide",
)

from ui.main import run  # noqa: E402

run()
