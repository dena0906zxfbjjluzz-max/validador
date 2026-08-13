"""Modo móvil liviano: QR pallet + registro de frío."""
from __future__ import annotations

import streamlit as st

import funciones
from ui.style import pagina_ecc_style


def _apagar_camara_movil() -> None:
    st.session_state["movil_cam_activa"] = False
    st.session_state["movil_cam_token"] = int(st.session_state.get("movil_cam_token") or 0) + 1
    st.session_state.pop("movil_qr_cam", None)


def render(*, producto_sel: str = "Palta Hass", auditor_nombre: str = "Control de Calidad") -> None:
    if "movil_cam_activa" not in st.session_state:
        st.session_state["movil_cam_activa"] = False
    if "movil_cam_token" not in st.session_state:
        st.session_state["movil_cam_token"] = 0

    pagina_ecc_style("Móvil", "QR · cadena de frío")

    tab_qr, tab_frio = st.tabs(["QR pallet", "Frío"])

    with tab_qr:
        texto = st.text_input("Código / hash / lote", key="movil_qr_texto")

        if not st.session_state["movil_cam_activa"]:
            st.caption("Cámara apagada (ahorra batería y privacidad).")
            if st.button("Activar cámara QR", type="secondary", key="movil_cam_on"):
                st.session_state["movil_cam_activa"] = True
                st.rerun()
            foto = None
        else:
            foto = st.camera_input(
                "Foto del QR",
                key=f"movil_qr_cam_{st.session_state['movil_cam_token']}",
            )
            if st.button("Apagar cámara", key="movil_cam_off"):
                _apagar_camara_movil()
                st.rerun()

        if st.button("Validar pallet", type="primary", key="movil_qr_btn"):
            try:
                if foto is not None:
                    r = funciones.procesar_escaneo_qr_camara(foto.getvalue())
                    _apagar_camara_movil()
                else:
                    r = funciones.validar_pallet_por_qr(texto_qr=texto)
                if r.get("ok") or r.get("verificado"):
                    st.success(r.get("mensaje") or r.get("mensaje_ui") or "OK")
                    if r.get("registro"):
                        st.json(r.get("registro"))
                else:
                    st.warning(r.get("mensaje") or r.get("mensaje_ui") or "No encontrado")
                if foto is not None:
                    st.rerun()
            except Exception as e:
                st.error(str(e))

    with tab_frio:
        camara = st.text_input("Cámara / túnel", value="Pre-Cámara 01", key="movil_cam")
        temp = st.number_input("Temperatura °C", value=5.0, step=0.1, key="movil_temp")
        prod = st.selectbox(
            "Producto",
            ["Palta Hass", "Arándano", "Espárrago", "Uva Red Globe", producto_sel],
            key="movil_prod",
        )
        insp = st.text_input("Inspector", value=auditor_nombre, key="movil_insp")
        if st.button("Registrar lectura", type="primary", key="movil_frio_btn"):
            r = funciones.registrar_control_frio(
                camara=camara,
                temperatura=temp,
                producto=prod,
                inspector=insp,
            )
            if r.get("tipo_ui") == "success":
                st.success(r.get("mensaje_ui"))
            else:
                st.error(r.get("mensaje_ui"))
            av = r.get("aviso") or {}
            if av.get("ok"):
                st.warning(av.get("mensaje"))
        ult = funciones.cargar_frio_db(8)
        if ult:
            st.caption("Últimas lecturas")
            st.dataframe(ult, width="stretch", hide_index=True)
