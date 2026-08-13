"""Estilos de página / tipografía de pantallas."""
import streamlit as st


def pagina_ecc_style(titulo: str, descripcion: str = ""):
    """Título limpio; descripción corta opcional (máx. una línea)."""
    st.title(titulo)
    if descripcion:
        st.caption(descripcion)
