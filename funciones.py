import io
import datetime
import sqlite3
import pandas as pd
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Alias de columnas frecuentes en packing lists agroindustriales
ALIAS_COLUMNAS = {
    "id_unidad": ["CAJA", "SSCC", "PALLET", "CODIGO", "BARCODE", "EAN", "GTIN", "ID"],
    "lote": ["LOTE"],
    "fundo": ["FUNDO", "PARCELA", "CAMPO", "ORIGEN", "SECTOR"],
    "productor": ["PRODUCTOR", "PROVEEDOR", "AGRICULTOR"],
    "turno": ["TURNO", "LINEA", "PROCESO", "PACKING"],
    "peso": ["PESO"],
    "cosecha": ["COSECHA", "HARVEST", "FECHA_COSECHA", "F_COSECHA"],
    "lmr": ["LMR", "RESIDUO", "ANALISIS", "FITOSANITARIO"],
    "calibre": ["CALIBRE"],
    "categoria": ["CATEGORIA", "CAT"],
}


def encontrar_columna(df, keywords):
    """Devuelve el nombre real de la primera columna cuyo nombre contenga alguno de los keywords."""
    for col in df.columns:
        col_up = str(col).upper()
        for kw in keywords:
            if kw.upper() in col_up:
                return col
    return None


def mapear_columnas_trazabilidad(df):
    return {clave: encontrar_columna(df, aliases) for clave, aliases in ALIAS_COLUMNAS.items()}


def _valor_celda(fila, col, default="N/D"):
    if col is None or col not in fila.index:
        return default
    val = fila[col]
    if pd.isna(val) or str(val).strip() in ("", "-"):
        return default
    return str(val).strip()


def buscar_registros_por_codigo(df, codigo):
    """Busca filas cuyo ID (caja/pallet/sscc/código) o cualquier celda coincida con el código."""
    codigo = str(codigo).strip()
    if not codigo or df.empty:
        return df.iloc[0:0].copy()

    cols_mapa = mapear_columnas_trazabilidad(df)
    cols_prioridad = [
        c for c in [
            cols_mapa["id_unidad"],
            cols_mapa["lote"],
            encontrar_columna(df, ["CONTENEDOR", "BOOKING"]),
        ] if c is not None
    ]
    # Evitar duplicados manteniendo orden
    cols_busqueda = list(dict.fromkeys(cols_prioridad + list(df.columns)))

    mask = pd.Series(False, index=df.index)
    for col in cols_busqueda:
        serie = df[col].astype(str).str.strip()
        mask = mask | serie.str.fullmatch(codigo, case=False, na=False)
        if mask.any():
            break

    if not mask.any():
        # Búsqueda parcial solo en columnas de identificación
        for col in cols_prioridad:
            serie = df[col].astype(str).str.strip()
            mask = mask | serie.str.contains(codigo, case=False, na=False, regex=False)

    return df.loc[mask].copy()


def armar_arbol_trazabilidad(fila, cols_mapa, inspector, codigo_buscado):
    """Construye un diccionario legible del árbol genealógico a partir de una fila real."""
    return {
        "codigo": codigo_buscado,
        "fundo": _valor_celda(fila, cols_mapa["fundo"], "No informado en archivo"),
        "productor": _valor_celda(fila, cols_mapa["productor"], "No informado en archivo"),
        "lote": _valor_celda(fila, cols_mapa["lote"]),
        "turno": _valor_celda(fila, cols_mapa["turno"], "No informado en archivo"),
        "cosecha": _valor_celda(fila, cols_mapa["cosecha"], "No informado en archivo"),
        "peso": _valor_celda(fila, cols_mapa["peso"]),
        "calibre": _valor_celda(fila, cols_mapa["calibre"]),
        "lmr": _valor_celda(fila, cols_mapa["lmr"], "Sin dato LMR en archivo"),
        "inspector": inspector,
        "fila_indice": int(fila.name) if fila.name is not None else None,
    }


def interpretar_estado_lmr(texto):
    """Clasifica un resultado LMR textual en conforme / alerta / rechazado."""
    t = str(texto).strip().upper()
    if not t or t in ("N/D", "-", "SIN DATO LMR EN ARCHIVO", "NAN"):
        return "sin_dato"
    if any(k in t for k in ["RECHAZ", "SUPERA", "FAIL", "NO CONFORME", "BLOQUE"]):
        return "rechazado"
    if any(k in t for k in ["ALERTA", "CERCANO", "CUARENTENA", "PENDIENTE", "WARNING"]):
        return "alerta"
    if any(k in t for k in ["CONFORME", "APROB", "OK", "BAJO", "PASS", "CUMPLE"]):
        return "conforme"
    return "sin_dato"


def registrar_peso_ultima_fila(df, peso):
    """Inyecta el peso capturado en la última fila de la columna PESO (si existe)."""
    df_out = df.copy()
    col_peso = encontrar_columna(df_out, ALIAS_COLUMNAS["peso"])
    if col_peso is None or df_out.empty:
        return df_out, False, col_peso
    df_out.iloc[-1, df_out.columns.get_loc(col_peso)] = str(peso)
    return df_out, True, col_peso


def inicializar_base_datos():
    conn = sqlite3.connect("calidad_cerroprieto_pro.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial_sesion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hora TEXT,
            archivo TEXT,
            registros INTEGER,
            confiabilidad TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bitacora_cambios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT,
            fila_indice INTEGER,
            columna TEXT,
            valor_anterior TEXT,
            nuevo_valor TEXT,
            inspector TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS control_frio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camara TEXT,
            temperatura REAL,
            hora_registro TEXT,
            estado TEXT,
            inspector TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contenedores_despacho (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking TEXT,
            contenedor TEXT,
            precinto_linea TEXT,
            precinto_senasa TEXT,
            destino TEXT,
            estado TEXT
        )
    """)
    # Migración suave si la tabla ya existía sin columna inspector
    try:
        cursor.execute("ALTER TABLE control_frio ADD COLUMN inspector TEXT")
    except sqlite3.OperationalError:
        pass
    cursor.execute("DELETE FROM bitacora_cambios WHERE datetime(fecha_hora) < datetime('now', '-7 days')")
    conn.commit()
    conn.close()

def guardar_historial_db(hora, archivo, registros, confiabilidad):
    conn = sqlite3.connect("calidad_cerroprieto_pro.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM historial_sesion WHERE archivo = ?", (archivo,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO historial_sesion (hora, archivo, registros, confiabilidad) VALUES (?, ?, ?, ?)",
                       (hora, archivo, registros, confiabilidad))
        conn.commit()
    conn.close()

def cargar_historial_db():
    conn = sqlite3.connect("calidad_cerroprieto_pro.db")
    df_db = pd.read_sql_query("SELECT hora AS Hora, archivo AS Archivo, registros AS Registros, confiabilidad AS Confiabilidad FROM historial_sesion", conn)
    conn.close()
    return df_db.to_dict("records")

def guardar_cambio_db(fecha_hora, fila_indice, columna, valor_anterior, nuevo_valor, inspector):
    conn = sqlite3.connect("calidad_cerroprieto_pro.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO bitacora_cambios (fecha_hora, fila_indice, columna, valor_anterior, nuevo_valor, inspector) VALUES (?, ?, ?, ?, ?, ?)",
                   (fecha_hora, fila_indice, columna, valor_anterior, nuevo_valor, inspector))
    conn.commit()
    conn.close()

def cargar_bitacora_db():
    conn = sqlite3.connect("calidad_cerroprieto_pro.db")
    df_bit = pd.read_sql_query("SELECT fecha_hora AS 'Fecha/Hora', fila_indice AS 'Fila Índice', columna AS 'Columna Modificada', valor_anterior AS 'Valor Anterior', nuevo_valor AS 'Nuevo Valor', inspector AS 'Inspector' FROM bitacora_cambios", conn)
    conn.close()
    return df_bit.to_dict("records")

def guardar_contenedor_db(booking, contenedor, p_linea, p_senasa, destino, estado):
    conn = sqlite3.connect("calidad_cerroprieto_pro.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO contenedores_despacho (booking, contenedor, precinto_linea, precinto_senasa, destino, estado) VALUES (?, ?, ?, ?, ?, ?)",
                   (booking, contenedor, p_linea, p_senasa, destino, estado))
    conn.commit()
    conn.close()

def cargar_contenedores_db():
    conn = sqlite3.connect("calidad_cerroprieto_pro.db")
    df_cont = pd.read_sql_query("SELECT booking AS 'Booking', contenedor AS 'Contenedor', precinto_linea AS 'Precinto Línea', precinto_senasa AS 'Precinto SENASA', destino AS 'Destino', estado AS 'Estado' FROM contenedores_despacho", conn)
    conn.close()
    return df_cont.to_dict("records")


def guardar_frio_db(camara, temperatura, hora_registro, estado, inspector):
    conn = sqlite3.connect("calidad_cerroprieto_pro.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO control_frio (camara, temperatura, hora_registro, estado, inspector) VALUES (?, ?, ?, ?, ?)",
        (camara, temperatura, hora_registro, estado, inspector),
    )
    conn.commit()
    conn.close()


def cargar_frio_db(limite=50):
    conn = sqlite3.connect("calidad_cerroprieto_pro.db")
    df_frio = pd.read_sql_query(
        """
        SELECT hora_registro AS 'Fecha/Hora', camara AS 'Cámara', temperatura AS 'Temp °C',
               estado AS 'Estado', COALESCE(inspector, '') AS 'Inspector'
        FROM control_frio
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(limite,),
    )
    conn.close()
    return df_frio.to_dict("records")

def cargar_datos_archivo(uploaded_file):
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file, dtype=str)
    else:
        df = pd.read_excel(uploaded_file, dtype=str)
    return df.map(lambda x: str(x).strip() if pd.notna(x) else "")

def resaltar_errores_celdas(val):
    val_str = str(val).strip()
    if val_str == "" or val_str == "-":
        return "background-color: #ffcccc; color: #990000; font-weight: bold;"
    return ""

def extraer_sello_ecc_pdf(pdf_bytes) -> dict:
    """
    Extrae mensaje firmado, firma y llave pública desde un PDF ejecutivo.
    Busca marcadores [ECC_*] y también etiquetas legibles Firma:/Llave Pública:.
    """
    import re
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    texto = "\n".join((page.extract_text() or "") for page in reader.pages)

    def _marker(tag):
        m = re.search(rf"\[{tag}\](.*?)\[/{tag}\]", texto, flags=re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else ""

    mensaje = _marker("ECC_MSG")
    firma = _marker("ECC_SIG")
    publica = _marker("ECC_PUB")

    if not mensaje:
        m = re.search(r"Mensaje firmado:\s*(.+)", texto, flags=re.IGNORECASE)
        if m:
            mensaje = m.group(1).strip()
    if not firma:
        m = re.search(r"Firma:\s*([0-9a-fA-F]+)", texto)
        if m:
            firma = m.group(1).strip()
    if not publica:
        m = re.search(r"Llave P[uú]blica:\s*([0-9a-fA-F]+)", texto, flags=re.IGNORECASE)
        if m:
            publica = m.group(1).strip()

    return {
        "mensaje": mensaje,
        "firma": "".join(firma.split()),
        "llave_publica": "".join(publica.split()),
        "texto_extraido": texto,
    }


def generar_pdf_resumen(
    archivo_nombre,
    total_filas,
    total_errores,
    duplicados,
    confiabilidad,
    producto,
    auditor,
    congelado_estado,
    mercado,
    capa_texto,
    firma_ECDSA,
    llave_publica,
    mensaje_firmado="",
):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )
    story = []
    styles = getSampleStyleSheet()

    titulo_estilo = ParagraphStyle(
        'TituloReporte',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1F4E78'),
        spaceAfter=10
    )

    title = Paragraph("<b>REPORTE EJECUTIVO DE AUDITORÍA Y TRAZABILIDAD AGROINDUSTRIAL</b>", titulo_estilo)
    story.append(title)
    story.append(Spacer(1, 5))

    fecha_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    estado_txt = "APROBADO Y CONGELADO" if congelado_estado else "EN EDICIÓN / REVISIÓN"
    
    sub = Paragraph(
        f"<b>Planta:</b> Cerro Prieto | <b>Producto:</b> {producto} | <b>Destino:</b> {mercado}<br/><b>Estado:</b> {estado_txt} | <b>Fecha:</b> {fecha_str}",
        styles["Normal"],
    )
    story.append(sub)
    story.append(Spacer(1, 10))

    datos_tabla = [
        ["Indicador de Control", "Valor Registrado"],
        ["Nombre del Archivo Base", archivo_nombre],
        ["Total Registros Auditados", str(total_filas)],
        ["Celdas Vacías / Errores Base", str(total_errores)],
        ["Registros Duplicados", str(duplicados)],
        ["Índice de Confiabilidad Inicial", f"{confiabilidad}%"],
        ["Responsable de Auditoría", auditor],
    ]

    t = Table(datos_tabla, colWidths=[220, 280])
    t.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#1F4E78")),
            ("TEXTCOLOR", (0, 0), (1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F2F2F2")),
            ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#D9D9D9")),
        ])
    )
    story.append(t)
    story.append(Spacer(1, 10))

    if capa_texto.strip() != "":
        capa_p = Paragraph(f"<b>Acción Correctiva (CAPA / Justificación):</b><br/>{capa_texto}", styles["Normal"])
        story.append(capa_p)
        story.append(Spacer(1, 10))

    mensaje_ref = mensaje_firmado or (
        f"Auditoría de Planta - Cultivo: {producto} - Fecha: {fecha_str[:10]} - Registros: {total_filas}"
    )
    # Marcadores machine-readable para verificación pública posterior
    bloque_verificacion = (
        f"[ECC_MSG]{mensaje_ref}[/ECC_MSG] "
        f"[ECC_SIG]{firma_ECDSA}[/ECC_SIG] "
        f"[ECC_PUB]{llave_publica}[/ECC_PUB]"
    )
    sello_data = [
        [Paragraph("<b>Sello Criptográfico de Curva Elíptica (ECC / P-256):</b>", styles["Normal"])],
        [Paragraph(f"<font size=7 face='Courier'><b>Mensaje firmado:</b> {mensaje_ref}</font>", styles["Normal"])],
        [Paragraph(f"<font size=7 face='Courier'><b>Firma:</b> {firma_ECDSA}</font>", styles["Normal"])],
        [Paragraph(f"<font size=7 face='Courier'><b>Llave Pública:</b> {llave_publica}</font>", styles["Normal"])],
        [Paragraph(f"<font size=5 face='Courier'>{bloque_verificacion}</font>", styles["Normal"])],
        [Paragraph(
            "<i>Verifique este PDF en la pestaña pública de la plataforma. "
            "Si el contenido firmado fue alterado, la verificación ECC fallará.</i>",
            styles["Normal"],
        )],
    ]
    
    tabla_sello = Table(sello_data, colWidths=[500])
    tabla_sello.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#EDF2F7')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#1F4E78')),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    
    story.append(tabla_sello)
    doc.build(story)
    buffer.seek(0)
    return buffer

def generar_pdf_errores(df_errores, archivo_nombre, producto, auditor):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20,
    )
    story = []
    styles = getSampleStyleSheet()

    title = Paragraph("<b>REPORTE DE REGISTROS CON ERRORES O FALTANTES EN PLANTA</b>", styles["Title"])
    story.append(title)
    story.append(Spacer(1, 5))

    fecha_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sub = Paragraph(
        f"<b>Archivo Base:</b> {archivo_nombre} | <b>Cultivo:</b> {producto}<br/><b>Inspector:</b> {auditor} | <b>Fecha de Emisión:</b> {fecha_str}",
        styles["Normal"],
    )
    story.append(sub)
    story.append(Spacer(1, 10))

    if df_errores.empty:
        story.append(Paragraph("<b>¡Excelente! No se encontraron registros con errores o celdas vacías.</b>", styles["Normal"]))
    else:
        cols_a_mostrar = list(df_errores.columns[:7])
        tabla_datos = [[Paragraph(f"<b>{c}</b>", styles["Normal"]) for c in cols_a_mostrar]]
        
        for _, row in df_errores.iterrows():
            fila_cells = [Paragraph(str(row[c]), styles["Normal"]) for c in cols_a_mostrar]
            tabla_datos.append(fila_cells)

        ancho_col = 572 / len(cols_a_mostrar)
        t = Table(tabla_datos, colWidths=[ancho_col] * len(cols_a_mostrar))
        t.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C00000")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F9F9F9")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
            ])
        )
        story.append(t)

    doc.build(story)
    buffer.seek(0)
    return buffer
