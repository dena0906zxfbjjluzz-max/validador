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

def _apagar_camara_qr():
    """Desmonta st.camera_input y libera el lente del dispositivo."""
    st.session_state["camara_qr_activa"] = False
    st.session_state["camera_qr_token"] = int(st.session_state.get("camera_qr_token") or 0) + 1
    for k in list(st.session_state.keys()):
        if str(k).startswith("camera_escaneo_qr_"):
            try:
                del st.session_state[k]
            except Exception:
                pass


def render():
    col_cen = st.container()
    with col_cen:
        pagina_ecc_style("QR pallet", "historial_reportes")
        with st.container():

            if not st.session_state["camara_qr_activa"]:
                if st.button(
                    "Activar escáner QR",
                    type="primary",
                    key="btn_activar_escaner_qr",
                ):
                    st.session_state["camara_qr_activa"] = True
                    st.rerun()
            else:
                foto_qr = st.camera_input(
                    "Cámara QR",
                    key=f"camera_escaneo_qr_{st.session_state['camera_qr_token']}",
                )
                if st.button("Apagar cámara", key="btn_apagar_camara_qr"):
                    _apagar_camara_qr()
                    st.rerun()

                if foto_qr is not None:
                    try:
                        with st.spinner("Decodificando QR y consultando Supabase…"):
                            resultado_qr = funciones.procesar_escaneo_qr_camara(foto_qr.getvalue())
                        st.session_state["ultimo_resultado_qr"] = resultado_qr
                    except Exception as e:
                        st.session_state["ultimo_resultado_qr"] = {
                            "verificado": False,
                            "tipo_ui": "error",
                            "mensaje_ui": f"Error en escaneo QR: {e}",
                        }
                    _apagar_camara_qr()
                    st.rerun()

            st.markdown("---")
            with st.expander("Validación manual / foto del QR (si no usa cámara)"):
                img_qr_upload = st.file_uploader(
                    "Subir foto del QR",
                    type=["png", "jpg", "jpeg", "webp"],
                    key="upload_foto_qr_pallet",
                )
                texto_qr_manual = st.text_area(
                    "Texto del QR (JSON / hash / lote|hash)",
                    height=90,
                    key="texto_manual_qr_pallet",
                    placeholder='{"lote":"L-001","hash_sha256":"abc...64 hex"}',
                )
                if st.button("Validar respaldo en Supabase", key="btn_validar_qr_respaldo"):
                    imagen_bytes = img_qr_upload.getvalue() if img_qr_upload is not None else None
                    try:
                        if imagen_bytes is not None and img_qr_upload is not None:
                            _ok_img, _msg_img = firewall.validar_upload_bytes(
                                img_qr_upload.name, imagen_bytes
                            )
                            if not _ok_img:
                                st.error(f"🛡️ Cortafuego: {_msg_img}")
                                resultado_qr = None
                            else:
                                resultado_qr = funciones.procesar_escaneo_qr_camara(imagen_bytes)
                        elif texto_qr_manual and texto_qr_manual.strip():
                            _ok_txt, _txt_o_err = firewall.validar_entrada_operativa(
                                texto_qr_manual.strip()
                            )
                            if not _ok_txt:
                                st.error(f"🛡️ Cortafuego: {_txt_o_err}")
                                resultado_qr = None
                            else:
                                resultado_qr = funciones.validar_pallet_por_qr(texto_qr=_txt_o_err)
                        else:
                            st.warning("Suba una imagen o pegue el texto del QR.")
                            resultado_qr = None
                        if resultado_qr is not None:
                            st.session_state["ultimo_resultado_qr"] = resultado_qr
                    except Exception as e:
                        st.error(f"Error en escaneo QR: {e}")

            resultado_qr_ui = st.session_state.get("ultimo_resultado_qr")
            if resultado_qr_ui:
                if resultado_qr_ui.get("tipo_ui") == "success":
                    st.success(
                        resultado_qr_ui.get("mensaje_ui")
                        or "✅ Pallet verificado de forma segura mediante QR en Supabase."
                    )
                else:
                    st.error(
                        resultado_qr_ui.get("mensaje_ui")
                        or "🚨 ALERTA: no se pudo verificar el pallet contra Supabase."
                    )

                payload_qr = resultado_qr_ui.get("payload") or {}
                if payload_qr:
                    st.caption(
                        f"Lote extraído: `{payload_qr.get('lote') or 'N/D'}` · "
                        f"Hash: `{(payload_qr.get('hash_sha256') or 'N/D')[:24]}"
                        f"{'…' if payload_qr.get('hash_sha256') and len(payload_qr.get('hash_sha256') or '') > 24 else ''}`"
                    )
                reg = resultado_qr_ui.get("registro")
                if reg:
                    with st.expander("Registro en historial_reportes (Supabase)"):
                        st.json(reg)
                sb_qr = resultado_qr_ui.get("supabase") or {}
                if sb_qr and not resultado_qr_ui.get("verificado"):
                    with st.expander("Detalle consulta Supabase"):
                        st.write(sb_qr.get("mensaje"))
                        st.caption(f"Endpoint: `{sb_qr.get('endpoint')}`")
                        if sb_qr.get("filas") is not None:
                            st.json(sb_qr.get("filas"))
