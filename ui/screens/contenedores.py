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

def _apagar_camara_cnt():
    """Apaga cámara del módulo de contenedores."""
    st.session_state["camara_cnt_activa"] = False
    st.session_state["camera_cnt_token"] = int(st.session_state.get("camera_cnt_token") or 0) + 1
    for k in list(st.session_state.keys()):
        if str(k).startswith("camera_escaneo_cnt_"):
            try:
                del st.session_state[k]
            except Exception:
                pass


def _cnt_aplicar_prefill(pl=None, reg=None):
    """Rellena los campos del formulario M5 (widgets key=) desde QR o registro."""
    pl = pl or {}
    reg = reg or {}

    def _pick(*keys):
        for src in (reg, pl):
            for k in keys:
                v = src.get(k) if isinstance(src, dict) else None
                if v is not None and str(v).strip():
                    return str(v).strip()
        return ""

    booking = _pick("booking", "Booking")
    contenedor = _pick("contenedor", "Contenedor", "container")
    plinea = _pick("precinto_linea", "Precinto Línea", "precinto linea")
    psenasa = _pick("precinto_senasa", "Precinto SENASA", "precinto senasa")
    if booking:
        st.session_state["cnt_form_booking"] = booking
    if contenedor:
        st.session_state["cnt_form_contenedor"] = contenedor
    if plinea:
        st.session_state["cnt_form_plinea"] = plinea
    if psenasa:
        st.session_state["cnt_form_psenasa"] = psenasa


def render(*, mercado_destino: str = "Europa (GlobalGAP/UE)"):
    pagina_ecc_style("Contenedores", "Booking · ISO 6346 · precintos")
    with st.container():

        col_c_scan, col_c_form = st.columns([1, 1])

        with col_c_scan:
            if not st.session_state["camara_cnt_activa"]:
                if st.button(
                    "Activar escáner",
                    type="primary",
                    key="btn_activar_escaner_cnt",
                ):
                    st.session_state["camara_cnt_activa"] = True
                    st.rerun()
            else:
                foto_cnt = st.camera_input(
                    "Cámara contenedor",
                    key=f"camera_escaneo_cnt_{st.session_state['camera_cnt_token']}",
                )
                if st.button("Apagar cámara", key="btn_apagar_camara_cnt"):
                    _apagar_camara_cnt()
                    st.rerun()

                if foto_cnt is not None:
                    try:
                        with st.spinner("Leyendo QR y consultando contenedor…"):
                            res_cnt = funciones.procesar_escaneo_contenedor_camara(
                                foto_cnt.getvalue()
                            )
                        st.session_state["ultimo_resultado_cnt"] = res_cnt
                        _cnt_aplicar_prefill(
                            res_cnt.get("payload"),
                            res_cnt.get("registro") or res_cnt.get("local"),
                        )
                    except Exception as e:
                        st.session_state["ultimo_resultado_cnt"] = {
                            "verificado": False,
                            "tipo_ui": "error",
                            "mensaje_ui": f"Error de escaneo: {e}",
                        }
                    _apagar_camara_cnt()
                    st.rerun()

            st.markdown("---")
            texto_cnt = st.text_input(
                "Booking o contenedor",
                placeholder="TGBU1234567 · BKG-998",
                key="cnt_lookup_manual",
            )
            if st.button("Buscar contenedor", key="btn_cnt_lookup"):
                if not (texto_cnt or "").strip():
                    st.warning("Escriba un booking o contenedor.")
                else:
                    ok_in, txt_ok = firewall.validar_entrada_operativa(texto_cnt.strip())
                    if not ok_in:
                        st.error(f"Cortafuego: {txt_ok}")
                    else:
                        res_cnt = funciones.validar_y_consultar_contenedor(texto_qr=txt_ok)
                        st.session_state["ultimo_resultado_cnt"] = res_cnt
                        _cnt_aplicar_prefill(
                            res_cnt.get("payload"),
                            res_cnt.get("registro") or res_cnt.get("local"),
                        )
                        st.rerun()

            res_ui = st.session_state.get("ultimo_resultado_cnt")
            if res_ui:
                if res_ui.get("tipo_ui") == "success":
                    st.success(res_ui.get("mensaje_ui") or "Contenedor OK")
                else:
                    st.error(res_ui.get("mensaje_ui") or "No encontrado")
                pl = res_ui.get("payload") or {}
                if pl:
                    st.caption(
                        f"Leído · booking `{pl.get('booking') or 'N/D'}` · "
                        f"contenedor `{(pl.get('contenedor') or 'N/D')}`"
                    )

        with col_c_form:
            booking_input = st.text_input(
                "Booking *",
                placeholder="BKG-998231",
                key="cnt_form_booking",
            )
            contenedor_input = st.text_input(
                "Contenedor reefer * (ISO 6346)",
                placeholder="TGBU1234567",
                key="cnt_form_contenedor",
            )
            precinto_linea_input = st.text_input(
                "Precinto línea naviera *",
                placeholder="MSC-L99821",
                key="cnt_form_plinea",
            )
            precinto_senasa_input = st.text_input(
                "Precinto SENASA",
                placeholder="SENASA-004821",
                key="cnt_form_psenasa",
            )
            st.caption(f"Destino: {mercado_destino}")

            if st.button(
                "Sellar y registrar contenedor",
                type="primary",
                key="btn_cnt_sellar",
            ):
                try:
                    resultado_cnt = funciones.registrar_contenedor_despacho(
                        booking=booking_input,
                        contenedor=contenedor_input,
                        precinto_linea=precinto_linea_input,
                        precinto_senasa=precinto_senasa_input,
                        destino=mercado_destino,
                        estado="SELLADO Y LISTO",
                        inspector=auditor_nombre,
                    )
                    if resultado_cnt.get("tipo_ui") == "success":
                        st.success(resultado_cnt.get("mensaje_ui"))
                    else:
                        st.error(resultado_cnt.get("mensaje_ui"))
                    sb_c = resultado_cnt.get("supabase") or {}
                    if sb_c.get("ok"):
                        if sb_c.get("ya_existia") or sb_c.get("status") == 409:
                            st.info("☁️ Supabase: contenedor ya estaba en la nube.")
                        else:
                            st.caption(f"☁️ Supabase: {sb_c.get('mensaje')}")
                    elif sb_c.get("configurado") is False:
                        st.caption("☁️ Supabase no configurado (solo SQLite local).")
                    elif sb_c:
                        st.warning(sb_c.get("mensaje") or "Error remoto contenedores_despacho")
                except Exception as e:
                    st.error(e)

        lista_cont_db = funciones.cargar_contenedores_db(50)
        if lista_cont_db:
            with st.expander(f"Contenedores registrados ({len(lista_cont_db)})"):
                st.dataframe(pd.DataFrame(lista_cont_db), width="stretch", hide_index=True)
