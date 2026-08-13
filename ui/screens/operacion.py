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


def render(
    *,
    archivo,
    modulo_nav: str,
    auditor_nombre: str,
    producto_sel: str,
    mercado_destino: str,
    peso_min_caja,
    max_merma_permitida,
    temp_min_limite,
    temp_max_limite,
    es_supervisor: bool,
    nombre_planta: str,
):
    try:
        df_original = st.session_state["df_trabajo"]
        archivo_nombre = st.session_state.get("nombre_archivo") or (archivo.name if archivo is not None else "lote.csv")
        # compat: código legacy usa archivo.name
        class _ArchivoProxy:
            def __init__(self, name):
                self.name = name
        archivo = archivo if archivo is not None else _ArchivoProxy(archivo_nombre)
        if "mapeo_columnas_manual" not in st.session_state:
            st.session_state["mapeo_columnas_manual"] = {}
        cols_traza = funciones.resolver_mapa_columnas(
            df_original,
            st.session_state.get("mapeo_columnas_manual"),
        )

        columnas_faltantes = funciones.campos_criticos_sin_mapear(cols_traza)

        if len(columnas_faltantes) > 0:
            st.warning(
                f"Faltan columnas clave: **{', '.join(columnas_faltantes)}**. "
                "Asigne el mapeo abajo o continue en modo flexible."
            )
        else:
            st.caption(
                "Columnas clave: "
                + " · ".join(
                    f"{k.upper()}→`{cols_traza[k]}`"
                    for k in ("lote", "peso", "calibre")
                    if cols_traza.get(k)
                )
            )

        with st.expander("Mapear columnas del packing", expanded=bool(columnas_faltantes)):
            st.caption("Si el Excel usa otros nombres, elija la columna real de cada campo.")
            opts_base = ["(auto)", "(ninguna)"] + [str(c) for c in df_original.columns]
            manual_prev = dict(st.session_state.get("mapeo_columnas_manual") or {})
            nuevo_manual = {}
            grid = st.columns(3)
            for i, campo in enumerate(funciones.CAMPOS_MAPEO_UI):
                with grid[i % 3]:
                    actual = manual_prev.get(campo)
                    if actual and actual in opts_base:
                        idx = opts_base.index(actual)
                    elif cols_traza.get(campo) and cols_traza[campo] in opts_base:
                        # mostrar auto detectado como selección visual en (auto)
                        idx = 0
                    else:
                        idx = 0
                    elegido = st.selectbox(
                        campo.replace("_", " ").title(),
                        opts_base,
                        index=idx,
                        key=f"map_col_{campo}",
                    )
                    if elegido == "(auto)":
                        nuevo_manual.pop(campo, None)
                    else:
                        nuevo_manual[campo] = elegido
            bmap1, bmap2 = st.columns(2)
            with bmap1:
                if st.button("Aplicar mapeo", type="primary", key="btn_aplicar_mapeo"):
                    st.session_state["mapeo_columnas_manual"] = {
                        k: v for k, v in nuevo_manual.items() if v not in (None, "", "(auto)")
                    }
                    st.success("Mapeo aplicado.")
                    st.rerun()
            with bmap2:
                if st.button("Restablecer auto", key="btn_reset_mapeo"):
                    st.session_state["mapeo_columnas_manual"] = {}
                    for _c in funciones.CAMPOS_MAPEO_UI:
                        st.session_state.pop(f"map_col_{_c}", None)
                    st.rerun()

        if "Observaciones_Rechazo" not in df_original.columns:
            df_original["Observaciones_Rechazo"] = ""
            st.session_state["df_trabajo"] = df_original

        total_filas = len(df_original)
        total_columnas = len(df_original.columns)
        total_duplicados = int(df_original.duplicated().sum())

        vacios_por_columna = (df_original == "").sum()
        total_errores = int(vacios_por_columna.sum())

        celdas_totales = total_filas * total_columnas
    
        try:
            eficiencia_rust, estado_rust = motor_planta.validar_datos_planta(
                float(total_filas), float(total_errores)
            )
            porcentaje_limpio = round(eficiencia_rust, 1)
            estado_rust = f"{estado_rust} [{motor_planta.motor_activo()}]"
        except Exception:
            porcentaje_limpio = (
                round(((celdas_totales - total_errores) / celdas_totales) * 100, 1)
                if celdas_totales > 0
                else 100
            )
            estado_rust = "Motor Python Respaldo"

        hora_actual = datetime.datetime.now().strftime("%H:%M:%S")
        funciones.guardar_historial_db(hora_actual, archivo.name, total_filas, f"{porcentaje_limpio}%")

        st.session_state["kpi_archivo"] = {
            "filas": total_filas,
            "errores": total_errores,
            "porcentaje": porcentaje_limpio,
            "motor": estado_rust,
            "historial": funciones.cargar_historial_db(),
            "archivo": archivo.name,
        }
        historial_db_data = st.session_state["kpi_archivo"]["historial"]

        pagina_ecc_style(
            modulo_nav,
            f"{archivo.name} · {total_filas} filas · {porcentaje_limpio}% limpio",
        )


        if modulo_nav == "Resumen del lote":
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Filas", total_filas)
            c2.metric("Columnas", total_columnas)
            c3.metric("Duplicados", total_duplicados)
            c4.metric("Confiabilidad", f"{porcentaje_limpio}%")
            with st.expander("Vista previa", expanded=False):
                st.dataframe(df_original.head(30), width="stretch", hide_index=True)
            if st.button("Alertas", key="btn_resumen_a_m7"):
                st.session_state["vista_planta"] = "operacion"
                st.session_state["modulo_nav"] = "7 · Alertas y tendencias"
                st.rerun()
            if st.button("Cierre", key="btn_resumen_a_cierre"):
                st.session_state["vista_planta"] = "operacion"
                st.session_state["modulo_nav"] = "Limpieza y cierre"
                st.rerun()


        if modulo_nav == "1 · Balanza / SSCC":
            # MÓDULO 1
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if "balanza_peso_input" not in st.session_state:
                    st.session_state["balanza_peso_input"] = 4.5
                peso_capturado = st.number_input(
                    "Peso neto (kg)",
                    step=0.1,
                    key="balanza_peso_input",
                )
                with st.expander("Balanza USB / serial", expanded=False):
                    st.caption(
                        "En PC local con pyserial. En Streamlit Cloud use captura manual."
                    )
                    puertos = funciones.listar_puertos_serial()
                    puerto = st.selectbox(
                        "Puerto",
                        options=(puertos or ["COM3", "/dev/ttyUSB0"]),
                        key="balanza_puerto",
                    )
                    baud = st.number_input("Baudrate", value=9600, step=100, key="balanza_baud")
                    if st.button("Capturar desde balanza", key="balanza_capturar"):
                        lec = funciones.leer_peso_serial(str(puerto), baudrate=int(baud))
                        if lec.get("ok"):
                            st.session_state["balanza_peso_input"] = float(lec["peso"])
                            st.success(lec.get("mensaje"))
                            st.rerun()
                        else:
                            st.warning(lec.get("mensaje") or "Sin lectura")
                            if lec.get("crudo"):
                                st.code(lec["crudo"])
                if st.button("Registrar peso", type="primary"):
                    df_nuevo, ok_peso, col_peso_usada = funciones.registrar_peso_ultima_fila(
                        df_original, peso_capturado
                    )
                    if ok_peso:
                        st.session_state["df_trabajo"] = df_nuevo
                        df_original = df_nuevo
                        funciones.guardar_cambio_db(
                            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            len(df_original) - 1,
                            col_peso_usada,
                            "(balanza)",
                            str(peso_capturado),
                            auditor_nombre,
                        )
                        st.success(
                            f"Peso de {peso_capturado} kg registrado en la última fila "
                            f"(columna `{col_peso_usada}`)."
                        )
                        st.rerun()
                    else:
                        st.error(
                            "No se encontró una columna de PESO en el archivo, o el archivo está vacío."
                        )
            with col_b2:
                sscc_input = st.text_input("SSCC / caja / pallet", placeholder="077512345678901234")
                if sscc_input:
                    df_sscc = funciones.buscar_registros_por_codigo(df_original, sscc_input)
                    if df_sscc.empty:
                        st.error(f"Código `{sscc_input}` no encontrado en la base cargada.")
                    else:
                        st.success(f"Unidad encontrada: **{sscc_input}** ({len(df_sscc)} registro(s))")
                        st.dataframe(df_sscc, width="stretch", hide_index=True)


        if modulo_nav == "2 · LMR / SENASA":
            # MÓDULO 2
            lotes_disponibles = []
            if cols_traza["lote"]:
                lotes_disponibles = sorted(
                    [x for x in df_original[cols_traza["lote"]].astype(str).str.strip().unique() if x and x != "nan"]
                )
            lote_default = lotes_disponibles[0] if lotes_disponibles else ""
            col_mle1, col_mle2, col_mle3 = st.columns(3)
            with col_mle1:
                if lotes_disponibles:
                    lote_lmr_sel = st.selectbox("Lote a consultar LMR:", options=lotes_disponibles, index=0)
                else:
                    lote_lmr_sel = st.text_input("Ingrese Lote a Consultar LMR:", value=lote_default, placeholder="Ej: LOTE-001")
            with col_mle2:
                analisis_lab = st.selectbox(
                    "Resultado de laboratorio (manual / respaldo):",
                    ["Usar dato del archivo", "Conforme (Bajo LMR)", "Alerta (Cercano al Límite)", "Rechazado (Supera LMR)"],
                )
            with col_mle3:
                estado_lmr = "sin_dato"
                detalle_lmr = "Sin lote consultado"
                df_lote_lmr = pd.DataFrame()
                if lote_lmr_sel:
                    df_lote_lmr = funciones.buscar_registros_por_codigo(df_original, lote_lmr_sel)
                    if cols_traza["lote"] and df_lote_lmr.empty:
                        mask_lote = df_original[cols_traza["lote"]].astype(str).str.strip().str.fullmatch(
                            str(lote_lmr_sel).strip(), case=False, na=False
                        )
                        df_lote_lmr = df_original.loc[mask_lote].copy()

                    if analisis_lab != "Usar dato del archivo":
                        if "Conforme" in analisis_lab:
                            estado_lmr = "conforme"
                        elif "Alerta" in analisis_lab:
                            estado_lmr = "alerta"
                        else:
                            estado_lmr = "rechazado"
                        detalle_lmr = analisis_lab
                    elif not df_lote_lmr.empty and cols_traza["lmr"]:
                        valores_lmr = df_lote_lmr[cols_traza["lmr"]].astype(str).str.strip()
                        estados = [funciones.interpretar_estado_lmr(v) for v in valores_lmr if v and v != "nan"]
                        if "rechazado" in estados:
                            estado_lmr = "rechazado"
                        elif "alerta" in estados:
                            estado_lmr = "alerta"
                        elif "conforme" in estados:
                            estado_lmr = "conforme"
                        detalle_lmr = ", ".join(sorted(set(valores_lmr.head(5))))
                    elif df_lote_lmr.empty:
                        detalle_lmr = "Lote no encontrado en archivo"
                    else:
                        detalle_lmr = "Lote hallado, sin columna LMR; use el selector manual"

            if estado_lmr == "conforme":
                st.success("APROBADO")
            elif estado_lmr == "alerta":
                st.warning("EN CUARENTENA")
            elif estado_lmr == "rechazado":
                st.error("BLOQUEADO")
            else:
                st.info("Sin veredicto")
            if detalle_lmr:
                st.caption(detalle_lmr)

            if lote_lmr_sel and not df_lote_lmr.empty:
                with st.expander(f"Registros del lote `{lote_lmr_sel}` ({len(df_lote_lmr)})"):
                    st.dataframe(df_lote_lmr, width="stretch", hide_index=True)


        if modulo_nav == "3 · Trazabilidad":
            # MÓDULO 3
            col_inv1, col_inv2 = st.columns([2, 3])
            with col_inv1:
                caja_busqueda_inversa = st.text_input(
                    "Caja o pallet",
                    placeholder="CJ-9842 / SSCC / LOTE",
                )
                cols_detectadas = [f"`{v}` ({k})" for k, v in cols_traza.items() if v]
            with col_inv2:
                if caja_busqueda_inversa:
                    df_traza = funciones.buscar_registros_por_codigo(df_original, caja_busqueda_inversa)
                    if df_traza.empty:
                        st.error("No encontrado")
                    else:
                        arbol = funciones.armar_arbol_trazabilidad(
                            df_traza.iloc[0], cols_traza, auditor_nombre, caja_busqueda_inversa
                        )
                        st.markdown(
                            f"""
    **`{arbol['codigo']}`**

    - Fundo: {arbol['fundo']} · Productor: {arbol['productor']}
    - Lote: {arbol['lote']} · Turno: {arbol['turno']}
    - Cosecha: {arbol['cosecha']} · LMR: {arbol['lmr']}
    """
                        )
                        if len(df_traza) > 1:
                            st.dataframe(df_traza, width="stretch", hide_index=True)


        if modulo_nav == "4 · Cadena de frío":
            # MÓDULO 4
            t_min_f, t_max_f = funciones.obtener_rango_frio_fruta(
                producto_sel,
                temp_min_override=temp_min_limite,
                temp_max_override=temp_max_limite if producto_sel == "Personalizado" else temp_max_limite,
            )
            st.caption(f"{producto_sel}: {t_min_f}–{t_max_f} °C")

            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                camara_sel = st.selectbox(
                    "Cámara Frigorífica / Túnel:",
                    ["Pre-Cámara 01", "Túnel de Enfriamiento 03", "Cámara de Almacenamiento 05", "Contenedor Reefer Puerto"],
                )
            with col_f2:
                valor_temp_default = float(
                    max(t_min_f, min(limit_temp_default, t_max_f))
                )
                temp_actual_camara = st.number_input(
                    "Temperatura Registrada (°C):",
                    value=valor_temp_default,
                    step=0.5,
                    format="%.1f",
                )
            with col_f3:
                prev = funciones.validar_temperatura_fruta(
                    temp_actual_camara,
                    producto_sel,
                    temp_min_override=t_min_f,
                    temp_max_override=t_max_f,
                )
                if prev["en_rango"]:
                    st.success(
                        f"✅ En rango ({prev['temp_min']}–{prev['temp_max']} °C) · "
                        f"lectura {prev['temperatura']} °C"
                    )
                else:
                    st.error(
                        f"🚨 Fuera de rango ({prev['temp_min']}–{prev['temp_max']} °C) · "
                        f"lectura {prev['temperatura']} °C"
                    )

                if st.button("💾 Registrar lectura de frío"):
                    try:
                        resultado_frio = funciones.registrar_control_frio(
                            camara=camara_sel,
                            temperatura=float(temp_actual_camara),
                            producto=producto_sel,
                            inspector=auditor_nombre,
                            temp_min_override=t_min_f,
                            temp_max_override=t_max_f,
                        )
                        if resultado_frio["tipo_ui"] == "success":
                            st.success(resultado_frio["mensaje_ui"])
                        else:
                            st.error(resultado_frio["mensaje_ui"])
                            av = resultado_frio.get("aviso") or {}
                            if av.get("ok"):
                                st.warning(f"📲 {av.get('mensaje')}")
                            elif av.get("omitido"):
                                st.caption(av.get("mensaje") or "")
                            elif av.get("configurado") is False:
                                st.caption(
                                    "Avisos WA/email no configurados "
                                    "(secrets [avisos])."
                                )
                            elif av.get("mensaje"):
                                st.caption(av.get("mensaje"))

                        if resultado_frio.get("sqlite_ok"):
                            pass
                        else:
                            st.warning(resultado_frio.get("sqlite_msg", "Error SQLite"))

                        sb_f = resultado_frio.get("supabase") or {}
                        if sb_f.get("ok"):
                            pass
                        elif sb_f.get("configurado") is False:
                            pass
                        else:
                            st.error(sb_f.get("mensaje") or "Error Supabase")
                    except Exception as e:
                        st.error(e)

            historial_frio = funciones.cargar_frio_db()
            if historial_frio:
                with st.expander("Historial de control de frío (SQLite)"):
                    st.dataframe(pd.DataFrame(historial_frio), width="stretch", hide_index=True)


        if modulo_nav == "7 · Alertas y tendencias":
            # MÓDULO 7 — con packing cargado (frío + patrones del lote)
            render_modulo_alertas_tendencias(
                df_packing=df_original,
                cols_mapa=cols_traza,
                peso_min_caja=peso_min_caja,
                max_merma_permitida=max_merma_permitida,
                key_prefix="m7_packing",
            )


        if modulo_nav == "Limpieza y cierre":
            st.subheader("Columnas a exportar")
            todas_cols = list(df_original.columns)

            default_cols = [
                c for c in todas_cols if any(k in c.upper() for k in ["CAJA", "PESO", "LOTE", "CODIGO", "OBServaciones"])
            ]
            if not default_cols:
                default_cols = todas_cols[: min(4, len(todas_cols))]

            cols_elegidas = st.multiselect(
                "Selecciona las columnas que formarán parte del Packing List y Reporte Final:",
                options=todas_cols,
                default=default_cols,
            )

            df_export = df_original[cols_elegidas].copy() if cols_elegidas else df_original.copy()

            st.subheader("Limpieza, auditoría y errores")
            col_l1, col_l2, col_l3, col_l4 = st.columns([1, 1, 1, 1])
            with col_l1:
                if not st.session_state["lote_congelado"]:
                    if st.button("🧹 Limpiar Espacios Ocultos"):
                        df_original = df_original.map(lambda x: str(x).strip() if pd.notna(x) else "")
                        df_export = df_original[cols_elegidas].copy() if cols_elegidas else df_original.copy()
                        st.success("¡Espacios eliminados!")
            with col_l2:
                if not st.session_state["lote_congelado"]:
                    if st.button("📝 Rellenar Vacíos con (-)"):
                        df_original = df_original.replace("", "-")
                        df_export = df_original[cols_elegidas].copy() if cols_elegidas else df_original.copy()
                        st.success("¡Vacíos reemplazados!")
            with col_l3:
                if st.button("🔍 Ver Registros con Vacíos"):
                    st.session_state["mostrar_vacios"] = not st.session_state["mostrar_vacios"]
            with col_l4:
                mask_errores_gen = (df_original == "").any(axis=1)
                col_peso_chk_aux = [c for c in df_original.columns if "PESO" in c.upper()]
                if col_peso_chk_aux:
                    pesos_num_aux = pd.to_numeric(df_original[col_peso_chk_aux[0]], errors="coerce")
                    mask_errores_gen = mask_errores_gen | (pesos_num_aux < peso_min_caja)
        
                df_solo_errores_dl = df_original[mask_errores_gen]
                pdf_errores_buffer = funciones.generar_pdf_errores(df_solo_errores_dl, archivo.name, producto_sel, auditor_nombre)
        
                st.download_button(
                    label="📥 Descargar Solo Errores (PDF)",
                    data=pdf_errores_buffer.getvalue(),
                    file_name="Reporte_Errores_Planta.pdf",
                    mime="application/pdf",
                )

            if st.session_state["mostrar_vacios"]:
                st.warning("⚠️ **Mostrando únicamente filas que contienen campos vacíos o incompletos:**")
                mask_vacios = (df_original == "").any(axis=1)
                df_solo_vacios = df_original[mask_vacios]
                if not df_solo_vacios.empty:
                    st.dataframe(df_solo_vacios.style.map(funciones.resaltar_errores_celdas), use_container_width=True)
                else:
                    st.success("¡Excelente! No hay registros con celdas vacías en este archivo.")

            st.subheader("Control de calidad y estadísticas")
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_pallet_chk = [c for c in df_original.columns if "PALLET" in c.upper()]
            total_pallets = df_original[col_pallet_chk[0]].nunique() if col_pallet_chk else "N/D"
    
            col_lote_chk = [c for c in df_original.columns if "LOTE" in c.upper()]
            total_lotes = df_original[col_lote_chk[0]].nunique() if col_lote_chk else "N/D"

            col_prod_chk = [c for c in df_original.columns if "PRODUCTOR" in c.upper()]
            total_productores = df_original[col_prod_chk[0]].nunique() if col_prod_chk else "N/D"

            with col_m1:
                st.metric("Total Pallets (SSCC)", total_pallets)
            with col_m2:
                st.metric("Lotes en Proceso", total_lotes)
            with col_m3:
                st.metric("Productores Implicados", total_productores)
            with col_m4:
                st.metric("Duplicados Detectados", total_duplicados)

            col_peso_chk = [c for c in df_original.columns if "PESO" in c.upper()]
            if col_peso_chk:
                pesos_num = pd.to_numeric(df_original[col_peso_chk[0]], errors="coerce")
                cajas_livianas = (pesos_num < peso_min_caja).sum()
                peso_promedio = round(pesos_num.mean(), 2) if not pesos_num.empty else 0
                peso_std = round(pesos_num.std(), 2) if not pesos_num.empty else 0
                st.caption(f"Peso medio {peso_promedio} kg · σ {peso_std}")

                if cajas_livianas > 0:
                    st.error(f"⚠️ **Alerta Crítica de Pesaje:** Se encontraron {cajas_livianas} registros por debajo del peso mínimo de {peso_min_caja} kg.")

            col1, col2 = st.columns(2)
            with col1:
                col_calibre = [c for c in df_original.columns if "CALIBRE" in c.upper()]
                if col_calibre:
                    conteo_calibres = df_original[col_calibre[0]].value_counts().reset_index()
                    conteo_calibres.columns = ["Calibre", "Cajas"]
                    st.caption("Calibres")
                    st.dataframe(conteo_calibres.T, use_container_width=True)
                
                    st.bar_chart(conteo_calibres.set_index("Calibre"))

            with col2:
                col_cat = [c for c in df_original.columns if "CATEGORIA" in c.upper() or "CAT" in c.upper()]
                if col_cat:
                    conteo_cat = df_original[col_cat[0]].value_counts()
                    descarte = conteo_cat.get("DESCARTE", 0) + conteo_cat.get("MERMA", 0)
                    porcentaje_merma = round((descarte / total_filas) * 100, 2)

                    if porcentaje_merma > max_merma_permitida:
                        st.error(f"🚨 **Alerta de Merma Elevada:** {porcentaje_merma}% de descarte (Límite: {max_merma_permitida}%).")
                    else:
                        st.success(f"✅ **Merma Bajo Control:** {porcentaje_merma}% de descarte.")

            st.markdown("---")
            st.subheader("Sello criptográfico ECC del lote")
            resumen_datos = f"Auditoría de Planta - Cultivo: {producto_sel} - Fecha: {datetime.date.today()} - Registros: {total_filas}"

            try:
                # Reutilizar el mismo sello en reruns de Streamlit
                cache_sello = st.session_state.get("cache_sello_ecc")
                if (
                    not cache_sello
                    or cache_sello.get("mensaje") != resumen_datos
                    or cache_sello.get("archivo") != archivo.name
                    or cache_sello.get("algo") != "Ed25519"
                ):
                    llave_publica, sello_digital = motor_planta.firmar_reporte_ecc(resumen_datos)
                    st.session_state["cache_sello_ecc"] = {
                        "mensaje": resumen_datos,
                        "archivo": archivo.name,
                        "llave_publica": llave_publica,
                        "sello_digital": sello_digital,
                        "modo": motor_planta.modo_firma_activo(),
                        "backend": motor_planta.motor_activo(),
                        "algo": "Ed25519",
                    }
                else:
                    llave_publica = cache_sello["llave_publica"]
                    sello_digital = cache_sello["sello_digital"]

                modo = st.session_state["cache_sello_ecc"].get("modo") or motor_planta.modo_firma_activo()
                backend = st.session_state["cache_sello_ecc"].get("backend") or motor_planta.motor_activo()
                if modo == "real":
                    st.success(f"🔒 Sello real Ed25519 · secrets + backend `{backend}`")
                    if str(backend).startswith("python"):
                        st.caption("Motor Rust no activo; fallback Python (cryptography / PyNaCl / ed25519).")
                else:
                    st.warning(
                        "🧪 Modo demo: no se pudo usar `st.secrets['LLAVE_PRIVADA']`. "
                        "Se firmó con llave Ed25519 efímera."
                    )
                st.code(f"Sello Digital (Firma ECC): {sello_digital}")
                st.caption(f"Llave Pública de Verificación: {llave_publica}")
                st.caption(f"Modo de firma: `{modo}` · Backend: `{backend}`")
                st.caption(f"Diagnóstico: {motor_planta.diagnostico()}")

                # Lote(s) detectados en el archivo
                if cols_traza.get("lote"):
                    lotes_vals = [
                        v for v in df_original[cols_traza["lote"]].astype(str).str.strip().unique()
                        if v and v.lower() != "nan"
                    ]
                    if not lotes_vals:
                        lote_reporte = "SIN-LOTE"
                    elif len(lotes_vals) <= 3:
                        lote_reporte = ", ".join(lotes_vals)
                    else:
                        lote_reporte = f"{lotes_vals[0]} … (+{len(lotes_vals) - 1} lotes)"
                else:
                    lote_reporte = archivo.name

                hash_reporte = funciones.calcular_hash_reporte(
                    resumen_datos, sello_digital, llave_publica
                )
                fecha_firma = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                try:
                    resultado_hist = funciones.guardar_reporte_historico(
                        fecha_hora=fecha_firma,
                        lote=lote_reporte,
                        hash_sha256=hash_reporte,
                        responsable=auditor_nombre,
                        archivo=archivo.name,
                        producto=producto_sel,
                        registros=total_filas,
                        firma_ecc=sello_digital,
                        llave_publica=llave_publica,
                        mensaje=resumen_datos,
                        modo_firma=modo,
                        backend=backend,
                    )
                except Exception as e:
                    st.error(e)
                    resultado_hist = {"guardado": False, "supabase_detalle": {}}

                st.session_state["ultimo_hash_reporte"] = hash_reporte
                st.session_state["ultimo_supabase"] = resultado_hist.get("supabase_detalle") or {}

                if resultado_hist.get("guardado"):
                    st.info(
                        f"📂 Historial local: archivado (id `{resultado_hist.get('id')}`) · "
                        f"Hash `{hash_reporte[:16]}…`"
                    )
                elif resultado_hist.get("ya_existia"):
                    st.caption(
                        f"📂 Historial local: sello ya registrado (hash `{hash_reporte[:16]}…`)"
                    )

                # --- Envío explícito a Supabase (también reintenta si el guardado falló en remoto) ---
                try:
                    sb = resultado_hist.get("supabase_detalle") or {}
                    # Reintento directo para forzar POST solo con fecha/lote/hash_sha256/inspector
                    if not sb.get("ok"):
                        sb = funciones.enviar_sello_a_supabase(
                            fecha=fecha_firma,
                            lote=lote_reporte,
                            hash_sha256=hash_reporte,
                            inspector=auditor_nombre,
                        )
                        st.session_state["ultimo_supabase"] = sb

                    if sb.get("ok"):
                        if sb.get("ya_existia") or sb.get("status") == 409:
                            st.info(
                                "☁️ Supabase · sello **ya registrado** (hash único). "
                                "No es un error — no se duplicó el registro."
                            )
                        else:
                            st.success(
                                f"☁️ Supabase OK · public.historial_reportes · {sb.get('mensaje', '')}"
                            )
                        with st.expander("Detalle payload Supabase"):
                            st.json(sb.get("payload") or {})
                            st.caption(f"Endpoint: `{sb.get('endpoint')}` · HTTP {sb.get('status')}")
                    else:
                        msg = sb.get("mensaje") or "Error desconocido al insertar en Supabase"
                        st.error(msg)
                        with st.expander("Detalle del error Supabase"):
                            st.write(f"Configurado: {sb.get('configurado')}")
                            st.write(f"HTTP status: {sb.get('status')}")
                            st.write(f"Endpoint: {sb.get('endpoint')}")
                            st.json(sb.get("payload") or {})
                except Exception as e:
                    st.error(e)
            except Exception as e:
                llave_publica = "LLAVE_NO_DISPONIBLE"
                sello_digital = "SELLO_NO_DISPONIBLE"
                st.error(f"No se pudo generar el sello criptográfico: {e}")
                st.caption(f"Diagnóstico: {motor_planta.diagnostico()}")

            st.subheader("Observaciones de turno, edición y cierre")
            col_bus1, col_bus2, col_bus3 = st.columns(3)
            with col_bus1:
                texto_busqueda = st.text_input("🔍 Búsqueda Global (Lote/Contenedor):")
            with col_bus2:
                if col_prod_chk:
                    lista_prod = ["TODOS"] + list(df_original[col_prod_chk[0]].unique())
                    prod_filtro_sel = st.selectbox("🎯 Filtrar por Productor:", lista_prod)
                else:
                    prod_filtro_sel = "TODOS"
            with col_bus3:
                turno_sel = st.selectbox("🕒 Filtrar por Turno de Trabajo:", ["TODOS", "Mañana (06:00 - 14:00)", "Tarde (14:00 - 22:00)", "Noche (22:00 - 06:00)"])

            df_mostrar = df_export
            if texto_busqueda.strip() != "":
                mask_busq = df_mostrar.astype(str).apply(
                    lambda row: row.str.contains(texto_busqueda, case=False, na=False).any(),
                    axis=1,
                )
                df_mostrar = df_mostrar[mask_busq]

            if col_prod_chk and prod_filtro_sel != "TODOS":
                mask_prod = df_original[col_prod_chk[0]] == prod_filtro_sel
                indices_validos = df_original[mask_prod].index
                df_mostrar = df_mostrar.loc[df_mostrar.index.isin(indices_validos)]

            TAMANO_PAGINA = 100
            total_registros_visibles = len(df_mostrar)
    
            if total_registros_visibles > TAMANO_PAGINA:
                total_paginas = (total_registros_visibles // TAMANO_PAGINA) + (1 if total_registros_visibles % TAMANO_PAGINA > 0 else 0)
                pagina_actual = st.number_input("Página de visualización:", min_value=1, max_value=total_paginas, step=1)
                inicio = (pagina_actual - 1) * TAMANO_PAGINA
                fin = inicio + TAMANO_PAGINA
                df_paginado = df_mostrar.iloc[inicio:fin]
                st.caption(f"Mostrando registros {inicio + 1} al {min(fin, total_registros_visibles)} de un total de {total_registros_visibles} filtrados.")
            else:
                df_paginado = df_mostrar

            if st.session_state["lote_congelado"]:
                st.warning("🔒 **Lote Congelado:** La tabla está en modo solo lectura. Para editar, desbloquee el lote abajo.")
                df_editado = df_mostrar
            else:
                df_editado_pag = st.data_editor(df_paginado, use_container_width=True, key="editor_datos_pag")
        
                df_editado = df_mostrar.copy()
                if total_registros_visibles > TAMANO_PAGINA:
                    df_editado.iloc[inicio:fin] = df_editado_pag
                else:
                    df_editado = df_editado_pag

                def _valores_iguales(valor_original, valor_nuevo):
                    if pd.isna(valor_original) and pd.isna(valor_nuevo):
                        return True
                    return str(valor_original).strip() == str(valor_nuevo).strip()

                for i in range(len(df_mostrar)):
                    fila_indice = df_mostrar.index[i]
                    for col in df_mostrar.columns:
                        val_orig = df_mostrar.iloc[i][col]
                        val_nuevo = df_editado.iloc[i][col]
                        if not _valores_iguales(val_orig, val_nuevo):
                            fecha_hora_cambio = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            funciones.guardar_cambio_db(
                                fecha_hora_cambio,
                                int(fila_indice) if isinstance(fila_indice, (int, float)) and not pd.isna(fila_indice) else i,
                                col,
                                val_orig,
                                val_nuevo,
                                auditor_nombre,
                            )

            st.markdown("#### ✅ Verificaciones Fitosanitarias Obligatorias")
            chk_pulpa = st.checkbox("Se verificó la temperatura de pulpa y los límites máximos de residuos (LMR).")
            chk_cuerpo = st.checkbox("El lote se encuentra libre de materias extrañas y plagas cuarentenarias exigidas por SENASA.")
    
            capa_texto = st.text_area("📝 Registro General de Acciones Correctivas (CAPA) / Resumen de Incidencias:", placeholder="Escribir observaciones generales de turno...")

            col_c1, col_c2 = st.columns(2)
            with col_c1:
                if not st.session_state["lote_congelado"]:
                    if es_supervisor:
                        if st.button("🔒 Congelar y Aprobar Lote (Cierre Oficial)"):
                            if chk_pulpa and chk_cuerpo:
                                st.session_state["lote_congelado"] = True
                                try:
                                    csv_bytes = funciones.exportar_packing_csv_bytes(df_original)
                                    st.session_state["packing_csv_erp"] = csv_bytes
                                    st.session_state["packing_csv_nombre"] = (
                                        f"packing_ERP_{archivo.name.rsplit('.', 1)[0]}.csv"
                                    )
                                except Exception:
                                    st.session_state["packing_csv_erp"] = None
                                st.success(
                                    "¡Lote aprobado y congelado! CSV listo para ERP abajo."
                                )
                                st.rerun()
                            else:
                                st.error(
                                    "⚠️ Debe marcar todas las verificaciones del checklist "
                                    "obligatorio antes de aprobar el lote."
                                )
                    else:
                        st.caption("Congelar/aprobar: solo supervisor.")
                else:
                    if es_supervisor:
                        if st.button("🔓 Descongelar Lote (Habilitar Edición)"):
                            st.session_state["lote_congelado"] = False
                            st.session_state.pop("packing_csv_erp", None)
                            st.warning("Lote habilitado para modificaciones.")
                            st.rerun()
                    else:
                        st.caption("Lote congelado. Solo un supervisor puede descongelarlo.")

            if st.session_state.get("lote_congelado") and st.session_state.get("packing_csv_erp"):
                st.download_button(
                    "Descargar packing limpio (CSV ERP)",
                    data=st.session_state["packing_csv_erp"],
                    file_name=st.session_state.get("packing_csv_nombre") or "packing_ERP.csv",
                    mime="text/csv",
                    key="dl_packing_erp_congelado",
                    type="primary",
                )

            bitacora_db_data = funciones.cargar_bitacora_db()
            if bitacora_db_data:
                with st.expander("📜 Ver Bitácora de Auditoría Persistente (SQLite Audit Trail)"):
                    st.dataframe(pd.DataFrame(bitacora_db_data), use_container_width=True)

            st.markdown("### 5️⃣ Exportación de Reportes Oficiales")
            col_ex1, col_ex2, col_ex3 = st.columns(3)

            with col_ex1:
                estado_lote = "CONGELADO / APROBADO" if st.session_state["lote_congelado"] else "EN REVISIÓN"
                df_resumen = pd.DataFrame({
                    "Parámetro de Control": [
                        "Fecha de Emisión",
                        "Cultivo Procesado",
                        "Mercado Destino",
                        "Total Registros Exportados",
                        "Errores Iniciales Detectados",
                        "Confiabilidad del Proceso",
                        "Estado del Lote",
                        "Inspector Responsable",
                        "Planta",
                    ],
                    "Detalle": [
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        producto_sel,
                        mercado_destino,
                        total_filas,
                        total_errores,
                        f"{porcentaje_limpio}%",
                        estado_lote,
                        auditor_nombre,
                        nombre_planta or "Planta Autorizada",
                    ],
                })
                hojas_excel = {
                    "Packing_List": (
                        df_editado,
                        f"Packing List — {nombre_planta or 'Planta Autorizada'} | {producto_sel}",
                    ),
                    "Trazabilidad_Resumen": (
                        df_resumen,
                        f"Resumen de Trazabilidad — {archivo.name}",
                    ),
                }
                if bitacora_db_data:
                    hojas_excel["Audit_Trail"] = (
                        pd.DataFrame(bitacora_db_data),
                        "Bitácora de Auditoría (Audit Trail)",
                    )

                buffer_completo = funciones.generar_excel_corporativo(
                    hojas_excel,
                    titulo_general="Reporte Corporativo de Exportación",
                )
                st.download_button(
                    label="📥 Descargar Excel corporativo",
                    data=buffer_completo.getvalue(),
                    file_name="Reporte_Completo_Exportacion.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            with col_ex2:
                pdf_buffer = funciones.generar_pdf_resumen(
                    archivo.name,
                    total_filas,
                    total_errores,
                    total_duplicados,
                    porcentaje_limpio,
                    producto_sel,
                    auditor_nombre,
                    st.session_state["lote_congelado"],
                    mercado_destino,
                    capa_texto,
                    sello_digital,
                    llave_publica,
                    mensaje_firmado=resumen_datos,
                    planta_nombre=nombre_planta,
                )
                st.download_button(
                    label="📄 Descargar PDF Ejecutivo Firmado",
                    data=pdf_buffer.getvalue(),
                    file_name="Resumen_Ejecutivo_Firmado_ECC.pdf",
                    mime="application/pdf",
                )

            with col_ex3:
                buffer_packing = io.BytesIO()
                df_editado.to_csv(buffer_packing, index=False)
                st.download_button(
                    label="🚢 Descargar Packing List (CSV)",
                    data=buffer_packing.getvalue(),
                    file_name="Packing_List_Oficial.csv",
                    mime="text/csv",
                )

    except Exception as e:
        st.error(f"Ocurrió un error al procesar el archivo: {e}")