"""Historial operativo: frío, sellos ECC y bitácora de cambios."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import funciones
from ui.style import pagina_ecc_style


def render() -> None:
    pagina_ecc_style("Historial", "Frío · sellos ECC · bitácora")

    tab_frio, tab_sellos, tab_bit = st.tabs(["Cadena de frío", "Sellos ECC", "Bitácora"])

    with tab_frio:
        lecturas = funciones.cargar_frio_db(80)
        if lecturas:
            st.dataframe(pd.DataFrame(lecturas), width="stretch", hide_index=True)
        else:
            st.info("Sin lecturas de frío registradas.")

    with tab_sellos:
        sellos = funciones.cargar_historial_reportes_db(80)
        if sellos:
            st.dataframe(pd.DataFrame(sellos), width="stretch", hide_index=True)
        else:
            st.info("Sin sellos ECC archivados.")

    with tab_bit:
        bit = funciones.cargar_bitacora_db()
        if bit:
            st.dataframe(pd.DataFrame(bit), width="stretch", hide_index=True)
        else:
            st.info("Bitácora de cambios vacía.")
