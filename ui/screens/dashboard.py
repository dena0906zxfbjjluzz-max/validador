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


def render(*, plant_label: str, rol_label: str, es_supervisor: bool):
    dash = funciones.resumen_dashboard_turno()
    pagina_ecc_style("Dashboard de turno", f"Resumen del {dash.get('fecha')} · frío y sellos ECC")

    estado = dash.get("estado_turno")
    if estado == "CRITICO":
        st.error(f"Estado del turno: {estado}")
    elif estado == "VIGILANCIA":
        st.warning(f"Estado del turno: {estado}")
    else:
        st.success(f"Estado del turno: {estado}")

    k = dash.get("kpis") or {}
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Sellos ECC hoy", k.get("sellos_ecc", 0))
    m2.metric("Lecturas frío hoy", k.get("lecturas_frio", 0))
    m3.metric("Rupturas frío hoy", k.get("rupturas_frio", 0))
    m4.metric("Contenedores", k.get("contenedores", 0))
    m5.metric("Cargas packing", k.get("cargas_packing", 0))

    st.markdown("---")
    st.subheader("Alertas de frío activas")
    af = dash.get("alertas_frio") or {}
    st.caption(af.get("mensaje") or "")
    activas = af.get("activas") or []
    if activas:
        st.dataframe(pd.DataFrame(activas), width="stretch", hide_index=True)
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Ir a cadena de frío", key="dash_ir_frio", use_container_width=True):
                if st.session_state.get("df_trabajo") is not None:
                    st.session_state["vista_planta"] = "operacion"
                    st.session_state["modulo_nav"] = "4 · Cadena de frío"
                else:
                    st.session_state["vista_planta"] = "alertas"
                st.rerun()
        with b2:
            if st.button("Ver tendencias", key="dash_ir_alertas", use_container_width=True):
                st.session_state["vista_planta"] = "alertas"
                st.rerun()
    else:
        st.info("Sin rupturas recientes en la ventana de alerta.")

    if es_supervisor:
        with st.expander("Borrar alertas de frío (SQLite local)"):
            st.caption(
                "Las alertas se leen de la base local de la app, no solo de Supabase. "
                "Si borró en Supabase y siguen apareciendo, limpie aquí."
            )
            c_del1, c_del2 = st.columns(2)
            with c_del1:
                if st.button("Borrar solo rupturas", key="dash_del_rupturas"):
                    r = purgar_frio_local_ui(solo_rupturas=True)
                    (st.success if r.get("ok") else st.error)(r.get("mensaje"))
                    if r.get("ok"):
                        st.rerun()
            with c_del2:
                if st.button("Borrar todas las lecturas de frío", key="dash_del_frio_all"):
                    r = purgar_frio_local_ui(solo_rupturas=False)
                    (st.success if r.get("ok") else st.error)(r.get("mensaje"))
                    if r.get("ok"):
                        st.rerun()

    cfg_av = funciones._config_avisos()
    st.caption(
        "Avisos: "
        + (
            "email "
            + ("✓" if cfg_av.get("email_ok") else "—")
            + " · WhatsApp "
            + ("✓" if cfg_av.get("whatsapp_ok") else "—")
        )
    )
    if activas and cfg_av.get("habilitado"):
        if es_supervisor:
            if st.button("Reenviar aviso de la última ruptura", key="dash_reenviar_aviso"):
                ult = activas[0]
                r = funciones.notificar_ruptura_frio(
                    {
                        "camara": ult.get("camara"),
                        "temperatura": ult.get("temperatura"),
                        "temp_min": "?",
                        "temp_max": "?",
                        "producto": ult.get("producto"),
                        "inspector": ult.get("inspector"),
                        "hora_registro": ult.get("hora"),
                        "estado": ult.get("estado"),
                    },
                    forzar=True,
                )
                if r.get("ok"):
                    st.success(r.get("mensaje"))
                else:
                    st.warning(r.get("mensaje") or "No enviado")
        else:
            st.caption("Reenvío de avisos: solo supervisor.")

    lotes = dash.get("lotes_sellados") or []
    with st.expander(f"Sellos ECC de hoy ({len(lotes)})"):
        if lotes:
            st.dataframe(pd.DataFrame(lotes), width="stretch", hide_index=True)
        else:
            st.caption("Aún no hay sellos archivados hoy.")

    _insp_dash = st.session_state.get("fw_usuario") or "Inspector"
    _k = dash.get("kpis") or {}
    _msg_dash = (
        f"Dashboard turno {dash.get('fecha')} | Planta: {plant_label} | "
        f"Estado: {dash.get('estado_turno')} | Rupturas: {_k.get('rupturas_frio', 0)} | "
        f"Lecturas frío: {_k.get('lecturas_frio', 0)} | "
        f"Sellos ECC: {_k.get('sellos_ecc', 0)} | Emisor: {_insp_dash}"
    )
    try:
        _pub_dash, _sig_dash = motor_planta.firmar_reporte_ecc(_msg_dash)
        _modo_dash = motor_planta.modo_firma_activo()
        if _modo_dash == "real":
            st.caption(f"PDF del turno con sello Ed25519 real · `{motor_planta.motor_activo()}`")
        else:
            st.caption("PDF del turno firmado en modo demo (revise LLAVE_PRIVADA en secrets).")
    except Exception as _e_sig:
        _pub_dash, _sig_dash = "", ""
        st.caption(f"No se pudo firmar el PDF del turno: {_e_sig}")

    pdf_dash = funciones.generar_pdf_dashboard_turno(
        dash,
        planta_nombre=plant_label,
        inspector=_insp_dash,
        rol=rol_label,
        firma_ECDSA=_sig_dash,
        llave_publica=_pub_dash,
        mensaje_firmado=_msg_dash,
    )
    st.download_button(
        "Descargar PDF del turno (firmado ECC)",
        data=pdf_dash,
        file_name=f"dashboard_turno_{dash.get('fecha', 'hoy')}.pdf",
        mime="application/pdf",
        key="dl_pdf_dashboard_turno",
        type="primary",
    )
