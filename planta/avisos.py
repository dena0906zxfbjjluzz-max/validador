"""Avisos email / WhatsApp por ruptura de frío."""
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

# ─── Avisos por correo / WhatsApp (ruptura de frío) ───────────────────────────


def _leer_secret_aviso(*rutas):
    """Lee un valor de secrets por varias rutas posibles. Retorna str o ''."""
    try:
        import streamlit as st

        secrets = st.secrets
    except Exception:
        return ""

    def _get(obj, key):
        try:
            return obj[key]
        except Exception:
            return None

    for ruta in rutas:
        cur = secrets
        ok = True
        for parte in ruta:
            cur = _get(cur, parte)
            if cur is None:
                ok = False
                break
        if ok and str(cur).strip():
            return str(cur).strip()
    return ""


def _config_avisos() -> dict:
    """
    Configuración opcional en secrets [avisos]:
    email_to, smtp_host, smtp_port, smtp_user, smtp_pass, smtp_from,
    whatsapp_to, callmebot_apikey, twilio_sid, twilio_token, twilio_from
    """
    cfg = {
        "email_to": _leer_secret_aviso(
            ("avisos", "email_to"), ("credenciales", "AVISO_EMAIL_TO"), ("AVISO_EMAIL_TO",)
        ),
        "smtp_host": _leer_secret_aviso(
            ("avisos", "smtp_host"), ("credenciales", "SMTP_HOST"), ("SMTP_HOST",)
        )
        or "smtp.gmail.com",
        "smtp_port": _leer_secret_aviso(
            ("avisos", "smtp_port"), ("credenciales", "SMTP_PORT"), ("SMTP_PORT",)
        )
        or "587",
        "smtp_user": _leer_secret_aviso(
            ("avisos", "smtp_user"), ("credenciales", "SMTP_USER"), ("SMTP_USER",)
        ),
        "smtp_pass": _leer_secret_aviso(
            ("avisos", "smtp_pass"), ("credenciales", "SMTP_PASS"), ("SMTP_PASS",)
        ),
        "smtp_from": _leer_secret_aviso(
            ("avisos", "smtp_from"), ("credenciales", "SMTP_FROM"), ("SMTP_FROM",)
        ),
        "whatsapp_to": _leer_secret_aviso(
            ("avisos", "whatsapp_to"), ("credenciales", "WHATSAPP_TO"), ("WHATSAPP_TO",)
        ),
        "callmebot_apikey": _leer_secret_aviso(
            ("avisos", "callmebot_apikey"),
            ("credenciales", "CALLMEBOT_APIKEY"),
            ("CALLMEBOT_APIKEY",),
        ),
        "twilio_sid": _leer_secret_aviso(("avisos", "twilio_sid"), ("credenciales", "TWILIO_SID")),
        "twilio_token": _leer_secret_aviso(
            ("avisos", "twilio_token"), ("credenciales", "TWILIO_TOKEN")
        ),
        "twilio_from": _leer_secret_aviso(
            ("avisos", "twilio_from"), ("credenciales", "TWILIO_FROM")
        ),
    }
    if not cfg["smtp_from"]:
        cfg["smtp_from"] = cfg["smtp_user"]
    cfg["email_ok"] = bool(cfg["email_to"] and cfg["smtp_user"] and cfg["smtp_pass"])
    cfg["wa_callmebot_ok"] = bool(cfg["whatsapp_to"] and cfg["callmebot_apikey"])
    cfg["wa_twilio_ok"] = bool(
        cfg["whatsapp_to"] and cfg["twilio_sid"] and cfg["twilio_token"] and cfg["twilio_from"]
    )
    cfg["whatsapp_ok"] = cfg["wa_callmebot_ok"] or cfg["wa_twilio_ok"]
    cfg["habilitado"] = cfg["email_ok"] or cfg["whatsapp_ok"]
    return cfg


def _cooldown_aviso_ok(clave: str, minutos: int = 30) -> bool:
    """Evita spam: un aviso por cámara cada N minutos (SQLite)."""
    inicializar_base_datos()
    conn = _conectar_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS avisos_enviados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clave TEXT NOT NULL,
            canal TEXT,
            fecha_hora TEXT NOT NULL,
            detalle TEXT
        )
        """
    )
    conn.commit()
    cur.execute(
        """
        SELECT fecha_hora FROM avisos_enviados
        WHERE clave = ?
        ORDER BY id DESC LIMIT 1
        """,
        (clave,),
    )
    row = cur.fetchone()
    ahora = datetime.datetime.now()
    if row:
        try:
            ult = datetime.datetime.strptime(str(row[0])[:19], "%Y-%m-%d %H:%M:%S")
            if (ahora - ult).total_seconds() < minutos * 60:
                conn.close()
                return False
        except Exception:
            pass
    conn.close()
    return True


def _registrar_aviso_enviado(clave: str, canal: str, detalle: str = ""):
    inicializar_base_datos()
    conn = _conectar_db()
    conn.execute(
        "INSERT INTO avisos_enviados (clave, canal, fecha_hora, detalle) VALUES (?, ?, ?, ?)",
        (
            clave,
            canal,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            (detalle or "")[:400],
        ),
    )
    conn.commit()
    conn.close()


def enviar_aviso_email(asunto: str, cuerpo: str) -> dict:
    cfg = _config_avisos()
    if not cfg["email_ok"]:
        return {
            "ok": False,
            "configurado": False,
            "mensaje": "Email no configurado en secrets [avisos]",
        }
    try:
        import smtplib
        from email.mime.text import MIMEText

        msg = MIMEText(cuerpo, "plain", "utf-8")
        msg["Subject"] = asunto
        msg["From"] = cfg["smtp_from"]
        msg["To"] = cfg["email_to"]
        port = int(cfg["smtp_port"] or 587)
        with smtplib.SMTP(cfg["smtp_host"], port, timeout=20) as server:
            server.starttls()
            server.login(cfg["smtp_user"], cfg["smtp_pass"])
            server.sendmail(cfg["smtp_from"], [cfg["email_to"]], msg.as_string())
        return {
            "ok": True,
            "configurado": True,
            "mensaje": f"Email enviado a {cfg['email_to']}",
        }
    except Exception as e:
        return {
            "ok": False,
            "configurado": True,
            "mensaje": f"Email error: {type(e).__name__}: {e}",
        }


def enviar_aviso_whatsapp(texto: str) -> dict:
    cfg = _config_avisos()
    if not cfg["whatsapp_ok"]:
        return {
            "ok": False,
            "configurado": False,
            "mensaje": "WhatsApp no configurado (CallMeBot o Twilio en secrets [avisos])",
        }

    if cfg["wa_twilio_ok"]:
        try:
            import base64

            to = cfg["whatsapp_to"]
            if not to.startswith("whatsapp:"):
                to = "whatsapp:+" + to.lstrip("+")
            endpoint = (
                f"https://api.twilio.com/2010-04-01/Accounts/{cfg['twilio_sid']}/Messages.json"
            )
            data = urllib.parse.urlencode(
                {"From": cfg["twilio_from"], "To": to, "Body": texto[:1500]}
            ).encode("utf-8")
            req = urllib.request.Request(endpoint, data=data, method="POST")
            token = base64.b64encode(
                f"{cfg['twilio_sid']}:{cfg['twilio_token']}".encode()
            ).decode()
            req.add_header("Authorization", f"Basic {token}")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            with urllib.request.urlopen(req, timeout=20) as resp:
                status = getattr(resp, "status", 200) or 200
                if status in (200, 201):
                    return {
                        "ok": True,
                        "configurado": True,
                        "mensaje": "WhatsApp Twilio OK",
                        "canal": "twilio",
                    }
                return {
                    "ok": False,
                    "configurado": True,
                    "mensaje": f"Twilio HTTP {status}",
                }
        except Exception as e:
            return {
                "ok": False,
                "configurado": True,
                "mensaje": f"Twilio error: {type(e).__name__}: {e}",
            }

    try:
        phone = cfg["whatsapp_to"].lstrip("+")
        q = urllib.parse.urlencode(
            {"phone": phone, "text": texto[:1000], "apikey": cfg["callmebot_apikey"]}
        )
        url = f"https://api.callmebot.com/whatsapp.php?{q}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8", errors="replace")[:200]
            status = getattr(resp, "status", 200) or 200
            if status == 200:
                return {
                    "ok": True,
                    "configurado": True,
                    "mensaje": f"WhatsApp CallMeBot OK",
                    "canal": "callmebot",
                    "detalle": raw,
                }
            return {
                "ok": False,
                "configurado": True,
                "mensaje": f"CallMeBot HTTP {status}: {raw}",
            }
    except Exception as e:
        return {
            "ok": False,
            "configurado": True,
            "mensaje": f"WhatsApp error: {type(e).__name__}: {e}",
        }


def notificar_ruptura_frio(registro: dict, forzar: bool = False) -> dict:
    """
    Envía aviso por email y/o WhatsApp si hay secrets.
    Cooldown 30 min por cámara (salvo forzar=True).
    """
    cfg = _config_avisos()
    if not cfg["habilitado"]:
        return {
            "ok": False,
            "configurado": False,
            "email": {"ok": False, "mensaje": "no config"},
            "whatsapp": {"ok": False, "mensaje": "no config"},
            "mensaje": "Avisos no configurados (secrets [avisos]).",
        }

    camara = str(registro.get("camara") or "N/D")
    clave = f"frio:{camara}"
    if not forzar and not _cooldown_aviso_ok(clave, minutos=30):
        return {
            "ok": False,
            "configurado": True,
            "omitido": True,
            "mensaje": f"Aviso omitido (cooldown 30 min · {camara})",
            "email": {},
            "whatsapp": {},
        }

    asunto = f"ALERTA frío · {camara}"
    cuerpo = (
        f"RUPTURA DE CADENA DE FRÍO\n"
        f"Cámara: {camara}\n"
        f"Temp: {registro.get('temperatura')} °C "
        f"(rango {registro.get('temp_min')}–{registro.get('temp_max')} °C)\n"
        f"Producto: {registro.get('producto')}\n"
        f"Inspector: {registro.get('inspector')}\n"
        f"Hora: {registro.get('hora_registro')}\n"
        f"Estado: {registro.get('estado')}\n"
        f"— Validador de planta"
    )

    email_r = (
        enviar_aviso_email(asunto, cuerpo)
        if cfg["email_ok"]
        else {"ok": False, "configurado": False, "mensaje": "Email no configurado"}
    )
    wa_r = (
        enviar_aviso_whatsapp(cuerpo)
        if cfg["whatsapp_ok"]
        else {"ok": False, "configurado": False, "mensaje": "WhatsApp no configurado"}
    )

    enviados = []
    if email_r.get("ok"):
        enviados.append("email")
        _registrar_aviso_enviado(clave, "email", email_r.get("mensaje", ""))
    if wa_r.get("ok"):
        enviados.append("whatsapp")
        _registrar_aviso_enviado(clave, "whatsapp", wa_r.get("mensaje", ""))

    ok = bool(enviados)
    return {
        "ok": ok,
        "configurado": True,
        "canales": enviados,
        "mensaje": (
            f"Aviso enviado: {', '.join(enviados)}"
            if ok
            else f"No se pudo enviar · email: {email_r.get('mensaje')} · wa: {wa_r.get('mensaje')}"
        ),
        "email": email_r,
        "whatsapp": wa_r,
    }
