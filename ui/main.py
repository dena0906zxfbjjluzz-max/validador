"""Orquestación UI: login, navegación y enrutado de pantallas."""
from __future__ import annotations

import datetime

import pandas as pd
import streamlit as st

import funciones
import motor_planta
import seguridad_cortafuego as firewall
from ui.auth import (
    cargar_nombre_planta,
    listar_accesos_planta,
    listar_nombres_planta,
)
from ui.style import pagina_ecc_style, sidebar_brand
from ui.theme import apply_theme
from ui.screens import alertas as screen_alertas
from ui.screens import contenedores as screen_contenedores
from ui.screens import dashboard as screen_dashboard
from ui.screens import historial as screen_historial
from ui.screens import inicio as screen_inicio
from ui.screens import movil as screen_movil
from ui.screens import operacion as screen_operacion
from ui.screens import qr as screen_qr


def run() -> None:
    # Cortafuego: bootstrap DB de seguridad
    try:
        firewall.inicializar_cortafuego_db()
    except Exception:
        pass

    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    apply_theme()

    # Marca de producto en sidebar (antes de navegación)
    _sb_planta = ""
    try:
        if st.session_state.get("autenticado"):
            _sb_planta = cargar_nombre_planta()
    except Exception:
        _sb_planta = ""
    sidebar_brand(
        planta=_sb_planta or "Control de calidad",
        usuario=st.session_state.get("fw_usuario") or "",
        rol=st.session_state.get("rol_planta") or "",
    )

    st.sidebar.markdown(
        """
        <p class="sb-nav-label">Espacio de trabajo</p>
        <p class="sb-nav-title">Módulo</p>
        """,
        unsafe_allow_html=True,
    )
    modo_app = st.sidebar.radio(
        "Seleccione el módulo:",
        [
            "Planta / Packing (login)",
            "Móvil · QR + frío",
            "Verificación pública ECC",
        ],
        index=0,
        key="nav_modo_app",
    )

    # Cortafuego: cerrar sesión (solo si autenticado) — detalle ya va en marca lateral
    if st.session_state.get("autenticado"):
        st.sidebar.markdown("---")
        if st.sidebar.button("Cerrar sesión segura", key="btn_fw_logout"):
            firewall.cerrar_sesion(st.session_state, "logout_manual")
            st.session_state["rol_planta"] = None
            st.session_state["nombre_planta_sesion"] = None
            st.rerun()

    # ---------- MÓDULO PÚBLICO: verificación de PDF firmado (sin login) ----------
    if modo_app == "Verificación pública ECC":
        pagina_ecc_style(
            "Verificación pública ECC",
            "Compruebe si la firma Ed25519 del PDF es auténtica o si el documento fue alterado.",
            eyebrow="Validador",
            meta="sin login",
        )

        pdf_verif = st.file_uploader(
            "PDF ejecutivo firmado",
            type=["pdf"],
            key="uploader_verificacion_ecc",
        )

        with st.expander("Verificación manual (si el PDF no se puede leer)"):
            mensaje_manual = st.text_input("Mensaje firmado", key="msg_manual_ecc")
            firma_manual = st.text_area("Firma hex Ed25519 (128 caracteres)", key="firma_manual_ecc")
            pub_manual = st.text_area("Llave pública hex Ed25519 (64 caracteres)", key="pub_manual_ecc")
            usar_manual = st.checkbox("Usar datos manuales en lugar del PDF", key="usar_manual_ecc")

        if st.button("Verificar autenticidad ECC", type="primary"):
            try:
                if usar_manual:
                    datos = {
                        "mensaje": mensaje_manual,
                        "firma": firma_manual,
                        "llave_publica": pub_manual,
                    }
                elif pdf_verif is not None:
                    datos = funciones.extraer_sello_ecc_pdf(pdf_verif.getvalue())
                else:
                    st.error("Suba un PDF o active la verificación manual.")
                    st.stop()

                resultado = motor_planta.auditar_sello_pdf(datos)

                st.markdown("#### Resultado de la auditoría criptográfica")
                if resultado["ok"] and resultado["estado"] == "AUTENTICO":
                    st.success(resultado["detalle"])
                elif resultado["ok"]:
                    st.warning(resultado["detalle"])
                else:
                    st.error(resultado["detalle"])

                st.caption(f"Estado: `{resultado['estado']}`")
                st.code(f"Mensaje: {resultado['mensaje']}")
                st.code(f"Firma: {resultado['firma']}")
                st.code(f"Llave pública: {resultado['llave_publica']}")

                oficial = motor_planta.llave_publica_oficial_hex()
                if oficial:
                    st.caption(f"Llave pública oficial de planta (derivada de secrets): `{oficial}`")

                # Cruce con registro histórico permanente (si el sello ya fue archivado)
                try:
                    hash_pdf = funciones.calcular_hash_reporte(
                        resultado["mensaje"], resultado["firma"], resultado["llave_publica"]
                    )
                    st.caption(f"Hash del sello (SHA-256): `{hash_pdf}`")
                    hist = funciones.buscar_reporte_por_hash(hash_pdf)
                    if hist:
                        st.success(
                            f"Registro histórico encontrado · Fecha: {hist['fecha_hora']} · "
                            f"Lote: {hist['lote']} · Responsable: {hist['responsable']}"
                        )
                    else:
                        st.info(
                            "No hay entrada en el historial SQLite para este hash "
                            "(puede ser un PDF anterior al registro histórico, o se generó en otra instancia)."
                        )
                except Exception:
                    pass
            except Exception as e:
                st.error(f"No se pudo verificar el PDF: {e}")

        st.markdown("---")
        st.subheader("Consulta de historial por hash")
        hash_busqueda = st.text_input("Pegue el hash SHA-256 del reporte", key="hash_hist_public")
        if st.button("Buscar en historial", key="btn_hash_hist_public"):
            if not hash_busqueda.strip():
                st.warning("Ingrese un hash.")
            else:
                hist = funciones.buscar_reporte_por_hash(hash_busqueda.strip())
                if hist:
                    st.success("Registro encontrado en historial permanente")
                    st.json({
                        "fecha": hist["fecha_hora"],
                        "lote": hist["lote"],
                        "hash": hist["hash_sha256"],
                        "responsable": hist["responsable"],
                        "archivo": hist["archivo"],
                        "producto": hist["producto"],
                    })
                else:
                    st.error("Hash no encontrado en el historial de reportes.")

        st.stop()

    # ---------- ACCESO PLANTA ----------
    if not st.session_state["autenticado"]:
        pagina_ecc_style(
            "Acceso de planta",
            "Credenciales de control de calidad. Para verificar un PDF use Verificación pública ECC.",
            eyebrow="Validador",
            meta="sesión segura",
        )

        accesos_planta, error_creds = listar_accesos_planta()
        if error_creds:
            st.error(error_creds)
            st.stop()

        # Estado del cortafuego (bloqueo por fuerza bruta)
        _bloq, _segs_bloq = firewall.estado_bloqueo(st.session_state)
        if _bloq:
            st.error(
                f"🔒 Cortafuego activo: demasiados intentos fallidos. "
                f"Espere {_segs_bloq // 60}m {_segs_bloq % 60}s."
            )
            st.caption("Los intentos se registran en la bitácora de seguridad local.")
            st.stop()

        usuarioInput = st.text_input("Usuario:", key="login_usuario")
        passwordInput = st.text_input("Contraseña:", type="password", key="login_clave")

        if st.button("Ingresar", type="primary", key="btn_login_planta"):
            resultado_login = firewall.intentar_login_lista(
                st.session_state,
                usuario_in=usuarioInput,
                clave_in=passwordInput,
                candidatos=accesos_planta,
            )
            if resultado_login.get("ok"):
                st.session_state["rol_planta"] = resultado_login.get("rol") or "supervisor"
                if resultado_login.get("planta"):
                    st.session_state["nombre_planta_sesion"] = resultado_login["planta"]
                st.success(resultado_login.get("mensaje") or "Acceso concedido.")
                st.rerun()
            else:
                st.error(resultado_login.get("mensaje") or "Credenciales incorrectas.")
                if resultado_login.get("bloqueado"):
                    st.rerun()
        _nombres_p = listar_nombres_planta(accesos_planta)
        if _nombres_p:
            st.caption("Plantas configuradas: " + " · ".join(_nombres_p))
        st.caption(f"Cortafuego · máx. {firewall.politica()['max_intentos']} intentos")
        st.stop()

    # Rol de sesión (compat: sesiones previas sin rol → supervisor)
    if "rol_planta" not in st.session_state or not st.session_state.get("rol_planta"):
        st.session_state["rol_planta"] = "supervisor"
    _es_supervisor = firewall.es_supervisor(st.session_state)
    _rol_label = st.session_state.get("rol_planta") or "supervisor"

    # Sesión autenticada: validar token + timeout en cada rerun
    _sesion_ok, _motivo_sesion = firewall.sesion_valida(st.session_state)
    if not _sesion_ok:
        st.warning(
            "Sesión cerrada por el cortafuego"
            + (f" ({_motivo_sesion})." if _motivo_sesion not in ("no_auth",) else ".")
            + " Vuelva a iniciar sesión."
        )
        st.session_state["autenticado"] = False
        st.stop()

    nombre_planta = cargar_nombre_planta()
    _plant_label = nombre_planta or "Planta Autorizada"

    # Modo móvil: solo QR + frío (sin packing completo)
    if modo_app == "Móvil · QR + frío":
        st.sidebar.caption(f"Planta: {_plant_label}")
        screen_movil.render(
            producto_sel=st.session_state.get("dash_producto") or "Palta Hass",
            auditor_nombre=st.session_state.get("dash_inspector") or "Control de Calidad",
        )
        st.stop()

    funciones.inicializar_base_datos()

    if "lote_congelado" not in st.session_state:
        st.session_state["lote_congelado"] = False

    if "mostrar_vacios" not in st.session_state:
        st.session_state["mostrar_vacios"] = False

    # Navegación por pantallas (no lista infinita de módulos)
    if "vista_planta" not in st.session_state:
        st.session_state["vista_planta"] = "inicio"
    if "modulo_nav" not in st.session_state:
        st.session_state["modulo_nav"] = "Resumen del lote"

    # Cámara QR apagada por defecto
    if "camara_qr_activa" not in st.session_state:
        st.session_state["camara_qr_activa"] = False
    if "camera_qr_token" not in st.session_state:
        st.session_state["camera_qr_token"] = 0
    if "camara_cnt_activa" not in st.session_state:
        st.session_state["camara_cnt_activa"] = False
    if "camera_cnt_token" not in st.session_state:
        st.session_state["camera_cnt_token"] = 0
    for _ck in (
        "cnt_form_booking",
        "cnt_form_contenedor",
        "cnt_form_plinea",
        "cnt_form_psenasa",
    ):
        if _ck not in st.session_state:
            st.session_state[_ck] = ""


    # ─── Navegación por botones (solo vista_planta / modulo_nav en session_state) ─
    st.sidebar.markdown("---")
    st.sidebar.caption("Navegación")

    _tiene_lote = st.session_state.get("df_trabajo") is not None
    _MODULOS_OP = [
        "Resumen del lote",
        "1 · Balanza / SSCC",
        "2 · LMR / SENASA",
        "3 · Trazabilidad",
        "4 · Cadena de frío",
        "7 · Alertas y tendencias",
        "Limpieza y cierre",
    ]
    _MODULOS_BTNS = [
        ("Resumen", "Resumen del lote", "nav_mod_resumen"),
        ("Balanza", "1 · Balanza / SSCC", "nav_mod_balanza"),
        ("LMR", "2 · LMR / SENASA", "nav_mod_lmr"),
        ("Trazabilidad", "3 · Trazabilidad", "nav_mod_traz"),
        ("Frío", "4 · Cadena de frío", "nav_mod_frio"),
        ("Alertas lote", "7 · Alertas y tendencias", "nav_mod_alertas_lote"),
        ("Cierre", "Limpieza y cierre", "nav_mod_cierre"),
    ]

    if st.session_state.get("vista_planta") == "operacion" and not _tiene_lote:
        st.session_state["vista_planta"] = "inicio"
    if st.session_state.get("modulo_nav") not in _MODULOS_OP:
        st.session_state["modulo_nav"] = "Resumen del lote"

    _nav_vistas = [
        ("Inicio", "inicio", "nav_btn_inicio"),
        ("Dashboard", "dashboard", "nav_btn_dashboard"),
    ]
    if _tiene_lote:
        _nav_vistas.append(("Operación del lote", "operacion", "nav_btn_operacion"))
    _nav_vistas.extend(
        [
            ("QR pallet", "qr", "nav_btn_qr"),
            ("Contenedores", "contenedores", "nav_btn_cnt"),
            ("Alertas", "alertas", "nav_btn_alertas"),
            ("Historial", "historial", "nav_btn_historial"),
        ]
    )

    for _lab, _vid, _key in _nav_vistas:
        _active = st.session_state.get("vista_planta") == _vid
        if st.sidebar.button(
            _lab,
            key=_key,
            type="primary" if _active else "secondary",
            use_container_width=True,
        ):
            st.session_state["vista_planta"] = _vid
            if _vid == "operacion":
                st.session_state["modulo_nav"] = st.session_state.get("modulo_nav") or "Resumen del lote"
            st.rerun()

    vista = st.session_state.get("vista_planta", "inicio")

    if vista == "operacion":
        st.sidebar.caption("Módulo")
        for _lab, _mod, _key in _MODULOS_BTNS:
            _active = st.session_state.get("modulo_nav") == _mod
            if st.sidebar.button(
                _lab,
                key=_key,
                type="primary" if _active else "secondary",
                use_container_width=True,
            ):
                st.session_state["modulo_nav"] = _mod
                st.rerun()
        if st.sidebar.button("Volver al inicio", key="btn_volver_inicio", use_container_width=True):
            st.session_state["vista_planta"] = "inicio"
            st.rerun()

    with st.sidebar.expander("Parámetros de planta", expanded=(vista == "inicio")):
        auditor_nombre = st.text_input("Inspector asignado:", value="Control de Calidad", key="dash_inspector")
        producto_sel = st.selectbox(
            "Cultivo / fruta:",
            ["Palta Hass", "Arándano", "Espárrago", "Uva Red Globe", "Personalizado"],
            key="dash_producto",
        )
        mercado_destino = st.selectbox(
            "Mercado de destino:",
            ["Europa (GlobalGAP/UE)", "Estados Unidos (FDA/USDA)", "Asia / China", "Chile / Local"],
            key="dash_mercado",
        )
        if producto_sel == "Palta Hass":
            limit_temp_default = 5.0
            limit_brix_default = 21.0
        elif producto_sel == "Arándano":
            limit_temp_default = 0.0
            limit_brix_default = 11.5
        elif producto_sel == "Espárrago":
            limit_temp_default = 3.0
            limit_brix_default = 8.0
        elif producto_sel == "Uva Red Globe":
            limit_temp_default = -0.5
            limit_brix_default = 16.0
        else:
            limit_temp_default = 4.0
            limit_brix_default = 10.0
        _tmin_fruta, _tmax_fruta = funciones.obtener_rango_frio_fruta(producto_sel)
        if producto_sel == "Personalizado":
            temp_min_limite = st.number_input(
                "Temp. mínima cámara (°C):", value=limit_temp_default, step=0.5, key="dash_tmin"
            )
            temp_max_limite = st.number_input(
                "Temp. máxima cámara (°C):", value=limit_temp_default + 2.0, step=0.5, key="dash_tmax"
            )
        else:
            temp_min_limite = _tmin_fruta
            temp_max_limite = _tmax_fruta
            st.caption(f"Cadena de frío: **{temp_min_limite} °C** a **{temp_max_limite} °C**")
        brix_min_limite = st.number_input(
            "Materia seca / Brix mínimo:", value=limit_brix_default, step=0.5, key="dash_brix"
        )
        st.caption("Tolerancias logísticas")
        peso_min_caja = st.number_input(
            "Peso mínimo neto caja (kg):", value=4.0, step=0.1, key="dash_peso"
        )
        max_merma_permitida = st.number_input(
            "Límite máximo de merma (%):", value=5.0, step=0.5, key="dash_merma"
        )

    st.sidebar.markdown("---")
    st.sidebar.caption("Cargar lote")
    archivo = st.sidebar.file_uploader(
        "Excel / CSV de packing",
        type=["xlsx", "csv"],
        key="uploader_recepcion_empaque",
    )

    if archivo is not None:
        try:
            _bytes_arch = archivo.getvalue()
            _ok_up, _msg_up = firewall.validar_upload_bytes(archivo.name, _bytes_arch)
            if not _ok_up:
                st.error(f"🛡️ Cortafuego bloqueó el archivo: {_msg_up}")
                firewall.registrar_evento(
                    "UPLOAD_BLOCK",
                    f"{archivo.name}: {_msg_up}",
                    severidad="warn",
                    usuario=st.session_state.get("fw_usuario") or "",
                )
            else:
                archivo_key = f"{archivo.name}_{archivo.size}"
                if st.session_state.get("archivo_activo") != archivo_key:
                    st.session_state["archivo_activo"] = archivo_key
                    st.session_state["df_trabajo"] = funciones.cargar_datos_archivo(archivo)
                    st.session_state["lote_congelado"] = False
                    st.session_state["nombre_archivo"] = archivo.name
                    st.session_state["mapeo_columnas_manual"] = {}
                    for _c in funciones.CAMPOS_MAPEO_UI:
                        st.session_state.pop(f"map_col_{_c}", None)
                    st.session_state["vista_planta"] = "operacion"
                    st.session_state["modulo_nav"] = "Resumen del lote"
                    firewall.registrar_evento(
                        "UPLOAD_OK",
                        f"Archivo {archivo.name} ({archivo.size} bytes)",
                        severidad="info",
                        usuario=st.session_state.get("fw_usuario") or "",
                    )
                    st.rerun()
                st.session_state["nombre_archivo"] = archivo.name
        except Exception as _e_up:
            st.error(f"No se pudo leer el archivo: {_e_up}")

    vista = st.session_state.get("vista_planta", "inicio")
    modulo_nav = st.session_state.get("modulo_nav", "Resumen del lote")

    # Enrutado de pantallas
    if vista == "inicio":
        screen_inicio.render(plant_label=_plant_label, es_supervisor=_es_supervisor)
    elif vista == "dashboard":
        screen_dashboard.render(
            plant_label=_plant_label,
            rol_label=_rol_label,
            es_supervisor=_es_supervisor,
        )
    elif vista == "qr":
        screen_qr.render()
    elif vista == "contenedores":
        screen_contenedores.render(mercado_destino=mercado_destino)
    elif vista == "alertas":
        screen_alertas.render(
            es_supervisor=_es_supervisor,
            peso_min_caja=peso_min_caja,
            max_merma_permitida=max_merma_permitida,
        )
    elif vista == "historial":
        screen_historial.render()
    elif vista == "operacion" and st.session_state.get("df_trabajo") is not None:
        screen_operacion.render(
            archivo=archivo,
            modulo_nav=modulo_nav,
            auditor_nombre=auditor_nombre,
            producto_sel=producto_sel,
            mercado_destino=mercado_destino,
            peso_min_caja=peso_min_caja,
            max_merma_permitida=max_merma_permitida,
            temp_min_limite=temp_min_limite,
            temp_max_limite=temp_max_limite,
            es_supervisor=_es_supervisor,
            nombre_planta=nombre_planta,
        )
