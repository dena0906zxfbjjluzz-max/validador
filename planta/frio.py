"""Cadena de frío: validación, SQLite, Supabase y purge."""
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
def guardar_frio_db(camara, temperatura, hora_registro, estado, inspector, producto=""):
    """Persiste lectura de frío en SQLite local."""
    inicializar_base_datos()
    conn = _conectar_db()
    cursor = conn.cursor()
    # Columna producto (migración suave)
    try:
        cursor.execute("ALTER TABLE control_frio ADD COLUMN producto TEXT")
    except sqlite3.OperationalError:
        pass
    cursor.execute(
        """
        INSERT INTO control_frio (camara, temperatura, hora_registro, estado, inspector, producto)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (camara, temperatura, hora_registro, estado, inspector, producto or ""),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def cargar_frio_db(limite=50):
    conn = _conectar_db()
    # producto puede no existir en DBs antiguas
    try:
        df_frio = pd.read_sql_query(
            """
            SELECT hora_registro AS 'Fecha/Hora', camara AS 'Cámara',
                   temperatura AS 'Temp °C', estado AS 'Estado',
                   COALESCE(inspector, '') AS 'Inspector',
                   COALESCE(producto, '') AS 'Fruta'
            FROM control_frio
            ORDER BY id DESC
            LIMIT ?
            """,
            conn,
            params=(limite,),
        )
    except Exception:
        df_frio = pd.read_sql_query(
            """
            SELECT hora_registro AS 'Fecha/Hora', camara AS 'Cámara',
                   temperatura AS 'Temp °C', estado AS 'Estado',
                   COALESCE(inspector, '') AS 'Inspector'
            FROM control_frio
            ORDER BY id DESC
            LIMIT ?
            """,
            conn,
            params=(limite,),
        )
    conn.close()
    return df_frio.to_dict("records")


# Rangos óptimos comerciales reales (agroexportación)
RANGOS_TEMP_FRUTO = {
    "Palta Hass": {"min": 4.0, "max": 6.0},
    "Arándano": {"min": -0.5, "max": 0.5},
    "Espárrago": {"min": 2.0, "max": 4.0},
    "Uva Red Globe": {"min": -1.0, "max": 0.0},
}


def obtener_rango_frio_fruta(producto, temp_min_override=None, temp_max_override=None):
    """
    Devuelve (t_min, t_max) según la fruta del menú.
    Para 'Personalizado' usa overrides del sidebar si vienen.
    """
    nombre = str(producto or "").strip()
    if nombre in RANGOS_TEMP_FRUTO:
        r = RANGOS_TEMP_FRUTO[nombre]
        return float(r["min"]), float(r["max"])

    t_min = float(temp_min_override) if temp_min_override is not None else 0.0
    if temp_max_override is not None:
        t_max = float(temp_max_override)
    else:
        t_max = t_min + 2.0
    if t_max < t_min:
        t_min, t_max = t_max, t_min
    return t_min, t_max


def validar_temperatura_fruta(temperatura, producto, temp_min_override=None, temp_max_override=None):
    """Indica si la temperatura está dentro del rango comercial de la fruta."""
    t_min, t_max = obtener_rango_frio_fruta(producto, temp_min_override, temp_max_override)
    temp = float(temperatura)
    en_rango = t_min <= temp <= t_max
    return {
        "en_rango": en_rango,
        "temp_min": t_min,
        "temp_max": t_max,
        "temperatura": temp,
        "producto": str(producto or "").strip() or "N/D",
    }


def enviar_control_frio_supabase(registro: dict, timeout: float = 15.0) -> dict:
    """
    POST a public.control_frio en Supabase (REST).
    Campos preferidos en minúsculas: fecha, camara, temperatura, estado,
    inspector, producto, temp_min, temp_max.
    """
    url, key, err_cfg = _supabase_config()
    if err_cfg or not url or not key:
        return {
            "ok": False,
            "configurado": False,
            "mensaje": err_cfg or "Supabase no configurado",
            "payload": {},
        }

    endpoint = f"{url}/rest/v1/control_frio"
    # Payload principal + alias comunes (fecha/hora_registro)
    payload = {
        "fecha": registro.get("fecha") or registro.get("hora_registro"),
        "hora_registro": registro.get("hora_registro") or registro.get("fecha"),
        "camara": registro.get("camara"),
        "temperatura": registro.get("temperatura"),
        "estado": registro.get("estado"),
        "inspector": registro.get("inspector"),
        "producto": registro.get("producto"),
        "temp_min": registro.get("temp_min"),
        "temp_max": registro.get("temp_max"),
    }
    # Quitar Nones
    payload = {k: v for k, v in payload.items() if v is not None}

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Prefer": "return=representation",
    }

    variantes = [
        payload,
        # mínimo común
        {
            k: payload[k]
            for k in ("fecha", "camara", "temperatura", "estado", "inspector", "producto")
            if k in payload
        },
        {
            k: payload[k]
            for k in ("hora_registro", "camara", "temperatura", "estado", "inspector")
            if k in payload
        },
    ]

    ultimo_error = "sin detalle"
    for pl in variantes:
        if not pl:
            continue
        try:
            body = json.dumps(pl, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(endpoint, data=body, method="POST", headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = getattr(resp, "status", 200) or 200
                raw = resp.read().decode("utf-8", errors="replace")[:300]
                if status in (200, 201, 204):
                    return {
                        "ok": True,
                        "configurado": True,
                        "status": status,
                        "mensaje": f"INSERT OK public.control_frio (HTTP {status})",
                        "payload": pl,
                        "respuesta": raw,
                    }
                ultimo_error = f"HTTP {status}: {raw}"
        except urllib.error.HTTPError as e:
            try:
                ultimo_error = f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:400]}"
            except Exception:
                ultimo_error = f"HTTP {e.code}: {e}"
            continue
        except Exception as e:
            ultimo_error = f"{type(e).__name__}: {e}"
            continue

    return {
        "ok": False,
        "configurado": True,
        "mensaje": f"No se pudo insertar en Supabase control_frio: {ultimo_error}",
        "payload": payload,
    }


def purgar_control_frio_local(solo_rupturas: bool = False) -> dict:
    """
    Borra lecturas de frío en SQLite local (planta_calidad_prod.db).
    Las alertas de la app leen esta base, no solo Supabase.
    """
    inicializar_base_datos()
    conn = _conectar_db()
    try:
        cur = conn.cursor()
        if solo_rupturas:
            cur.execute(
                """
                DELETE FROM control_frio
                WHERE upper(COALESCE(estado, '')) LIKE '%RUPTURA%'
                """
            )
        else:
            cur.execute("DELETE FROM control_frio")
        borradas = int(cur.rowcount or 0)
        conn.commit()
        return {
            "ok": True,
            "borradas": borradas,
            "mensaje": (
                f"Se borraron {borradas} lectura(s) de frío en SQLite local"
                + (" (solo rupturas)." if solo_rupturas else ".")
            ),
        }
    except Exception as e:
        return {"ok": False, "borradas": 0, "mensaje": f"No se pudo borrar: {e}"}
    finally:
        conn.close()


def registrar_control_frio(
    camara,
    temperatura,
    producto,
    inspector,
    temp_min_override=None,
    temp_max_override=None,
    hora_registro=None,
):
    """
    Valida la temperatura según rangos comerciales de la fruta seleccionada,
    guarda en SQLite y replica a Supabase (tabla control_frio).

    Returns dict con en_rango, estado, mensajes UI y resultado remoto.
    """
    validacion = validar_temperatura_fruta(
        temperatura, producto, temp_min_override, temp_max_override
    )
    t_min = validacion["temp_min"]
    t_max = validacion["temp_max"]
    temp = validacion["temperatura"]
    fruta = validacion["producto"]
    en_rango = validacion["en_rango"]

    if en_rango:
        estado = "FRIO_OPTIMO"
        mensaje_ui = "✅ Temperatura validada"
        tipo_ui = "success"
    else:
        estado = "RUPTURA_CADENA_FRIO"
        mensaje_ui = f"🚨 ALERTA ROJA: Ruptura de cadena de frío para {fruta}"
        tipo_ui = "error"

    if not hora_registro:
        hora_registro = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1) SQLite local (siempre)
    try:
        row_id = guardar_frio_db(
            camara=camara,
            temperatura=temp,
            hora_registro=hora_registro,
            estado=estado,
            inspector=inspector or "N/D",
            producto=fruta,
        )
        sqlite_ok = True
        sqlite_msg = f"SQLite OK (id {row_id})"
    except Exception as e:
        row_id = None
        sqlite_ok = False
        sqlite_msg = f"SQLite error: {e}"

    # 2) Supabase (siempre se intenta registrar, incluso en alerta)
    registro_remoto = {
        "fecha": hora_registro,
        "hora_registro": hora_registro,
        "camara": camara,
        "temperatura": temp,
        "estado": estado,
        "inspector": inspector or "N/D",
        "producto": fruta,
        "temp_min": t_min,
        "temp_max": t_max,
    }
    try:
        sb = enviar_control_frio_supabase(registro_remoto)
    except Exception as e:
        sb = {
            "ok": False,
            "configurado": True,
            "mensaje": f"{type(e).__name__}: {e}",
            "payload": registro_remoto,
        }

    # Cola offline si la nube falló (se reintenta desde Dashboard)
    if not sb.get("ok") and not sb.get("ya_existia") and sb.get("configurado") is not False:
        try:
            from planta.cola_sync import encolar_sync

            encolar_sync(
                "control_frio",
                registro_remoto,
                error=str(sb.get("mensaje") or "fallo supabase"),
            )
            sb = dict(sb)
            sb["encolado"] = True
        except Exception:
            pass

    # 3) Aviso WhatsApp / email solo en ruptura
    aviso = {"ok": False, "configurado": False, "mensaje": ""}
    if not en_rango:
        try:
            from planta.avisos import notificar_ruptura_frio

            aviso = notificar_ruptura_frio(
                {
                    "camara": camara,
                    "temperatura": temp,
                    "temp_min": t_min,
                    "temp_max": t_max,
                    "producto": fruta,
                    "inspector": inspector or "N/D",
                    "hora_registro": hora_registro,
                    "estado": estado,
                }
            )
        except Exception as e:
            aviso = {
                "ok": False,
                "configurado": True,
                "mensaje": f"Aviso error: {type(e).__name__}: {e}",
            }

    return {
        "en_rango": en_rango,
        "estado": estado,
        "temp_min": t_min,
        "temp_max": t_max,
        "temperatura": temp,
        "producto": fruta,
        "camara": camara,
        "hora_registro": hora_registro,
        "tipo_ui": tipo_ui,
        "mensaje_ui": mensaje_ui,
        "sqlite_ok": sqlite_ok,
        "sqlite_msg": sqlite_msg,
        "id_local": row_id,
        "supabase": sb,
        "aviso": aviso,
    }
