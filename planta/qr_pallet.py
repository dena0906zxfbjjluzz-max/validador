"""Escaneo QR de pallets / historial_reportes."""
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
from planta.supabase_io import _supabase_config, buscar_reporte_por_hash, cargar_historial_reportes_db
# ─── Módulo Escaneo QR → historial_reportes (Supabase) ───────────────────────

_RE_HASH_SHA256 = re.compile(r"\b([a-fA-F0-9]{64})\b")
_RE_LOTE_KV = re.compile(
    r"(?:lote|lot|id_lote|lote_id)\s*[:=]\s*([^\s,;|]+)",
    re.IGNORECASE,
)
_RE_HASH_KV = re.compile(
    r"(?:hash_sha256|hash|sha256|sello)\s*[:=]\s*([a-fA-F0-9]{64})",
    re.IGNORECASE,
)


def construir_payload_qr(lote: str, hash_sha256: str, inspector: str = "") -> str:
    """Texto canónico del QR del pallet (JSON legible para pyzbar)."""
    payload = {
        "lote": str(lote or "").strip() or "N/D",
        "hash_sha256": str(hash_sha256 or "").strip().lower(),
    }
    if inspector:
        payload["inspector"] = str(inspector).strip()
    return json.dumps(payload, ensure_ascii=False)


def parsear_payload_qr(texto_qr: str) -> dict:
    """
    Extrae lote y hash_sha256 del QR.
    Formatos aceptados: JSON, clave=valor, pipe, hash hex puro, URL con query.
    """
    crudo = (texto_qr or "").strip()
    result = {
        "texto": crudo,
        "lote": None,
        "hash_sha256": None,
    }
    if not crudo:
        return result

    # 1) JSON
    if crudo.startswith("{") and crudo.endswith("}"):
        try:
            obj = json.loads(crudo)
            if isinstance(obj, dict):
                for k_hash in ("hash_sha256", "hash", "sha256", "sello"):
                    if obj.get(k_hash):
                        result["hash_sha256"] = str(obj[k_hash]).strip().lower()
                        break
                for k_lote in ("lote", "lot", "id_lote", "lote_id", "id"):
                    if obj.get(k_lote):
                        result["lote"] = str(obj[k_lote]).strip()
                        break
                if result["hash_sha256"] or result["lote"]:
                    return result
        except json.JSONDecodeError:
            pass

    # 2) Query string / URL
    try:
        parsed = urllib.parse.urlparse(crudo)
        qs = urllib.parse.parse_qs(parsed.query)
        for k, vals in qs.items():
            if not vals:
                continue
            kl = k.lower()
            if kl in ("hash_sha256", "hash", "sha256") and not result["hash_sha256"]:
                result["hash_sha256"] = str(vals[0]).strip().lower()
            if kl in ("lote", "lot", "id_lote") and not result["lote"]:
                result["lote"] = str(vals[0]).strip()
        if result["hash_sha256"] or result["lote"]:
            return result
    except Exception:
        pass

    # 3) Hash hex puro
    if re.fullmatch(r"[a-fA-F0-9]{64}", crudo):
        result["hash_sha256"] = crudo.lower()
        return result

    # 4) lote|hash o hash|lote
    if "|" in crudo:
        partes = [p.strip() for p in crudo.split("|") if p.strip()]
        for p in partes:
            if re.fullmatch(r"[a-fA-F0-9]{64}", p):
                result["hash_sha256"] = p.lower()
            elif not result["lote"] and p.lower() not in ("n/d", "nan"):
                result["lote"] = p
        if result["hash_sha256"] or result["lote"]:
            return result

    # 5) Clave: valor en el texto
    m_h = _RE_HASH_KV.search(crudo)
    if m_h:
        result["hash_sha256"] = m_h.group(1).lower()
    m_l = _RE_LOTE_KV.search(crudo)
    if m_l:
        result["lote"] = m_l.group(1).strip()
    if not result["hash_sha256"]:
        m_any = _RE_HASH_SHA256.search(crudo)
        if m_any:
            result["hash_sha256"] = m_any.group(1).lower()

    # 6) Si no hay hash, el texto completo puede ser el ID de lote
    if not result["hash_sha256"] and not result["lote"] and crudo and len(crudo) < 120:
        result["lote"] = crudo

    return result


def decodificar_qr_desde_imagen(imagen_bytes: bytes) -> dict:
    """
    Decodifica QR/códigos desde bytes de imagen (st.camera_input / upload).
    Usa Pillow + pyzbar.
    """
    if not imagen_bytes:
        return {
            "ok": False,
            "textos": [],
            "mensaje": "No hay imagen para decodificar.",
        }

    try:
        from PIL import Image
    except ImportError:
        return {
            "ok": False,
            "textos": [],
            "mensaje": "Falta Pillow. Añada `Pillow` a requirements.txt.",
        }

    try:
        from pyzbar.pyzbar import decode as pyzbar_decode
    except ImportError:
        return {
            "ok": False,
            "textos": [],
            "mensaje": (
                "Falta pyzbar (o libzbar del sistema). "
                "Instale `pyzbar` y el paquete del SO `libzbar0`."
            ),
        }

    try:
        img = Image.open(io.BytesIO(imagen_bytes))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        codigos = pyzbar_decode(img)
    except Exception as e:
        return {
            "ok": False,
            "textos": [],
            "mensaje": f"Error al decodificar imagen: {type(e).__name__}: {e}",
        }

    textos = []
    detalles = []
    for c in codigos or []:
        try:
            t = c.data.decode("utf-8", errors="replace").strip()
        except Exception:
            t = str(getattr(c, "data", "")).strip()
        if t:
            textos.append(t)
            detalles.append(
                {
                    "tipo": str(getattr(c, "type", "") or "QR"),
                    "texto": t,
                }
            )

    if not textos:
        return {
            "ok": False,
            "textos": [],
            "detalles": [],
            "mensaje": "No se detectó ningún código QR en la imagen. Encuadre el código y capture de nuevo.",
        }

    return {
        "ok": True,
        "textos": textos,
        "detalles": detalles,
        "texto": textos[0],
        "mensaje": f"QR leído ({len(textos)} código(s)).",
    }


def consultar_historial_reportes_supabase(
    hash_sha256: str | None = None,
    lote: str | None = None,
    timeout: float = 15.0,
    limite: int = 20,
) -> dict:
    """
    GET REST equivalente a:
      supabase.table('historial_reportes').select('*').eq('hash_sha256', ...).eq('lote', ...)

    Filtra por hash y/o lote en public.historial_reportes.
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

    params = {
        "select": "fecha,lote,hash_sha256,inspector",
        "limit": str(int(limite)),
        "order": "fecha.desc",
    }
    h = (hash_sha256 or "").strip().lower()
    l = (lote or "").strip()
    if h:
        params["hash_sha256"] = f"eq.{h}"
    if l:
        params["lote"] = f"eq.{l}"

    if "hash_sha256" not in params and "lote" not in params:
        return {
            "ok": False,
            "configurado": True,
            "encontrado": False,
            "filas": [],
            "mensaje": "Se requiere hash_sha256 o lote para consultar historial_reportes.",
            "endpoint": None,
        }

    endpoint = f"{url}/rest/v1/{SUPABASE_TABLA_SELLOS}?{urllib.parse.urlencode(params)}"
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
                try:
                    data = json.loads(raw)
                    if isinstance(data, list):
                        filas = data
                    elif isinstance(data, dict):
                        filas = [data]
                except json.JSONDecodeError:
                    return {
                        "ok": False,
                        "configurado": True,
                        "encontrado": False,
                        "filas": [],
                        "mensaje": f"Respuesta no JSON de Supabase (HTTP {status}): {raw[:200]}",
                        "endpoint": endpoint,
                    }
            return {
                "ok": True,
                "configurado": True,
                "encontrado": len(filas) > 0,
                "filas": filas,
                "status": status,
                "mensaje": (
                    f"Consulta OK public.{SUPABASE_TABLA_SELLOS}: {len(filas)} fila(s)."
                ),
                "endpoint": endpoint,
            }
    except urllib.error.HTTPError as e:
        try:
            detalle = e.read().decode("utf-8", errors="replace")[:400]
        except Exception:
            detalle = str(e)
        return {
            "ok": False,
            "configurado": True,
            "encontrado": False,
            "filas": [],
            "status": e.code,
            "mensaje": f"HTTP {e.code} GET historial_reportes: {detalle}",
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


def validar_pallet_por_qr(imagen_bytes: bytes = None, texto_qr: str = None) -> dict:
    """
    Pipeline ERP: imagen/cámara → pyzbar → lote/hash → Supabase historial_reportes.

    Si el QR contiene un hash_sha256 registrado en la nube → verificado.
    Si solo hay lote, valida existencia del lote en la tabla remota.
    """
    textos_qr = []
    decode_info = None

    if imagen_bytes:
        decode_info = decodificar_qr_desde_imagen(imagen_bytes)
        if not decode_info.get("ok"):
            return {
                "verificado": False,
                "tipo_ui": "error",
                "mensaje_ui": decode_info.get("mensaje") or "No se pudo leer el QR.",
                "payload": None,
                "supabase": None,
                "decode": decode_info,
            }
        textos_qr = list(decode_info.get("textos") or [])
    elif texto_qr and str(texto_qr).strip():
        textos_qr = [str(texto_qr).strip()]
    else:
        return {
            "verificado": False,
            "tipo_ui": "error",
            "mensaje_ui": "Capture una foto del QR o ingrese el texto decodificado.",
            "payload": None,
            "supabase": None,
            "decode": None,
        }

    # Priorizar payload con hash; si hay varios QR, intentar todos
    payloads = [parsear_payload_qr(t) for t in textos_qr]
    payload = None
    for p in payloads:
        if p.get("hash_sha256"):
            payload = p
            break
    if payload is None:
        payload = payloads[0] if payloads else parsear_payload_qr(textos_qr[0])

    hash_q = payload.get("hash_sha256")
    lote_q = payload.get("lote")

    # Consulta automática a public.historial_reportes
    if hash_q:
        sb = consultar_historial_reportes_supabase(hash_sha256=hash_q, lote=None)
        # Si no hay fila por hash y hay lote, revalidar enlace hash+lote
        if not sb.get("encontrado") and lote_q:
            sb_lote = consultar_historial_reportes_supabase(hash_sha256=hash_q, lote=lote_q)
            if sb_lote.get("encontrado"):
                sb = sb_lote
    elif lote_q:
        sb = consultar_historial_reportes_supabase(hash_sha256=None, lote=lote_q)
    else:
        return {
            "verificado": False,
            "tipo_ui": "error",
            "mensaje_ui": (
                "🚨 El QR no contiene un ID de lote ni un hash_sha256 reconocible."
            ),
            "payload": payload,
            "supabase": None,
            "decode": decode_info,
        }

    if not sb.get("configurado"):
        # Fallback local SQLite si Supabase no está configurado
        local = None
        if hash_q:
            local = buscar_reporte_por_hash(hash_q)
        if local:
            return {
                "verificado": True,
                "tipo_ui": "success",
                "mensaje_ui": (
                    "✅ Pallet verificado en historial local (SQLite). "
                    "Configure Supabase para validación en la nube."
                ),
                "payload": payload,
                "supabase": sb,
                "registro": {
                    "fecha": local.get("fecha_hora"),
                    "lote": local.get("lote"),
                    "hash_sha256": local.get("hash_sha256"),
                    "inspector": local.get("responsable"),
                },
                "decode": decode_info,
            }
        return {
            "verificado": False,
            "tipo_ui": "error",
            "mensaje_ui": sb.get("mensaje") or "Supabase no configurado.",
            "payload": payload,
            "supabase": sb,
            "decode": decode_info,
        }

    if not sb.get("ok"):
        return {
            "verificado": False,
            "tipo_ui": "error",
            "mensaje_ui": f"🚨 Error al consultar Supabase: {sb.get('mensaje')}",
            "payload": payload,
            "supabase": sb,
            "decode": decode_info,
        }

    if sb.get("encontrado"):
        filas = sb.get("filas") or []
        # Si el QR traía hash, debe coincidir exactamente con alguna fila
        if hash_q:
            match = any(
                str(f.get("hash_sha256") or "").strip().lower() == hash_q for f in filas
            )
            if not match:
                return {
                    "verificado": False,
                    "tipo_ui": "error",
                    "mensaje_ui": (
                        "🚨 ALERTA: el hash del QR no coincide con ningún sello "
                        "registrado en Supabase (historial_reportes)."
                    ),
                    "payload": payload,
                    "supabase": sb,
                    "decode": decode_info,
                }
        registro = filas[0] if filas else {}
        return {
            "verificado": True,
            "tipo_ui": "success",
            "mensaje_ui": (
                "✅ Pallet verificado de forma segura mediante QR en Supabase."
            ),
            "payload": payload,
            "supabase": sb,
            "registro": registro,
            "decode": decode_info,
        }

    # No encontrado en la nube
    if hash_q:
        msg = (
            "🚨 ALERTA: el hash del QR no está registrado en Supabase "
            f"(historial_reportes). Lote leído: {lote_q or 'N/D'}."
        )
    else:
        msg = (
            f"🚨 ALERTA: el lote `{lote_q}` no tiene reportes sellados "
            "en Supabase (historial_reportes)."
        )
    return {
        "verificado": False,
        "tipo_ui": "error",
        "mensaje_ui": msg,
        "payload": payload,
        "supabase": sb,
        "decode": decode_info,
    }


def procesar_escaneo_qr_camara(imagen_bytes: bytes) -> dict:
    """
    Entrada desde st.camera_input: decodifica el QR y valida en Supabase.
    Alias funcional del pipeline ERP de pallet.
    """
    return validar_pallet_por_qr(imagen_bytes=imagen_bytes)

