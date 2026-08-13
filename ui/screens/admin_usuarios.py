"""Panel supervisor: usuarios locales SQLite."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from planta.usuarios import (
    crear_usuario_local,
    desactivar_usuario_local,
    listar_usuarios_local,
)
from ui.style import pagina_ecc_style


def render(*, plant_label: str):
    pagina_ecc_style(
        "Usuarios de línea",
        "Alta y baja de operarios sin editar Secrets. Los de Secrets siguen vigentes.",
        eyebrow=plant_label or "Planta",
        meta="solo jefe de turno",
    )

    st.caption(
        "Las claves se guardan con hash en la base local de la app. "
        "Si el mismo usuario existe en Secrets, gana Secrets."
    )

    with st.form("form_nuevo_usuario_local"):
        c1, c2 = st.columns(2)
        with c1:
            u = st.text_input("Usuario")
            rol = st.selectbox("Rol", ["operario", "supervisor"])
        with c2:
            clave = st.text_input("Clave", type="password")
            email = st.text_input("Email (OTP / avisos)", placeholder="opcional")
        planta = st.text_input("Planta", value=plant_label or "")
        if st.form_submit_button("Crear usuario", type="primary"):
            r = crear_usuario_local(u, clave, rol=rol, planta=planta, email=email)
            (st.success if r.get("ok") else st.error)(r.get("mensaje"))
            if r.get("ok"):
                st.rerun()

    rows = listar_usuarios_local(solo_activos=False)
    if rows:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "usuario": r["usuario"],
                        "rol": r["rol"],
                        "planta": r["planta"],
                        "email": r["email"],
                        "activo": r["activo"],
                        "creado": r["creado_en"],
                    }
                    for r in rows
                ]
            ),
            width="stretch",
            hide_index=True,
        )
        activos = [r["usuario"] for r in rows if r.get("activo")]
        if activos:
            baja = st.selectbox("Desactivar usuario", activos)
            if st.button("Desactivar", key="btn_desactivar_user"):
                r = desactivar_usuario_local(baja)
                (st.success if r.get("ok") else st.error)(r.get("mensaje"))
                if r.get("ok"):
                    st.rerun()
    else:
        st.info("Aún no hay usuarios locales. Cree el primero arriba.")
