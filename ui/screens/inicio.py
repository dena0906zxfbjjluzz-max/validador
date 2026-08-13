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


def render(*, plant_label: str, es_supervisor: bool = False):
    import html as _html

    _pl = _html.escape(plant_label or "Planta Autorizada")
    st.markdown(
        f"""
        <section class="vx-home-hero">
          <p class="vx-home-kicker">Suite de planta · packing y cadena de frío</p>
          <h1 class="vx-page-title">{_pl}</h1>
          <p class="vx-page-desc">
            Espacio de trabajo para jefe de turno y línea: calidad, pallets y cámaras.
            Cargue el packing en la barra lateral para operar el lote.
          </p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    _af_home = funciones.alertas_frio_activas(limite=5, horas_ventana=12)
    if _af_home.get("nivel") == "CRITICO":
        st.error(_af_home.get("mensaje"))
        if st.button("Ver dashboard de turno", key="btn_home_dash_crit"):
            st.session_state["vista_planta"] = "dashboard"
            st.rerun()
    elif _af_home.get("nivel") == "ALERTA":
        st.warning(_af_home.get("mensaje"))
        if st.button("Ver dashboard de turno", key="btn_home_dash_alerta"):
            st.session_state["vista_planta"] = "dashboard"
            st.rerun()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Panel del turno", type="primary", key="tile_dash", use_container_width=True):
            st.session_state["vista_planta"] = "dashboard"
            st.rerun()
        if st.button("Escanear pallet", key="tile_qr", use_container_width=True):
            st.session_state["vista_planta"] = "qr"
            st.rerun()
        if st.button("Contenedores", key="tile_cnt", use_container_width=True):
            st.session_state["vista_planta"] = "contenedores"
            st.rerun()
    with c2:
        if st.button("Alertas de planta", key="tile_alertas", use_container_width=True):
            st.session_state["vista_planta"] = "alertas"
            st.rerun()
        if st.button("Historial", key="tile_hist", use_container_width=True):
            st.session_state["vista_planta"] = "historial"
            st.rerun()
        if es_supervisor:
            if st.button("Usuarios de línea", key="tile_users", use_container_width=True):
                st.session_state["vista_planta"] = "admin_usuarios"
                st.rerun()
        if st.session_state.get("df_trabajo") is not None:
            if st.button("Operación del lote", type="primary", key="btn_ir_operacion", use_container_width=True):
                st.session_state["vista_planta"] = "operacion"
                st.session_state["modulo_nav"] = "Resumen del lote"
                st.rerun()

    if st.session_state.get("df_trabajo") is not None:
        st.success(f"Lote activo: **{st.session_state.get('nombre_archivo', 'archivo')}**")


    st.markdown("---")
    st.markdown(
        '<p class="vx-page-eyebrow" style="margin:0 0 0.65rem 0">Infraestructura</p>'
        '<h2 class="vx-page-title" style="font-size:1.25rem!important;margin:0 0 0.85rem 0!important">'
        "Servicios de planta</h2>",
        unsafe_allow_html=True,
    )
    col_der = st.container()
    with col_der:
        if "panel_der" not in st.session_state:
            st.session_state["panel_der"] = None

        def _abrir_panel_der(pid: str):
            if st.session_state.get("panel_der") == pid:
                st.session_state["panel_der"] = None
            else:
                st.session_state["panel_der"] = pid

        # id del panel → etiqueta del botón (key Streamlit único por id)
        _ATAJOS_DER = (
            ("db", "Base de datos", "nav_der_db"),
            ("hist", "Historial de sellos", "nav_der_hist"),
            ("seg", "Seguridad", "nav_der_seg"),
            ("ecc", "Criptografía", "nav_der_ecc"),
        )

        _p = st.session_state.get("panel_der")
        for _pid, _label, _key in _ATAJOS_DER:
            if st.button(
                _label,
                key=_key,
                type="primary" if _p == _pid else "secondary",
                use_container_width=True,
            ):
                _abrir_panel_der(_pid)
                st.rerun()

        # —— Panel: Base de datos (solo DB / KPI) ——
        if st.session_state.get("panel_der") == "db":
            with st.container(border=True):
                st.markdown(
                    '<p class="sb-card-title">Infraestructura</p>'
                    '<p class="sb-card-heading">Estado de base de datos</p>',
                    unsafe_allow_html=True,
                )

                _sb_url, _sb_key, _sb_err = None, None, None
                try:
                    _sb_url, _sb_key, _sb_err = funciones._supabase_config()
                except Exception as _e_sb:
                    _sb_err = str(_e_sb)

                if _sb_url and _sb_key and not _sb_err:
                    st.markdown(
                        '<span class="sb-pill ok">Supabase conectado</span>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"""
                        <div class="sb-status-row"><span>Proyecto</span><span>{(_sb_url or "")[:36]}…</span></div>
                        <div class="sb-status-row"><span>Tabla sellos</span><span>historial_reportes</span></div>
                        <div class="sb-status-row"><span>API key</span><span>configurada</span></div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<span class="sb-pill warn">Supabase no configurado</span>',
                        unsafe_allow_html=True,
                    )
                    if _sb_err:
                        st.caption(str(_sb_err)[:180])

                st.markdown(
                    f"""
                    <div class="sb-status-row"><span>SQLite local</span><span>planta_calidad_prod.db</span></div>
                    <div class="sb-status-row"><span>Último POST sello</span>
                    <span>{"OK" if (st.session_state.get("ultimo_supabase") or {}).get("ok") else (st.session_state.get("ultimo_supabase") or {}).get("mensaje", "—")[:40]}</span></div>
                    """,
                    unsafe_allow_html=True,
                )

                ultimo_hash = st.session_state.get("ultimo_hash_reporte")
                if ultimo_hash:
                    st.caption(f"Último hash de sesión: `{str(ultimo_hash)[:20]}…`")

                _kpi = st.session_state.get("kpi_archivo") or {}
                if _kpi:
                    st.markdown("---")
                    st.markdown(
                        '<p class="sb-card-title">Archivo activo</p>',
                        unsafe_allow_html=True,
                    )
                    st.metric("Total registros", _kpi.get("filas", "—"))
                    st.metric("Campos vacíos", _kpi.get("errores", "—"))
                    st.metric(
                        "Confiabilidad",
                        f"{_kpi.get('porcentaje', '—')}%",
                        delta=_kpi.get("motor", ""),
                    )
                    if _kpi.get("historial"):
                        with st.expander("Historial de cargas (SQLite)"):
                            st.dataframe(
                                pd.DataFrame(_kpi["historial"]),
                                width="stretch",
                                hide_index=True,
                            )

        # —— Panel: Criptografía (solo ECC) ——
        if st.session_state.get("panel_der") == "ecc":
            with st.container(border=True):
                st.markdown(
                    '<p class="sb-card-title">Criptografía</p>'
                    '<p class="sb-card-heading">Verificación ECC</p>',
                    unsafe_allow_html=True,
                )

                try:
                    _modo_ecc = motor_planta.modo_firma_activo()
                    _backend_ecc = motor_planta.motor_activo()
                    _diag_ecc = motor_planta.diagnostico()
                    _pub_oficial = motor_planta.llave_publica_oficial_hex()
                except Exception:
                    _modo_ecc, _backend_ecc, _diag_ecc, _pub_oficial = "n/d", "n/d", "n/d", None

                if _modo_ecc == "real":
                    st.markdown(
                        '<span class="sb-pill ok">Ed25519 real</span>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<span class="sb-pill warn">Modo demo / revisión</span>',
                        unsafe_allow_html=True,
                    )

                _backend_ui = _backend_ecc
                if _modo_ecc == "real" and str(_backend_ecc) in ("python", "n/d"):
                    _backend_ui = "rust" if motor_planta.rust_disponible() else _backend_ecc

                st.markdown(
                    f"""
                    <div class="sb-status-row"><span>Modo firma</span><span>{_modo_ecc}</span></div>
                    <div class="sb-status-row"><span>Backend</span><span>{_backend_ui}</span></div>
                    """,
                    unsafe_allow_html=True,
                )
                if _pub_oficial:
                    st.caption(f"Llave pública oficial: `{_pub_oficial[:16]}…`")
                    st.caption(
                        "La llave de secrets ya está activa. El sello del PDF se firmará "
                        "con ella al generar el reporte."
                    )
                st.caption(f"Diagnóstico: {_diag_ecc}")
                st.caption(
                    "PDF firmado: use **Verificación pública ECC** en la barra de navegación."
                )

        # —— Panel: Historial de sellos ——
        if st.session_state.get("panel_der") == "hist":
            with st.container(border=True):
                st.markdown(
                    '<p class="sb-card-title">SQLite · Sellos firmados</p>'
                    '<p class="sb-card-heading">Historial de reportes</p>',
                    unsafe_allow_html=True,
                )
                st.caption("Fecha, lote, hash y responsable de cada sello ECC.")
                historial_reportes = funciones.cargar_historial_reportes_db(200)
                _n_hist = len(historial_reportes) if historial_reportes else 0
                st.markdown(
                    f'<div class="sb-status-row"><span>Registros</span><span>{_n_hist}</span></div>',
                    unsafe_allow_html=True,
                )
                if historial_reportes:
                    df_hist = pd.DataFrame(historial_reportes)
                    _cols_pref = [
                        c
                        for c in (
                            "Fecha",
                            "fecha_hora",
                            "Lote",
                            "lote",
                            "Hash",
                            "hash_sha256",
                            "Responsable",
                            "responsable",
                            "Archivo",
                            "archivo",
                        )
                        if c in df_hist.columns
                    ]
                    df_show = df_hist[_cols_pref].copy() if _cols_pref else df_hist
                    for _hc in ("Hash", "hash_sha256"):
                        if _hc in df_show.columns:
                            df_show[_hc] = df_show[_hc].astype(str).str.slice(0, 12) + "…"
                    st.dataframe(df_show, width="stretch", hide_index=True, height=280)
                    if st.session_state.get("ultimo_hash_reporte"):
                        st.caption(
                            f"Último hash sesión: "
                            f"`{str(st.session_state['ultimo_hash_reporte'])[:20]}…`"
                        )
                else:
                    st.info("Sin reportes archivados. Genere un sello ECC al cargar un Excel.")

        # —— Contenido: Seguridad ——
        if st.session_state.get("panel_der") == "seg":
            with st.container(border=True):
                st.markdown(
                    '<p class="sb-card-title">Seguridad</p>'
                    '<p class="sb-card-heading">Cortafuego de planta</p>',
                    unsafe_allow_html=True,
                )
                _fw = firewall.resumen_panel(st.session_state)
                st.markdown(
                    '<span class="sb-pill ok">Firewall ON</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"""
                    <div class="sb-status-row"><span>Usuario sesión</span><span>{_fw.get('usuario')}</span></div>
                    <div class="sb-status-row"><span>Token</span><span>{_fw.get('token_corto')}</span></div>
                    <div class="sb-status-row"><span>Timeout</span><span>{_fw.get('timeout_min')} min</span></div>
                    <div class="sb-status-row"><span>Max login fails</span><span>{_fw.get('max_intentos')}</span></div>
                    <div class="sb-status-row"><span>Upload máx.</span><span>{_fw.get('max_upload_mb')} MB</span></div>
                    """,
                    unsafe_allow_html=True,
                )
                _ev = firewall.ultimos_eventos(5)
                if _ev:
                    with st.expander("Últimos eventos de seguridad"):
                        for e in _ev:
                            import html as _html

                            fecha = _html.escape(str(e.get("fecha") or "—"))
                            evento = _html.escape(str(e.get("evento") or "—"))
                            sev = _html.escape(str(e.get("severidad") or "info"))
                            det = _html.escape(str(e.get("detalle") or "").strip())
                            st.markdown(
                                f"""
                                <div class="fw-event-row">
                                  <div class="fw-event-time">{fecha}</div>
                                  <div class="fw-event-main">
                                    <span class="fw-event-name">{evento}</span>
                                    <span class="fw-event-sev">{sev}</span>
                                  </div>
                                  <div class="fw-event-det">{det}</div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
