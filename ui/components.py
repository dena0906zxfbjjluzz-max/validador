"""Componentes UI reutilizables."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import funciones
from ui.style import pagina_ecc_style


def render_modulo_alertas_tendencias(
    df_packing=None,
    cols_mapa=None,
    peso_min_caja: float = 4.0,
    max_merma_permitida: float = 5.0,
    key_prefix: str = "m7",
):
    """Módulo 7 — Alertas y tendencias (frío SQLite + packing cargado)."""
    with st.container():
        informe = funciones.consolidar_inteligencia_planta(
            df_packing=df_packing,
            cols_mapa=cols_mapa,
            peso_min_caja=peso_min_caja,
            max_merma_permitida=max_merma_permitida,
        )
        cont = informe.get("contadores") or {}
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Críticas", cont.get("criticas", 0))
        with c2:
            st.metric("Advertencias", cont.get("advertencias", 0))
        with c3:
            frio = informe.get("frio") or {}
            st.metric("Lecturas frío", frio.get("total_lecturas", 0))
        with c4:
            st.metric("% ruptura frío", f"{frio.get('pct_ruptura', 0)}%")

        veredicto = informe.get("veredicto")
        if veredicto == "ACCION_REQUERIDA":
            st.error(veredicto)
        elif veredicto == "VIGILANCIA":
            st.warning(veredicto)
        else:
            st.success(veredicto)

        alertas = [a for a in (informe.get("alertas") or []) if a.get("severidad") != "info"]
        if alertas:
            with st.expander(f"Alertas ({len(alertas)})", expanded=False):
                for a in alertas[:12]:
                    st.write(f"{a.get('titulo')} — {a.get('detalle')}")

        por_cam = (informe.get("frio") or {}).get("por_camara") or []
        packing = informe.get("packing") or {}
        with st.expander("Detalle frío / packing", expanded=False):
            if por_cam:
                st.dataframe(pd.DataFrame(por_cam), width="stretch", hide_index=True)
            prod = packing.get("por_productor") or []
            if prod:
                st.dataframe(pd.DataFrame(prod), width="stretch", hide_index=True)
            serie = (informe.get("frio") or {}).get("serie_chart")
            if isinstance(serie, pd.DataFrame) and not serie.empty and "camara" in serie.columns:
                cams = sorted(serie["camara"].astype(str).unique().tolist())
                cam_sel = st.selectbox("Cámara", options=cams, key=f"{key_prefix}_cam_chart")
                sub = serie[serie["camara"].astype(str) == str(cam_sel)]
                if not sub.empty and "etiqueta" in sub.columns:
                    st.line_chart(sub.set_index("etiqueta")[["temperatura"]])

