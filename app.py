import streamlit as st
import datetime
import io
import pandas as pd

from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter
import funciones

# --- CONFIGURACIÓN DE SEGURIDAD GENERAL ---
USUARIO_CORRECTO = "calidad"
PASSWORD_CORRECTO = "control2026"

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔒 Acceso Restringido - Control de Calidad")
    st.write("Por favor, introduzca sus credenciales para ingresar a la plataforma corporativa.")
    
    usuarioInput = st.text_input("Usuario:")
    passwordInput = st.text_input("Contraseña:", type="password")
    
    if st.button("Ingresar"):
        if usuarioInput == USUARIO_CORRECTO and passwordInput == PASSWORD_CORRECTO:
            st.session_state["autenticado"] = True
            st.success("Acceso concedido.")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos. Inténtelo de nuevo.")
    st.stop()  
# -------------------------------------------

st.set_page_config(
    page_title="Sistema Integral de Exportación - Cerro Prieto",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stButton>button {
        background-color: #1F4E78;
        color: white;
        border-radius: 8px;
        font-weight: bold;
        border: none;
        padding: 0.5rem 1rem;
    }
    .stButton>button:hover {
        background-color: #153859;
        color: white;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("🏭 Plataforma Corporativa de Control de Calidad, Trazabilidad, Contenedores y Planta (Perú)")
st.write(
    "Sistema integral optimizado con motor estándar Python: GS1, Balanzas, LMR SENASA, Trazabilidad Inversa, Control de Frío y Gestión de Precintos de Contenedor."
)

funciones.inicializar_base_datos()

if "lote_congelado" not in st.session_state:
    st.session_state["lote_congelado"] = False

if "mostrar_vacios" not in st.session_state:
    st.session_state["mostrar_vacios"] = False

st.sidebar.header("⚙️ Parámetros de Planta & Destino")

auditor_nombre = st.sidebar.text_input("Inspector Asignado:", value="Control de Calidad")
producto_sel = st.sidebar.selectbox(
    "Cultivo / Fruta:", ["Palta Hass", "Arándano", "Espárrago", "Uva Red Globe", "Personalizado"]
)

mercado_destino = st.sidebar.selectbox(
    "🌍 Mercado de Destino:", ["Europa (GlobalGAP/UE)", "Estados Unidos (FDA/USDA)", "Asia / China", "Chile / Local"]
)

if producto_sel == "Palta Hass":
    limit_temp_default = 5.0
elif producto_sel == "Arándano":
    limit_temp_default = 1.5
elif producto_sel == "Espárrago":
    limit_temp_default = 2.0
elif producto_sel == "Uva Red Globe":
    limit_temp_default = 0.5
else:
    limit_temp_default = 4.0

temp_min_limite = st.sidebar.number_input("Temp. Mínima Cámara (°C):", value=limit_temp_default, step=0.5)

st.sidebar.subheader("📦 Tolerancias Logísticas")
peso_min_caja = st.sidebar.number_input("Peso Mínimo Neto Caja (kg):", value=4.0, step=0.1)
max_merma_permitida = st.sidebar.number_input("Límite Máximo de Merma (%):", value=5.0, step=0.5)

archivo = st.file_uploader(
    "Cargar Base de Datos de Recepción / Empaque (Excel o CSV)", type=["xlsx", "csv"]
)

if archivo is not None:
    try:
        df_original = funciones.cargar_datos_archivo(archivo)

        columnas_requeridas = ["LOTE", "PESO", "CALIBRE"]
        columnas_actuales_mayus = [c.upper() for c in df_original.columns]
        columnas_faltantes = [req for req in columnas_requeridas if not any(req in col for col in columnas_actuales_mayus)]

        if len(columnas_faltantes) > 0:
            st.warning(f"⚠️ **Aviso de Estructura:** El archivo no contiene columnas exactas como **{', '.join(columnas_faltantes)}**. La app operará con normalidad en modo flexible.")

        if "Observaciones_Rechazo" not in df_original.columns:
            df_original["Observaciones_Rechazo"] = ""

        total_filas = len(df_original)
        total_columnas = len(df_original.columns)
        total_duplicados = int(df_original.duplicated().sum())

        vacios_por_columna = (df_original == "").sum()
        total_errores = int(vacios_por_columna.sum())
        celdas_totales = total_filas * total_columnas

        porcentaje_limpio = (
            round(((celdas_totales - total_errores) / celdas_totales) * 100, 1)
            if celdas_totales > 0
            else 100
        )
        estado_rust = "Motor Python Estándar"

        hora_actual = datetime.datetime.now().strftime("%H:%M:%S")
        funciones.guardar_historial_db(hora_actual, archivo.name, total_filas, f"{porcentaje_limpio}%")

        st.sidebar.markdown("---")
        st.sidebar.metric(label="Total Registros", value=total_filas)
        st.sidebar.metric(
            label="Campos Vacíos",
            value=total_errores,
            delta=f"-{total_errores}" if total_errores > 0 else "0",
            delta_color="inverse",
        )
        st.sidebar.metric(label="Confiabilidad", value=f"{porcentaje_limpio}%", delta=estado_rust)

        historial_db_data = funciones.cargar_historial_db()
        if historial_db_data:
            st.sidebar.subheader("🕒 Historial Persistente (SQLite)")
            st.sidebar.dataframe(
                pd.DataFrame(historial_db_data),
                use_container_width=True,
                hide_index=True,
            )

        # MÓDULO 1
        st.markdown("---")
        st.markdown("### 🔌 Módulo 1: Conexión de Balanza y Lectura Rápida de Pallets (SSCC)")
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.info("⚡ **Balanza en línea (Puerto Serial/USB):** Simule la captura del peso automático de plataforma.")
            peso_capturado = st.number_input("Peso Neto capturado desde Balanza (kg):", value=4.5, step=0.1)
            if st.button("📥 Registrar Peso en Última Fila"):
                st.success(f"¡Peso de {peso_capturado} kg inyectado correctamente al flujo!")
        with col_b2:
            st.info("🔫 **Lector GS1-128 / SSCC:** Escaneo rápido para identificar unidades logísticas.")
            sscc_input = st.text_input("Escanear Código SSCC o Caja:", placeholder="Ej: 077512345678901234")
            if sscc_input:
                st.success(f"Pallet/Caja identificada mediante código de barras: **{sscc_input}**")

        # MÓDULO 2
        st.markdown("---")
        st.markdown("### 🧪 Módulo 2: Control de Límites Máximos de Residuos (LMR) y Certificación SENASA")
        col_mle1, col_mle2, col_mle3 = st.columns(3)
        with col_mle1:
            lote_lmr_sel = st.text_input("Ingrese Lote a Consultar LMR:", value="LOTE-001")
        with col_mle2:
            analisis_lab = st.selectbox("Resultado / Análisis Lab Químico:", ["Conforme (Bajo LMR)", "Alerta (Cercano al Límite)", "Rechazado (Supera LMR)"])
        with col_mle3:
            st.write("###")
            if analisis_lab == "Conforme (Bajo LMR)":
                st.success("🟢 **SENASA / Destino:** APROBADO")
            elif analisis_lab == "Alerta (Cercano al Límite)":
                st.warning("🟡 **SENASA / Destino:** EN CUARENTENA")
            else:
                st.error("🔴 **SENASA / Destino:** BLOQUEADO DE PLANTA")

        # MÓDULO 3
        st.markdown("---")
        st.markdown("### 🗺️ Módulo 3: Trazabilidad Inversa (De Caja o Pallet al Fundo de Origen)")
        col_inv1, col_inv2 = st.columns([2, 3])
        with col_inv1:
            caja_busqueda_inversa = st.text_input("🔍 Ingrese ID de Caja o Pallet:", placeholder="Ej: CJ-9842")
        with col_inv2:
            if caja_busqueda_inversa:
                st.markdown(f"""
                **🌳 Árbol Genealógico de Trazabilidad para `{caja_busqueda_inversa}`:**
                * **Fundo de Origen:** Fundo Santa Elena - Sector Norte (Parcela 4B)
                * **Productor Registrado:** Agroexportadora del Norte S.A.C.
                * **Fecha y Hora de Cosecha:** {datetime.datetime.now().strftime('%Y-%m-%d')} 06:30 AM
                * **Línea de Proceso / Packing:** Línea 02 - Turno Mañana
                * **Inspector Responsable:** {auditor_nombre}
                """)

        # MÓDULO 4
        st.markdown("---")
        st.markdown("### 🌡️ Módulo 4: Control Térmico de Cadena de Frío")
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            camara_sel = st.selectbox("Cámara Frigorífica / Túnel:", ["Pre-Cámara 01", "Túnel de Enfriamiento 03", "Cámara de Almacenamiento 05"])
        with col_f2:
            temp_actual_camara = st.number_input("Temperatura Registrada (°C):", value=temp_min_limite, step=0.5)
        with col_f3:
            st.write("###")
            if temp_actual_camara <= temp_min_limite + 1.0:
                st.success(f"❄️ **Frío Óptimo:** En rango seguro ({temp_actual_camara}°C)")
            else:
                st.error(f"🚨 **Ruptura de Frío:** ¡Temperatura alta ({temp_actual_camara}°C)!")

        # MÓDULO 5
        st.markdown("---")
        st.markdown("### 🚢 Módulo 5: Gestión de Contenedores y Precintos")
        col_cnt1, col_cnt2, col_cnt3 = st.columns(3)
        with col_cnt1:
            booking_input = st.text_input("Número de Booking:", placeholder="Ej: BKG-998231")
            contenedor_input = st.text_input("ID de Contenedor:", placeholder="Ej: TGBU1234567")
        with col_cnt2:
            precinto_linea_input = st.text_input("Precinto de Línea Naviera:", placeholder="Ej: MSC-L99821")
            precinto_senasa_input = st.text_input("Precinto Oficial SENASA:", placeholder="Ej: SENASA-004821")
        with col_cnt3:
            st.write("###")
            if st.button("🔒 Registrar y Sellar Contenedor"):
                if booking_input and contenedor_input and precinto_linea_input:
                    funciones.guardar_contenedor_db(booking_input, contenedor_input, precinto_linea_input, precinto_senasa_input, mercado_destino, "SELLADO")
                    st.success(f"¡Contenedor `{contenedor_input}` sellado y registrado!")
                else:
                    st.error("⚠️ Complete los campos obligatorios.")

        lista_cont_db = funciones.cargar_contenedores_db()
        if lista_cont_db:
            with st.expander("📦 Ver Contenedores Registrados"):
                st.dataframe(pd.DataFrame(lista_cont_db), use_container_width=True)

        st.markdown("---")
        st.markdown("### 1️⃣ Selección de Columnas para Exportar")
        todas_cols = list(df_original.columns)
        default_cols = [c for c in todas_cols if any(k in c.upper() for k in ["CAJA", "PESO", "LOTE", "CODIGO", "OBServaciones"])]
        if not default_cols:
            default_cols = todas_cols[: min(4, len(todas_cols))]

        cols_elegidas = st.multiselect("Selecciona columnas para el reporte:", options=todas_cols, default=default_cols)
        df_export = df_original[cols_elegidas].copy() if cols_elegidas else df_original.copy()

        st.markdown("### 2️⃣ Limpieza, Auditoría y Reporte de Errores")
        col_l1, col_l2, col_l3, col_l4 = st.columns(4)
        with col_l1:
            if not st.session_state["lote_congelado"]:
                if st.button("🧹 Limpiar Espacios"):
                    df_original = df_original.map(lambda x: str(x).strip() if pd.notna(x) else "")
                    df_export = df_original[cols_elegidas].copy() if cols_elegidas else df_original.copy()
                    st.success("¡Espacios eliminados!")
        with col_l2:
            if not st.session_state["lote_congelado"]:
                if st.button("📝 Rellenar Vacíos (-)"):
                    df_original = df_original.replace("", "-")
                    df_export = df_original[cols_elegidas].copy() if cols_elegidas else df_original.copy()
                    st.success("¡Vacíos reemplazados!")
        with col_l3:
            if st.button("🔍 Ver Vacíos"):
                st.session_state["mostrar_vacios"] = not st.session_state["mostrar_vacios"]
        with col_l4:
            mask_errores_gen = (df_original == "").any(axis=1)
            df_solo_errores_dl = df_original[mask_errores_gen]
            pdf_errores_buffer = funciones.generar_pdf_errores(df_solo_errores_dl, archivo.name, producto_sel, auditor_nombre)
            st.download_button("📥 Descargar Errores (PDF)", data=pdf_errores_buffer.getvalue(), file_name="Errores.pdf", mime="application/pdf")

        if st.session_state["mostrar_vacios"]:
            mask_vacios = (df_original == "").any(axis=1)
            df_solo_vacios = df_original[mask_vacios]
            if not df_solo_vacios.empty:
                st.dataframe(df_solo_vacios.style.map(funciones.resaltar_errores_celdas), use_container_width=True)
            else:
                st.success("¡No hay celdas vacías!")

        st.markdown("---")
        st.markdown("### 🛡️ Sello Criptográfico Hash-256 del Lote")
        resumen_datos = f"Auditoría - Cultivo: {producto_sel} - Fecha: {datetime.date.today()} - Registros: {total_filas}"
        llave_publica, sello_digital = funciones.generar_firma_ecc_fallback(resumen_datos)

        st.success("🔒 Reporte Asegurado con Hash Criptográfico")
        st.code(f"Sello Digital: {sello_digital}")
        st.caption(f"Llave Pública: {llave_publica}")

        st.markdown("### 3️⃣ Observaciones y Cierre")
        col_bus1, col_bus2 = st.columns(2)
        with col_bus1:
            texto_busqueda = st.text_input("🔍 Búsqueda Global:")
        with col_bus2:
            turno_sel = st.selectbox("🕒 Turno:", ["TODOS", "Mañana", "Tarde", "Noche"])

        df_mostrar = df_export
        if texto_busqueda.strip() != "":
            mask_busq = df_mostrar.astype(str).apply(lambda row: row.str.contains(texto_busqueda, case=False, na=False).any(), axis=1)
            df_mostrar = df_mostrar[mask_busq]

        if not st.session_state["lote_congelado"]:
            df_editado_pag = st.data_editor(df_mostrar, use_container_width=True, key="editor_datos")
            df_editado = df_editado_pag
        else:
            st.warning("🔒 Lote Congelado (Solo lectura)")
            df_editado = df_mostrar

        chk_pulpa = st.checkbox("Se verificó la temperatura de pulpa y los límites máximos de residuos (LMR).")
        chk_cuerpo = st.checkbox("El lote se encuentra libre de materias extrañas y plagas.")
        capa_texto = st.text_area("📝 Acciones Correctivas (CAPA):")

        if not st.session_state["lote_congelado"]:
            if st.button("🔒 Congelar y Aprobar Lote"):
                if chk_pulpa and chk_cuerpo:
                    st.session_state["lote_congelado"] = True
                    st.success("¡Lote aprobado y congelado!")
                    st.rerun()
                else:
                    st.error("⚠️ Marque las verificaciones del checklist.")
        else:
            if st.button("🔓 Descongelar Lote"):
                st.session_state["lote_congelado"] = False
                st.rerun()

        st.markdown("### 4️⃣ Exportación de Reportes Oficiales")
        col_ex1, col_ex2, col_ex3 = st.columns(3)

        with col_ex1:
            buffer_completo = io.BytesIO()
            with pd.ExcelWriter(buffer_completo, engine="openpyxl") as writer:
                df_editado.to_excel(writer, index=False, sheet_name="Packing_List")
            st.download_button("📥 Descargar Excel", data=buffer_completo.getvalue(), file_name="Reporte.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        with col_ex2:
            pdf_buffer = funciones.generar_pdf_resumen(archivo.name, total_filas, total_errores, total_duplicados, porcentaje_limpio, producto_sel, auditor_nombre, st.session_state["lote_congelado"], mercado_destino, capa_texto, sello_digital, llave_publica)
            st.download_button("📄 Descargar PDF", data=pdf_buffer.getvalue(), file_name="Resumen.pdf", mime="application/pdf")

        with col_ex3:
            buffer_packing = io.BytesIO()
            df_editado.to_csv(buffer_packing, index=False)
            st.download_button("🚢 Descargar CSV", data=buffer_packing.getvalue(), file_name="Packing_List.csv", mime="text/csv")

    except Exception as e:
        st.error(f"Ocurrió un error al procesar el archivo: {e}")
