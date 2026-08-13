"""Informe semanal de planta (KPIs 7 días + PDF/email)."""
from __future__ import annotations

import datetime
import io

from planta.db import _conectar_db, inicializar_base_datos


def consolidar_informe_semanal(dias: int = 7) -> dict:
    """Agrega frío, sellos y contenedores de los últimos N días (SQLite)."""
    inicializar_base_datos()
    hoy = datetime.date.today()
    desde = hoy - datetime.timedelta(days=max(1, int(dias)) - 1)
    desde_s = desde.strftime("%Y-%m-%d")
    hasta_s = hoy.strftime("%Y-%m-%d")

    conn = _conectar_db()
    try:
        frio = conn.execute(
            """
            SELECT camara, temperatura, estado, producto, inspector, hora_registro
            FROM control_frio
            WHERE date(hora_registro) >= date(?)
            ORDER BY hora_registro DESC
            """,
            (desde_s,),
        ).fetchall()
        sellos = conn.execute(
            """
            SELECT fecha_hora, archivo, producto, responsable, hash_sha256
            FROM historial_reportes
            WHERE date(fecha_hora) >= date(?)
            ORDER BY fecha_hora DESC
            """,
            (desde_s,),
        ).fetchall()
        conts = conn.execute(
            """
            SELECT booking, contenedor, destino, estado, COALESCE(fecha, '')
            FROM contenedores_despacho
            WHERE fecha IS NULL OR fecha = '' OR date(fecha) >= date(?)
            ORDER BY id DESC
            """,
            (desde_s,),
        ).fetchall()
    finally:
        conn.close()

    lecturas = len(frio)
    rupturas = sum(1 for r in frio if "RUPTURA" in str(r[2] or "").upper())
    camaras = sorted({str(r[0]) for r in frio if r[0]})
    alertas = [
        {
            "camara": r[0],
            "temperatura": r[1],
            "estado": r[2],
            "producto": r[3],
            "inspector": r[4],
            "hora": r[5],
        }
        for r in frio
        if "RUPTURA" in str(r[2] or "").upper()
    ][:30]

    if rupturas >= 5:
        estado = "CRITICO"
    elif rupturas >= 1:
        estado = "VIGILANCIA"
    else:
        estado = "OK"

    return {
        "ok": True,
        "desde": desde_s,
        "hasta": hasta_s,
        "dias": dias,
        "estado": estado,
        "kpis": {
            "lecturas_frio": lecturas,
            "rupturas_frio": rupturas,
            "sellos_ecc": len(sellos),
            "contenedores": len(conts),
            "camaras_distintas": len(camaras),
        },
        "alertas_ruptura": alertas,
        "camaras": camaras,
        "sellos": [
            {
                "fecha": s[0],
                "archivo": s[1],
                "producto": s[2],
                "auditor": s[3],
                "hash": (s[4] or "")[:16],
            }
            for s in sellos[:40]
        ],
        "contenedores": [
            {
                "booking": c[0],
                "contenedor": c[1],
                "destino": c[2],
                "estado": c[3],
                "fecha": c[4],
            }
            for c in conts[:40]
        ],
    }


def enviar_informe_semanal_email(
    informe: dict,
    pdf_bytes: bytes | None = None,
    planta: str = "",
) -> dict:
    """Envía resumen semanal por SMTP (adjunto PDF si hay)."""
    from planta.avisos import _config_avisos, enviar_aviso_email

    cfg = _config_avisos()
    if not cfg.get("email_ok"):
        return {"ok": False, "configurado": False, "mensaje": "Email no configurado en [avisos]."}

    k = informe.get("kpis") or {}
    asunto = (
        f"Validador · informe semanal {informe.get('desde')} → {informe.get('hasta')}"
    )
    cuerpo = (
        f"Informe semanal — {planta or 'Planta'}\n"
        f"Periodo: {informe.get('desde')} a {informe.get('hasta')}\n"
        f"Estado: {informe.get('estado')}\n\n"
        f"Lecturas de frío: {k.get('lecturas_frio', 0)}\n"
        f"Rupturas: {k.get('rupturas_frio', 0)}\n"
        f"Sellos ECC: {k.get('sellos_ecc', 0)}\n"
        f"Contenedores: {k.get('contenedores', 0)}\n"
    )
    # Adjunto: si el helper de email no soporta MIME multipart con archivo,
    # enviamos texto; el PDF se descarga en UI.
    try:
        from email.mime.application import MIMEApplication
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        import smtplib

        msg = MIMEMultipart()
        msg["Subject"] = asunto
        msg["From"] = cfg["smtp_from"]
        msg["To"] = cfg["email_to"]
        msg.attach(MIMEText(cuerpo, "plain", "utf-8"))
        if pdf_bytes:
            part = MIMEApplication(pdf_bytes, Name="informe_semanal.pdf")
            part["Content-Disposition"] = 'attachment; filename="informe_semanal.pdf"'
            msg.attach(part)
        with smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"] or 587), timeout=25) as s:
            s.starttls()
            s.login(cfg["smtp_user"], cfg["smtp_pass"])
            s.sendmail(cfg["smtp_from"], [cfg["email_to"]], msg.as_string())
        return {"ok": True, "configurado": True, "mensaje": f"Informe enviado a {cfg['email_to']}."}
    except Exception as e:
        # Fallback texto simple
        r = enviar_aviso_email(asunto, cuerpo)
        if r.get("ok"):
            r["mensaje"] = (r.get("mensaje") or "OK") + f" (sin adjunto: {e})"
        return r
