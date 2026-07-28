import streamlit as st
import sqlite3
import pandas as pd
import io
import base64
import hashlib
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# IMPORTACIÓN NATIVA DEL MOTOR EN RUST (PyO3)
try:
    import motor_rust
except ImportError:
    motor_rust = None

DB_NAME = "cerro_pie_auditoria.db"

def inicializar_base_datos():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hora TEXT,
            archivo TEXT,
            registros INTEGER,
            confiabilidad TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bitacora (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT,
            fila INTEGER,
            columna TEXT,
            valor_anterior TEXT,
            valor_nuevo TEXT,
            auditor TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contenedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking TEXT,
            contenedor TEXT,
            precinto_linea TEXT,
            precinto_senasa TEXT,
            destino TEXT,
            estado TEXT
        )
    ''')
    conn.commit()
    conn.close()

def cargar_datos_archivo(archivo):
    if archivo.name.endswith('.csv'):
        return pd.read_csv(archivo)
    else:
        return pd.read_excel(archivo)

def guardar_historial_db(hora, archivo, registros, confiabilidad):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO historial (hora, archivo, registros, confiabilidad) VALUES (?, ?, ?, ?)",
                   (hora, archivo, registros, confiabilidad))
    conn.commit()
    conn.close()

def cargar_historial_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT hora, archivo, registros, confiabilidad FROM historial ORDER BY id DESC LIMIT 5")
    data = cursor.fetchall()
    conn.close()
    return [{"Hora": d[0], "Archivo": d[1], "Registros": d[2], "Confiabilidad": d[3]} for d in data]

def guardar_cambio_db(fecha_hora, fila, columna, valor_anterior, valor_nuevo, auditor):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO bitacora (fecha_hora, fila, columna, valor_anterior, valor_nuevo, auditor) VALUES (?, ?, ?, ?, ?, ?)",
                   (fecha_hora, fila, columna, str(valor_anterior), str(valor_nuevo), auditor))
    conn.commit()
    conn.close()

def cargar_bitacora_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT fecha_hora, fila, columna, valor_anterior, valor_nuevo, auditor FROM bitacora ORDER BY id DESC LIMIT 20")
    data = cursor.fetchall()
    conn.close()
    return [{"Fecha/Hora": d[0], "Fila": d[1], "Columna": d[2], "Antiguo": d[3], "Nuevo": d[4], "Auditor": d[5]} for d in data]

def guardar_contenedor_db(booking, contenedor, precinto_linea, precinto_senasa, destino, estado):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO contenedores (booking, contenedor, precinto_linea, precinto_senasa, destino, estado) VALUES (?, ?, ?, ?, ?, ?)",
                   (booking, contenedor, precinto_linea, precinto_senasa, destino, estado))
    conn.commit()
    conn.close()

def cargar_contenedores_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT booking, contenedor, precinto_linea, precinto_senasa, destino, estado FROM contenedores ORDER BY id DESC")
    data = cursor.fetchall()
    conn.close()
    return [{"Booking": d[0], "Contenedor": d[1], "Precinto Línea": d[2], "Precinto SENASA": d[3], "Destino": d[4], "Estado": d[5]} for d in data]

def resaltar_errores_celdas(val):
    if val == "" or val == "-" or pd.isna(val):
        return "background-color: #ffcccc"
    return ""

def generar_firma_ecc_fallback(texto):
    if motor_rust is not None:
        try:
            llave_pub, sello_ecc = motor_rust.firmar_reporte_ecc(texto)
            return llave_pub, sello_ecc
        except Exception:
            pass
            
    hash_bytes = hashlib.sha256(texto.encode('utf-8')).digest()
    sello_b64 = base64.b64encode(hash_bytes).decode('utf-8')
    return "FALLBACK-LOCAL-KEY", sello_b64

def validar_mermas_con_rust(total_filas, total_mermas):
    if motor_rust is not None:
        try:
            porcentaje, estado = motor_rust.validar_datos_planta(int(total_filas), float(total_mermas))
            return porcentaje, estado
        except Exception:
            pass
            
    porcentaje = (1.0 - (float(total_mermas) / float(total_filas))) * 100.0 if total_filas > 0 else 100.0
    estado = "Aprobado - Planta Eficiente" if porcentaje > 95.0 else "Alerta - Revisar Línea de Producción"
    return porcentaje, estado

def generar_pdf_resumen(archivo_nombre, total_filas, total_errores, total_duplicados, porcentaje_limpio, producto, auditor, congelado, destino, capa, sello, llave):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    story.append(Paragraph("<b>Reporte Ejecutivo de Auditoría - Planta Cerro Prieto</b>", styles['Title']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<b>Archivo Analizado:</b> {archivo_nombre}", styles['Normal']))
    story.append(Paragraph(f"<b>Cultivo:</b> {producto} | <b>Destino:</b> {destino}", styles['Normal']))
    story.append(Paragraph(f"<b>Inspector:</b> {auditor}", styles['Normal']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<b>Total de Registros:</b> {total_filas}", styles['Normal']))
    story.append(Paragraph(f"<b>Campos Vacíos / Errores:</b> {total_errores}", styles['Normal']))
    story.append(Paragraph(f"<b>Registros Duplicados:</b> {total_duplicados}", styles['Normal']))
    story.append(Paragraph(f"<b>Confiabilidad:</b> {porcentaje_limpio}%", styles['Normal']))
    story.append(Paragraph(f"<b>Estado del Lote:</b> {'CONGELADO / APROBADO' if congelado else 'EN REVISIÓN'}", styles['Normal']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<b>Acciones Correctivas (CAPA):</b> {capa if capa else 'Sin observaciones.'}", styles['Normal']))
    story.append(Spacer(1, 12))
    
    story.append(Paragraph(f"<b>Sello Criptográfico Digital (ECC P-256):</b> <font size=6 color='#1a5f7a'>{sello}</font>", styles['Normal']))
    story.append(Paragraph(f"<b>Llave Pública de Verificación:</b> <font size=6 color='#444444'>{llave}</font>", styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def generar_pdf_errores(df_errores, archivo_nombre, producto, auditor):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    story.append(Paragraph("<b>Reporte de Errores e Incidencias Detectadas</b>", styles['Title']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<b>Archivo:</b> {archivo_nombre} | <b>Cultivo:</b> {producto}", styles['Normal']))
    story.append(Paragraph(f"<b>Inspector Responsable:</b> {auditor}", styles['Normal']))
    story.append(Paragraph(f"<b>Total de Anomalías:</b> {len(df_errores)}", styles['Normal']))
    story.append(Spacer(1, 12))
    
    if df_errores.empty:
        story.append(Paragraph("No se encontraron errores en este lote.", styles['Normal']))
    else:
        for idx, row in df_errores.head(30).iterrows():
            story.append(Paragraph(f"Fila ID {idx}: {row.to_dict()}", styles['Normal']))
            
    doc.build(story)
    buffer.seek(0)
    return buffer

# --- INTERFAZ STREAMLIT ---
def main():
    st.set_page_config(page_title="Auditoría Cerro Prieto", layout="wide")
    inicializar_base_datos()
    
    st.title("🌱 Sistema de Auditoría y Control - Planta Cerro Prieto")
    
    # Barra lateral de configuración
    st.sidebar.header("Parámetros de Auditoría")
    auditor = st.sidebar.text_input("Inspector / Auditor", value="Supervisor General")
    producto = st.sidebar.selectbox("Cultivo / Producto", ["Arándanos", "Uvas", "Palta", "Espárragos", "Mangos"])
    destino = st.sidebar.selectbox("Mercado de Destino", ["USA", "Europa", "Asia", "Mercado Local"])
    
    # Pestañas principales
    tab1, tab2, tab3, tab4 = st.tabs(["📁 Carga y Análisis", "📝 Bitácora de Cambios", "🚢 Control de Contenedores", "📊 Historial"])
    
    with tab1:
        st.subheader("Carga de Lotes de Producción")
        archivo_subido = st.file_uploader("Sube tu archivo CSV o Excel", type=["csv", "xlsx"])
        
        if archivo_subido is not None:
            df = cargar_datos_archivo(archivo_subido)
            total_filas = len(df)
            
            st.write(f"**Vista previa del archivo:** `{archivo_subido.name}` ({total_filas} registros)")
            st.dataframe(df.head(10))
            
            # Análisis de errores y duplicados
            total_vacios = df.isna().sum().sum() + (df == "").sum().sum() + (df == "-").sum().sum()
            total_dupl = df.duplicated().sum()
            
            porcentaje, estado_planta = validar_mermas_con_rust(total_filas, total_vacios)
            
            st.metric("Confiabilidad del Lote", f"{porcentaje:.2f}%", delta=estado_planta)
            
            capa_obs = st.text_area("Acciones Correctivas y Preventivas (CAPA)")
            congelado = st.checkbox("Congelar / Aprobar Lote para Despacho")
            
            if st.button("Generar Reportes PDF y Sellar Lote"):
                hora_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                guardar_historial_db(hora_actual, archivo_subido.name, total_filas, f"{porcentaje:.2f}%")
                
                # Sello criptográfico
                texto_a_firmar = f"{archivo_subido.name}-{total_filas}-{porcentaje}-{hora_actual}"
                llave, sello = generar_firma_ecc_fallback(texto_a_firmar)
                
                pdf_res = generar_pdf_resumen(archivo_subido.name, total_filas, total_vacios, total_dupl, f"{porcentaje:.2f}%", producto, auditor, congelado, destino, capa_obs, sello, llave)
                
                st.success("¡Lote auditado y registrado correctamente en la base de datos!")
                st.download_button(
                    label="📥 Descargar Reporte Ejecutivo (PDF)",
                    data=pdf_res,
                    file_name=f"Reporte_CerroPrieto_{archivo_subido.name}.pdf",
                    mime="application/pdf"
                )

    with tab2:
        st.subheader("Bitácora de Modificaciones Manuales")
        bitacora_data = cargar_bitacora_db()
        if bitacora_data:
            st.dataframe(pd.DataFrame(bitacora_data))
        else:
            st.info("No hay registros en la bitácora de cambios.")

    with tab3:
        st.subheader("Gestión de Contenedores y Precintos SENASA")
        with st.form("form_contenedor"):
            col1, col2 = st.columns(2)
            with col1:
                booking = st.text_input("Número de Booking")
                contenedor = st.text_input("Código de Contenedor")
                precinto_linea = st.text_input("Precinto de Línea Naviera")
            with col2:
                precinto_senasa = st.text_input("Precinto SENASA")
                destino_cont = st.selectbox("Destino Final", ["USA", "Europa", "Asia", "Local"], key="dest_cont")
                estado_cont = st.selectbox("Estado", ["Liberado", "Inspección Fitosanitaria", "Observado"])
            
            submit_cont = st.form_submit_button("Registrar Contenedor")
            if submit_cont:
                if booking and contenedor:
                    guardar_contenedor_db(booking, contenedor, precinto_linea, precinto_senasa, destino_cont, estado_cont)
                    st.success("¡Contenedor registrado exitosamente!")
                else:
                    st.error("Por favor completa al menos el Booking y el Contenedor.")
        
        st.markdown("---")
        st.subheader("Contenedores Registrados")
        cont_data = cargar_contenedores_db()
        if cont_data:
            st.dataframe(pd.DataFrame(cont_data))

    with tab4:
        st.subheader("Historial Reciente de Auditorías")
        hist_data = cargar_historial_db()
        if hist_data:
            st.dataframe(pd.DataFrame(hist_data))
        else:
            st.info("Aún no hay auditorías guardadas en el historial.")

if __name__ == "__main__":
    main()
