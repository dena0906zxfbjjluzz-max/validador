"""Contenedores de despacho (SQLite + Supabase)."""
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

from planta.db import _conectar_db, inicializar_base_datos
from planta.supabase_io import _supabase_config
def guardar_contenedor_db(booking, contenedor, p_linea, p_senasa, destino, estado):
    inicializar_base_datos()
    conn = _conectar_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO contenedores_despacho
            (booking, contenedor, precinto_linea, precinto_senasa, destino, estado)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (booking, contenedor, p_linea, p_senasa, destino, estado),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def cargar_contenedores_db(limite: int = 100):
    inicializar_base_datos()
    conn = _conectar_db()
    df_cont = pd.read_sql_query(
        """
        SELECT booking AS 'Booking', contenedor AS 'Contenedor',
               precinto_linea AS 'Precinto Línea', precinto_senasa AS 'Precinto SENASA',
               destino AS 'Destino', estado AS 'Estado'
        FROM contenedores_despacho
        ORDER BY rowid DESC
        LIMIT ?
        """,
        conn,
        params=(int(limite),),
    )
    conn.close()
    return df_cont.to_dict("records")


def buscar_contenedor_local(contenedor: str = "", booking: str = "") -> dict | None:
    """Busca un contenedor o booking en SQLite local."""
    inicializar_base_datos()
    c_id = str(contenedor or "").strip().upper()
    bkg = str(booking or "").strip().upper()
    if not c_id and not bkg:
        return None
    conn = _conectar_db()
    cur = conn.cursor()
    if c_id:
        cur.execute(
            """
            SELECT booking, contenedor, precinto_linea, precinto_senasa, destino, estado
            FROM contenedores_despacho
            WHERE upper(contenedor) = ?
            ORDER BY rowid DESC LIMIT 1
            """,
            (c_id,),
        )
        row = cur.fetchone()
        if row:
            conn.close()
            return dict(
                zip(
                    ["booking", "contenedor", "precinto_linea", "precinto_senasa", "destino", "estado"],
                    row,
                )
            )
    if bkg:
        cur.execute(
            """
            SELECT booking, contenedor, precinto_linea, precinto_senasa, destino, estado
            FROM contenedores_despacho
            WHERE upper(booking) = ?
            ORDER BY rowid DESC LIMIT 1
            """,
            (bkg,),
        )
        row = cur.fetchone()
        if row:
            conn.close()
            return dict(
                zip(
                    ["booking", "contenedor", "precinto_linea", "precinto_senasa", "destino", "estado"],
                    row,
                )
            )
    conn.close()
    return None


_RE_ISO6346 = re.compile(r"\b([A-Z]{4}\s?\d{7})\b", re.IGNORECASE)
_RE_BOOKING = re.compile(
    r"(?:booking|bkg|bl|reserva)\s*[:=]\s*([A-Za-z0-9\-/]+)", re.IGNORECASE
)
_RE_CONT_KV = re.compile(
    r"(?:contenedor|container|cntr|reefer)\s*[:=]\s*([A-Za-z0-9]+)", re.IGNORECASE
)
_RE_PREC_LIN = re.compile(
    r"(?:precinto_linea|precinto.?linea|seal.?line|seal)\s*[:=]\s*([A-Za-z0-9\-/]+)",
    re.IGNORECASE,
)
_RE_PREC_SEN = re.compile(
    r"(?:precinto_senasa|senasa|precinto.?oficial)\s*[:=]\s*([A-Za-z0-9\-/]+)",
    re.IGNORECASE,
)


def parsear_payload_contenedor(texto: str) -> dict:
    """
    Extrae booking / contenedor / precintos del QR o texto.
    Formatos: JSON, clave=valor, pipe, código ISO 6346 puro.
    """
    crudo = (texto or "").strip()
    out = {
        "texto": crudo,
        "booking": None,
        "contenedor": None,
        "precinto_linea": None,
        "precinto_senasa": None,
        "destino": None,
        "estado": None,
    }
    if not crudo:
        return out

    if crudo.startswith("{") and crudo.endswith("}"):
        try:
            obj = json.loads(crudo)
            if isinstance(obj, dict):
                for k, alias in (
                    ("booking", ("booking", "bkg", "bl", "reserva")),
                    ("contenedor", ("contenedor", "container", "cntr", "reefer", "id")),
                    ("precinto_linea", ("precinto_linea", "precinto_line", "seal", "seal_line")),
                    ("precinto_senasa", ("precinto_senasa", "senasa", "precinto_oficial")),
                    ("destino", ("destino", "market", "mercado")),
                    ("estado", ("estado", "status")),
                ):
                    for a in alias:
                        if obj.get(a):
                            out[k] = str(obj[a]).strip()
                            break
                if out["contenedor"] or out["booking"]:
                    if out["contenedor"]:
                        out["contenedor"] = out["contenedor"].upper().replace(" ", "")
                    return out
        except json.JSONDecodeError:
            pass

    if "|" in crudo:
        partes = [p.strip() for p in crudo.split("|") if p.strip()]
        # booking|contenedor|p_linea|p_senasa|destino
        if len(partes) >= 2:
            out["booking"] = partes[0]
            out["contenedor"] = partes[1].upper().replace(" ", "")
            if len(partes) >= 3:
                out["precinto_linea"] = partes[2]
            if len(partes) >= 4:
                out["precinto_senasa"] = partes[3]
            if len(partes) >= 5:
                out["destino"] = partes[4]
            return out

    m_iso = _RE_ISO6346.search(crudo.upper().replace(" ", ""))
    if m_iso or _RE_ISO6346.search(crudo.upper()):
        m2 = _RE_ISO6346.search(crudo.upper())
        if m2:
            out["contenedor"] = m2.group(1).replace(" ", "")

    m_b = _RE_BOOKING.search(crudo)
    if m_b:
        out["booking"] = m_b.group(1).strip()
    m_c = _RE_CONT_KV.search(crudo)
    if m_c:
        out["contenedor"] = m_c.group(1).strip().upper().replace(" ", "")
    m_pl = _RE_PREC_LIN.search(crudo)
    if m_pl:
        out["precinto_linea"] = m_pl.group(1).strip()
    m_ps = _RE_PREC_SEN.search(crudo)
    if m_ps:
        out["precinto_senasa"] = m_ps.group(1).strip()

    # Texto corto = posible contenedor ISO
    if not out["contenedor"] and re.fullmatch(r"[A-Za-z]{4}\d{7}", crudo.replace(" ", "")):
        out["contenedor"] = crudo.replace(" ", "").upper()
    elif not out["contenedor"] and not out["booking"] and len(crudo) < 40:
        # asumir booking corto
        out["booking"] = crudo

    return out


def consultar_contenedores_supabase(
    contenedor: str | None = None,
    booking: str | None = None,
    timeout: float = 15.0,
) -> dict:
    """
    GET REST ≈ supabase.table('contenedores_despacho').select('*').eq(...)
    """
    url, key, err_cfg = _supabase_config()
    if err_cfg or not url or not key:
        return {
            "ok": False,
            "configurado": False,
            "encontrado": False,
            "filas": [],
            "mensaje": err_cfg or "Supabase no configurado",
            "endpoint": None,
        }

    params = {"select": "*", "limit": "10"}
    c_id = (contenedor or "").strip()
    bkg = (booking or "").strip()
    if c_id:
        params["contenedor"] = f"eq.{c_id}"
    if bkg:
        params["booking"] = f"eq.{bkg}"
    if "contenedor" not in params and "booking" not in params:
        return {
            "ok": False,
            "configurado": True,
            "encontrado": False,
            "filas": [],
            "mensaje": "Se requiere contenedor o booking para consultar.",
            "endpoint": None,
        }

    endpoint = f"{url}/rest/v1/contenedores_despacho?{urllib.parse.urlencode(params)}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    try:
        req = urllib.request.Request(endpoint, method="GET", headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200) or 200
            raw = resp.read().decode("utf-8", errors="replace")
            filas = []
            if raw.strip():
                data = json.loads(raw)
                if isinstance(data, list):
                    filas = data
                elif isinstance(data, dict):
                    filas = [data]
            return {
                "ok": True,
                "configurado": True,
                "encontrado": len(filas) > 0,
                "filas": filas,
                "status": status,
                "mensaje": f"Consulta OK: {len(filas)} fila(s).",
                "endpoint": endpoint,
            }
    except urllib.error.HTTPError as e:
        try:
            detalle = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            detalle = str(e)
        return {
            "ok": False,
            "configurado": True,
            "encontrado": False,
            "filas": [],
            "status": e.code,
            "mensaje": f"HTTP {e.code}: {detalle}",
            "endpoint": endpoint,
        }
    except Exception as e:
        return {
            "ok": False,
            "configurado": True,
            "encontrado": False,
            "filas": [],
            "mensaje": f"{type(e).__name__}: {e}",
            "endpoint": endpoint,
        }


def enviar_contenedor_supabase(registro: dict, timeout: float = 15.0) -> dict:
    """POST a public.contenedores_despacho (variantes de columnas)."""
    url, key, err_cfg = _supabase_config()
    if err_cfg or not url or not key:
        return {
            "ok": False,
            "configurado": False,
            "mensaje": err_cfg or "Supabase no configurado",
            "payload": {},
        }

    endpoint = f"{url}/rest/v1/contenedores_despacho"
    base = {
        "booking": registro.get("booking"),
        "contenedor": registro.get("contenedor"),
        "precinto_linea": registro.get("precinto_linea"),
        "precinto_senasa": registro.get("precinto_senasa"),
        "destino": registro.get("destino"),
        "estado": registro.get("estado"),
        "inspector": registro.get("inspector"),
        "fecha": registro.get("fecha")
        or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    base = {k: v for k, v in base.items() if v is not None and str(v).strip() != ""}

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Prefer": "return=representation",
    }

    variantes = [
        base,
        {
            k: base[k]
            for k in ("booking", "contenedor", "precinto_linea", "precinto_senasa", "destino", "estado")
            if k in base
        },
        {k: base[k] for k in ("booking", "contenedor", "estado") if k in base},
    ]

    ultimo = "sin detalle"
    for pl in variantes:
        if not pl or "contenedor" not in pl:
            continue
        try:
            body = json.dumps(pl, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(endpoint, data=body, method="POST", headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = getattr(resp, "status", 200) or 200
                if status in (200, 201, 204):
                    return {
                        "ok": True,
                        "configurado": True,
                        "status": status,
                        "mensaje": f"INSERT OK contenedores_despacho (HTTP {status})",
                        "payload": pl,
                        "endpoint": endpoint,
                    }
        except urllib.error.HTTPError as e:
            try:
                ultimo = f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:300]}"
            except Exception:
                ultimo = f"HTTP {e.code}"
            if e.code == 409:
                return {
                    "ok": True,
                    "ya_existia": True,
                    "configurado": True,
                    "status": 409,
                    "mensaje": "Contenedor ya registrado en Supabase (sin duplicar).",
                    "payload": pl,
                    "endpoint": endpoint,
                }
            continue
        except Exception as e:
            ultimo = f"{type(e).__name__}: {e}"
            continue

    return {
        "ok": False,
        "configurado": True,
        "mensaje": f"No se pudo insertar en Supabase contenedores_despacho: {ultimo}",
        "payload": base,
        "endpoint": endpoint,
    }


def validar_y_consultar_contenedor(
    imagen_bytes: bytes | None = None,
    texto_qr: str | None = None,
) -> dict:
    """
    Pipeline tipo Módulo 6: imagen/texto → QR → parse → local + Supabase.
    """
    textos = []
    decode_info = None
    if imagen_bytes:
        decode_info = decodificar_qr_desde_imagen(imagen_bytes)
        if not decode_info.get("ok"):
            return {
                "verificado": False,
                "tipo_ui": "error",
                "mensaje_ui": decode_info.get("mensaje") or "No se pudo leer el QR.",
                "payload": None,
                "local": None,
                "supabase": None,
                "decode": decode_info,
            }
        textos = list(decode_info.get("textos") or [])
    elif texto_qr and str(texto_qr).strip():
        textos = [str(texto_qr).strip()]
    else:
        return {
            "verificado": False,
            "tipo_ui": "error",
            "mensaje_ui": "Capture o pegue el QR / código del contenedor.",
            "payload": None,
            "local": None,
            "supabase": None,
            "decode": None,
        }

    payload = None
    for t in textos:
        p = parsear_payload_contenedor(t)
        if p.get("contenedor") or p.get("booking"):
            payload = p
            break
    if payload is None:
        payload = parsear_payload_contenedor(textos[0])

    c_id = payload.get("contenedor")
    bkg = payload.get("booking")
    if not c_id and not bkg:
        return {
            "verificado": False,
            "tipo_ui": "error",
            "mensaje_ui": (
                "🚨 No se detectó booking ni contenedor en el QR. "
                "Use JSON, ISO 6346 (4 letras + 7 dígitos) o booking|contenedor|…"
            ),
            "payload": payload,
            "local": None,
            "supabase": None,
            "decode": decode_info,
        }

    local = buscar_contenedor_local(contenedor=c_id or "", booking=bkg or "")
    sb = consultar_contenedores_supabase(contenedor=c_id, booking=bkg if not c_id else None)

    if local or (sb.get("ok") and sb.get("encontrado")):
        reg = local or ((sb.get("filas") or [{}])[0])
        return {
            "verificado": True,
            "tipo_ui": "success",
            "mensaje_ui": (
                f"✅ Contenedor verificado: `{reg.get('contenedor') or c_id or 'N/D'}` · "
                f"estado **{reg.get('estado') or 'REGISTRADO'}**"
            ),
            "payload": payload,
            "local": local,
            "supabase": sb,
            "registro": reg,
            "decode": decode_info,
        }

    return {
        "verificado": False,
        "tipo_ui": "error",
        "mensaje_ui": (
            f"🚨 Contenedor no encontrado en base local/nube. "
            f"Booking: {bkg or 'N/D'} · Contenedor: {c_id or 'N/D'}. "
            "Complete el formulario y selle el despacho."
        ),
        "payload": payload,
        "local": None,
        "supabase": sb,
        "registro": None,
        "decode": decode_info,
    }


def procesar_escaneo_contenedor_camara(imagen_bytes: bytes) -> dict:
    """Alias Módulo 5: cámara → consulta contenedor."""
    return validar_y_consultar_contenedor(imagen_bytes=imagen_bytes)


def registrar_contenedor_despacho(
    booking: str,
    contenedor: str,
    precinto_linea: str = "",
    precinto_senasa: str = "",
    destino: str = "",
    estado: str = "SELLADO Y LISTO",
    inspector: str = "",
) -> dict:
    """
    Guarda en SQLite y replica a Supabase (mismo patrón que frío / QR).
    """
    booking = str(booking or "").strip()
    contenedor = str(contenedor or "").strip().upper().replace(" ", "")
    precinto_linea = str(precinto_linea or "").strip()
    precinto_senasa = str(precinto_senasa or "").strip()
    destino = str(destino or "").strip() or "N/D"
    estado = str(estado or "SELLADO Y LISTO").strip()
    inspector = str(inspector or "N/D").strip()

    if not booking or not contenedor or not precinto_linea:
        return {
            "ok": False,
            "tipo_ui": "error",
            "mensaje_ui": "⚠️ Complete Booking, Contenedor y Precinto de línea (obligatorios).",
            "sqlite_ok": False,
            "supabase": None,
        }

    # Ya existe local
    ya = buscar_contenedor_local(contenedor=contenedor)
    if ya:
        return {
            "ok": True,
            "ya_existia": True,
            "tipo_ui": "success",
            "mensaje_ui": (
                f"✅ Contenedor `{contenedor}` ya estaba registrado "
                f"(estado: {ya.get('estado')})."
            ),
            "registro": ya,
            "sqlite_ok": True,
            "supabase": None,
        }

    try:
        row_id = guardar_contenedor_db(
            booking, contenedor, precinto_linea, precinto_senasa, destino, estado
        )
        sqlite_ok = True
        sqlite_msg = f"SQLite OK (id {row_id})"
    except Exception as e:
        row_id = None
        sqlite_ok = False
        sqlite_msg = f"SQLite error: {e}"
        return {
            "ok": False,
            "tipo_ui": "error",
            "mensaje_ui": f"🚨 No se pudo guardar localmente: {e}",
            "sqlite_ok": False,
            "sqlite_msg": sqlite_msg,
            "supabase": None,
        }

    registro = {
        "booking": booking,
        "contenedor": contenedor,
        "precinto_linea": precinto_linea,
        "precinto_senasa": precinto_senasa,
        "destino": destino,
        "estado": estado,
        "inspector": inspector,
        "fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        sb = enviar_contenedor_supabase(registro)
    except Exception as e:
        sb = {"ok": False, "configurado": True, "mensaje": f"{type(e).__name__}: {e}"}

    return {
        "ok": True,
        "ya_existia": False,
        "tipo_ui": "success",
        "mensaje_ui": (
            f"✅ Contenedor `{contenedor}` sellado y registrado "
            f"(booking {booking})."
        ),
        "registro": registro,
        "id_local": row_id,
        "sqlite_ok": sqlite_ok,
        "sqlite_msg": sqlite_msg,
        "supabase": sb,
    }

