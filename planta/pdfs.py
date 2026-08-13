"""Generación y extracción de PDFs (resumen, errores, dashboard)."""
from __future__ import annotations

import datetime
import hashlib
import io
import json
import os
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from planta.db import calcular_hash_reporte
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
    planta_nombre="",
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
    
    sub_planta = f"<b>Planta:</b> {planta_nombre} | " if str(planta_nombre).strip() else ""
    sub = Paragraph(
        f"{sub_planta}<b>Producto:</b> {producto} | <b>Destino:</b> {mercado}<br/>"
        f"<b>Estado:</b> {estado_txt} | <b>Fecha:</b> {fecha_str}",
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
        f"[ECC_PUB]{llave_publica}[/ECC_PUB] "
        f"[ECC_HASH]{calcular_hash_reporte(mensaje_ref, firma_ECDSA, llave_publica)}[/ECC_HASH]"
    )
    sello_data = [
        [Paragraph("<b>Sello Criptográfico Ed25519:</b>", styles["Normal"])],
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


def generar_pdf_dashboard_turno(
    dash: dict,
    planta_nombre: str = "",
    inspector: str = "",
    rol: str = "",
    firma_ECDSA: str = "",
    llave_publica: str = "",
    mensaje_firmado: str = "",
):
    """PDF del dashboard de turno (KPIs + alertas). Con sello Ed25519 si hay firma."""
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
        "TituloDash",
        parent=styles["Heading1"],
        fontSize=15,
        textColor=colors.HexColor("#1F4E78"),
        spaceAfter=8,
    )
    story.append(Paragraph("<b>DASHBOARD DE TURNO — RESUMEN OPERATIVO</b>", titulo_estilo))

    fecha_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fecha_turno = dash.get("fecha") or fecha_str[:10]
    estado = dash.get("estado_turno") or "—"
    sub_bits = []
    if str(planta_nombre).strip():
        sub_bits.append(f"<b>Planta:</b> {planta_nombre}")
    sub_bits.append(f"<b>Turno:</b> {fecha_turno}")
    sub_bits.append(f"<b>Estado:</b> {estado}")
    if str(inspector).strip():
        sub_bits.append(f"<b>Emitido por:</b> {inspector}")
    if str(rol).strip():
        sub_bits.append(f"<b>Rol:</b> {rol}")
    sub_bits.append(f"<b>Generado:</b> {fecha_str}")
    story.append(Paragraph(" | ".join(sub_bits), styles["Normal"]))
    story.append(Spacer(1, 12))

    k = dash.get("kpis") or {}
    datos_kpi = [
        ["Indicador", "Valor"],
        ["Sellos ECC hoy", str(k.get("sellos_ecc", 0))],
        ["Lecturas de frío hoy", str(k.get("lecturas_frio", 0))],
        ["Rupturas de frío hoy", str(k.get("rupturas_frio", 0))],
        ["Contenedores (total)", str(k.get("contenedores", 0))],
        ["Cargas packing (sesión)", str(k.get("cargas_packing", 0))],
    ]
    t = Table(datos_kpi, colWidths=[260, 220])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#1F4E78")),
                ("TEXTCOLOR", (0, 0), (1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F2F2F2")),
                ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#D9D9D9")),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 14))

    af = dash.get("alertas_frio") or {}
    story.append(
        Paragraph(
            f"<b>Alertas de frío:</b> {af.get('mensaje') or 'Sin detalle'}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 6))
    activas = af.get("activas") or []
    if not activas:
        story.append(Paragraph("Sin rupturas activas en la ventana de alerta.", styles["Normal"]))
    else:
        filas_af = [["Cámara", "Temp.", "Producto", "Inspector", "Hora", "Estado"]]
        for a in activas[:20]:
            filas_af.append(
                [
                    str(a.get("camara") or "—")[:24],
                    str(a.get("temperatura") if a.get("temperatura") is not None else "—"),
                    str(a.get("producto") or "—")[:18],
                    str(a.get("inspector") or "—")[:18],
                    str(a.get("hora") or "—")[:19],
                    str(a.get("estado") or "—")[:22],
                ]
            )
        ta = Table(filas_af, colWidths=[75, 45, 70, 70, 85, 85])
        ta.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8B2942")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FFF5F5")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(ta)

    story.append(Spacer(1, 14))
    lotes = dash.get("lotes_sellados") or []
    story.append(Paragraph(f"<b>Sellos ECC del día ({len(lotes)}):</b>", styles["Normal"]))
    story.append(Spacer(1, 4))
    if not lotes:
        story.append(Paragraph("Aún no hay sellos archivados hoy.", styles["Normal"]))
    else:
        filas_l = [["Hora", "Lote", "Responsable", "Producto", "Registros"]]
        for L in lotes[:15]:
            filas_l.append(
                [
                    str(L.get("fecha_hora") or "—")[:19],
                    str(L.get("lote") or "—")[:20],
                    str(L.get("responsable") or "—")[:18],
                    str(L.get("producto") or "—")[:16],
                    str(L.get("registros") if L.get("registros") is not None else "—"),
                ]
            )
        tl = Table(filas_l, colWidths=[95, 90, 90, 85, 60])
        tl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F2F2F2")),
                ]
            )
        )
        story.append(tl)

    story.append(Spacer(1, 16))

    firma = str(firma_ECDSA or "").strip()
    pub = str(llave_publica or "").strip()
    if firma and pub:
        kpis = dash.get("kpis") or {}
        mensaje_ref = mensaje_firmado or (
            f"Dashboard turno {fecha_turno} | Planta: {planta_nombre or 'N/D'} | "
            f"Estado: {estado} | Rupturas: {kpis.get('rupturas_frio', 0)} | "
            f"Lecturas frío: {kpis.get('lecturas_frio', 0)} | "
            f"Sellos ECC: {kpis.get('sellos_ecc', 0)} | Emisor: {inspector or 'N/D'}"
        )
        bloque_verificacion = (
            f"[ECC_MSG]{mensaje_ref}[/ECC_MSG] "
            f"[ECC_SIG]{firma}[/ECC_SIG] "
            f"[ECC_PUB]{pub}[/ECC_PUB] "
            f"[ECC_HASH]{calcular_hash_reporte(mensaje_ref, firma, pub)}[/ECC_HASH]"
        )
        sello_data = [
            [Paragraph("<b>Sello Criptográfico Ed25519 (dashboard de turno):</b>", styles["Normal"])],
            [Paragraph(
                f"<font size=7 face='Courier'><b>Mensaje firmado:</b> {mensaje_ref}</font>",
                styles["Normal"],
            )],
            [Paragraph(
                f"<font size=7 face='Courier'><b>Firma:</b> {firma}</font>",
                styles["Normal"],
            )],
            [Paragraph(
                f"<font size=7 face='Courier'><b>Llave Pública:</b> {pub}</font>",
                styles["Normal"],
            )],
            [Paragraph(f"<font size=5 face='Courier'>{bloque_verificacion}</font>", styles["Normal"])],
            [Paragraph(
                "<i>Verifique este PDF en Verificación pública ECC. "
                "Si el contenido firmado fue alterado, la verificación fallará.</i>",
                styles["Normal"],
            )],
        ]
        tabla_sello = Table(sello_data, colWidths=[500])
        tabla_sello.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EDF2F7")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#1F4E78")),
                    ("PADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(tabla_sello)
    else:
        story.append(
            Paragraph(
                "<i>Documento sin sello Ed25519 (faltó LLAVE_PRIVADA o firma).</i>",
                styles["Normal"],
            )
        )

    doc.build(story)
    buffer.seek(0)
    return buffer

