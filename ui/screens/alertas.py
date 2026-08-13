"""Pantalla UI."""
from __future__ import annotations

import datetime
import io

import pandas as pd
import streamlit as st

import funciones
import motor_planta
import seguridad_cortafuego as firewall
from ui.auth import purgar_frio_local_ui
from ui.style import pagina_ecc_style

from ui.components import render_modulo_alertas_tendencias


def render(*, es_supervisor: bool, peso_min_caja, max_merma_permitida):
    pagina_ecc_style("Alertas", "Frío · pesos · LMR")
    if es_supervisor:
        with st.expander("Borrar alertas de frío (SQLite local)"):
            st.caption(
                "Supabase ≠ alertas de pantalla. Esta app usa `planta_calidad_prod.db`."
            )
            if st.button("Borrar rupturas locales", key="alertas_del_rupturas"):
                r = purgar_frio_local_ui(solo_rupturas=True)
                (st.success if r.get("ok") else st.error)(r.get("mensaje"))
                if r.get("ok"):
                    st.rerun()
            if st.button("Borrar todo el frío local", key="alertas_del_frio_all"):
                r = purgar_frio_local_ui(solo_rupturas=False)
                (st.success if r.get("ok") else st.error)(r.get("mensaje"))
                if r.get("ok"):
                    st.rerun()
    _df_al = st.session_state.get("df_trabajo")
    _cols_al = (
        funciones.resolver_mapa_columnas(_df_al, st.session_state.get("mapeo_columnas_manual"))
        if _df_al is not None
        else None
    )
    render_modulo_alertas_tendencias(
        df_packing=_df_al,
        cols_mapa=_cols_al,
        peso_min_caja=peso_min_caja,
        max_merma_permitida=max_merma_permitida,
        key_prefix="m7_vista_alertas",
    )
