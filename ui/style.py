"""Cabeceras y tipografía de pantallas (sistema Validador)."""
from __future__ import annotations

import html

import streamlit as st


def pagina_ecc_style(
    titulo: str,
    descripcion: str = "",
    *,
    eyebrow: str = "Validador",
    meta: str = "",
):
    """
    Cabecera de pantalla tipo producto: marca + título + una línea de apoyo.
    """
    t = html.escape(str(titulo or "").strip() or "Planta")
    d = html.escape(str(descripcion or "").strip())
    eye = html.escape(str(eyebrow or "Validador").strip())
    m = html.escape(str(meta or "").strip())

    meta_html = f'<span class="vx-page-meta">{m}</span>' if m else ""
    desc_html = f'<p class="vx-page-desc">{d}</p>' if d else ""

    st.markdown(
        f"""
        <header class="vx-page-header">
          <div class="vx-page-brand">
            <span class="vx-page-mark" aria-hidden="true"></span>
            <span class="vx-page-eyebrow">{eye}</span>
            {meta_html}
          </div>
          <h1 class="vx-page-title">{t}</h1>
          {desc_html}
        </header>
        """,
        unsafe_allow_html=True,
    )


def sidebar_brand(planta: str = "", usuario: str = "", rol: str = "") -> None:
    """Marca compacta en la barra lateral."""
    p = html.escape((planta or "Planta").strip())
    u = html.escape((usuario or "").strip())
    r = html.escape((rol or "").strip())
    sub = " · ".join(x for x in (u, r) if x)
    sub_html = f'<p class="vx-side-sub">{html.escape(sub)}</p>' if sub else ""
    st.sidebar.markdown(
        f"""
        <div class="vx-side-brand">
          <div class="vx-side-mark" aria-hidden="true"></div>
          <div>
            <p class="vx-side-product">Validador</p>
            <p class="vx-side-plant">{p}</p>
            {sub_html}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
