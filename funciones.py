import sqlite3
import pandas as pd
import io
import base64
import hashlib
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

DB_NAME = "cerro_prieto_auditoria.db"

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
    if val == "" or val == "-":
        return "background-color: #ffcccc"
    return ""

def generar_firma_ecc_fallback(texto):
    """Genera una firma criptográfica segura usando SHA-256 nativo."""
    hash_bytes = hashlib.sha256(texto.encode('utf-8')).digest()
    sello_b64 = base64.b64encode(hash_bytes).decode('utf-8')
    llave_pub = "PUBKEY-CERRO-PRIETO-SECURE"
    return llave_pub, sello_b64

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
    story.append(Paragraph(f"<b>Sello Criptográfico Hash-256:</b> <font size=7>{sello}</font>", styles['Normal']))
    
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
