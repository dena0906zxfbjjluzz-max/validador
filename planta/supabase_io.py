"""Cliente REST Supabase (sellos / tablas públicas)."""
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
def _supabase_config():
    """
    Lee SUPABASE_URL y SUPABASE_KEY desde st.secrets.

    Orden de búsqueda:
      1) st.secrets["credenciales"]["SUPABASE_URL"] / ["SUPABASE_KEY"]  (Cloud actual)
      2) st.secrets["SUPABASE_URL"] / ["SUPABASE_KEY"]  (raíz)
      3) st.secrets["supabase"]["url"] / ["key"]

    Returns: (url, key, error_si_falla)
    """
    try:
        import streamlit as st
    except Exception as e:
        return None, None, f"Streamlit no disponible para secrets: {e}"

    try:
        secrets = st.secrets
    except Exception as e:
        return None, None, f"No se pudieron leer secrets: {e}"

    def _limpiar(val):
        if val is None:
            return None
        s = str(val).strip().strip('"').strip("'")
        return s or None

    def _desde_bloque(bloque, *nombres):
        if bloque is None:
            return None
        for nombre in nombres:
            try:
                v = bloque[nombre]
            except Exception:
                try:
                    v = bloque.get(nombre)  # type: ignore[attr-defined]
                except Exception:
                    continue
            limpio = _limpiar(v)
            if limpio:
                return limpio
        return None

    url = None
    key = None
    origen = None

    # 1) Preferido: dentro de [credenciales]  (diagnóstico: solo existe esta clave raíz)
    try:
        creds = secrets["credenciales"]
        url = _desde_bloque(
            creds,
            "SUPABASE_URL",
            "supabase_url",
            "URL",
            "url",
        )
        key = _desde_bloque(
            creds,
            "SUPABASE_KEY",
            "SUPABASE_SERVICE_KEY",
            "supabase_key",
            "service_key",
            "KEY",
            "key",
            "anon_key",
        )
        if url and key:
            origen = "st.secrets['credenciales']"
    except Exception:
        creds = None

    # 2) Raíz
    if not url or not key:
        try:
            url = url or _limpiar(secrets["SUPABASE_URL"])
        except Exception:
            pass
        try:
            url = url or _limpiar(secrets["supabase_url"])
        except Exception:
            pass
        try:
            key = key or _limpiar(secrets["SUPABASE_KEY"])
        except Exception:
            pass
        try:
            key = key or _limpiar(secrets["SUPABASE_SERVICE_KEY"])
        except Exception:
            pass
        try:
            key = key or _limpiar(secrets["supabase_key"])
        except Exception:
            pass
        if url and key and origen is None:
            origen = "st.secrets (raíz)"

    # 3) Sección [supabase]
    if not url or not key:
        try:
            bloque = secrets["supabase"]
            url = url or _desde_bloque(bloque, "url", "URL", "SUPABASE_URL")
            key = key or _desde_bloque(
                bloque, "key", "KEY", "SUPABASE_KEY", "service_key", "anon_key"
            )
            if url and key and origen is None:
                origen = "st.secrets['supabase']"
        except Exception:
            pass

    if not url or not key:
        extras = ""
        try:
            claves = sorted(str(k) for k in secrets.keys())
            extras = f" Claves en secrets: {claves}."
        except Exception:
            pass
        detalle_creds = ""
        try:
            creds = secrets["credenciales"]
            sub = sorted(str(k) for k in creds.keys())
            detalle_creds = f" Claves dentro de credenciales: {sub}."
        except Exception:
            detalle_creds = (
                " No se encontraron subclaves en [credenciales]. "
                "Defina SUPABASE_URL y SUPABASE_KEY dentro de ese bloque."
            )
        return (
            None,
            None,
            "Faltan SUPABASE_URL o SUPABASE_KEY. "
            "Úselas como st.secrets['credenciales']['SUPABASE_URL'] y "
            "st.secrets['credenciales']['SUPABASE_KEY']."
            + extras
            + detalle_creds,
        )

    if not url.startswith("http"):
        return None, None, f"SUPABASE_URL inválida (debe empezar con https://): {url[:40]}..."

    return url.rstrip("/"), key, None


def enviar_sello_a_supabase(
    fecha,
    lote,
    hash_sha256,
    inspector,
    tabla=None,
    timeout=15.0,
):
    """
    POST REST a public.historial_reportes con EXACTAMENTE:
      { "fecha", "lote", "hash_sha256", "inspector" }
    en minúsculas. Sin campos extra (fecha_hora/responsable ya no se envían).

    Returns dict: ok, configurado, status, mensaje, payload, endpoint
    """
    url, key, err_cfg = _supabase_config()
    if err_cfg or not url or not key:
        return {
            "ok": False,
            "configurado": False,
            "status": None,
            "mensaje": err_cfg or "Supabase no configurado",
            "payload": {},
            "endpoint": None,
        }

    tabla_destino = (tabla or SUPABASE_TABLA_SELLOS).strip() or SUPABASE_TABLA_SELLOS
    # PostgREST: /rest/v1/historial_reportes → public.historial_reportes
    endpoint = f"{url}/rest/v1/{tabla_destino}"

    # Payload estricto — solo las 4 columnas de la tabla
    payload = {
        "fecha": str(fecha or "").strip(),
        "lote": str(lote or "N/D").strip(),
        "hash_sha256": str(hash_sha256 or "").strip(),
        "inspector": str(inspector or "N/D").strip(),
    }

    # Validación local de campos vacíos
    vacios = [c for c in SUPABASE_CAMPOS_SELLO if not payload.get(c)]
    if vacios:
        return {
            "ok": False,
            "configurado": True,
            "status": None,
            "mensaje": f"Campos vacíos, no se envió a Supabase: {vacios}",
            "payload": payload,
            "endpoint": endpoint,
        }

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        # Devuelve la fila insertada para confirmar que no falló en silencio
        "Prefer": "return=representation",
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(endpoint, data=body, method="POST", headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200) or 200
            raw = resp.read().decode("utf-8", errors="replace")
            if status in (200, 201, 204):
                # return=representation suele devolver un array JSON
                return {
                    "ok": True,
                    "configurado": True,
                    "status": status,
                    "mensaje": (
                        f"INSERT OK en public.{tabla_destino} "
                        f"(HTTP {status}). Respuesta: {(raw or '[]')[:200]}"
                    ),
                    "payload": payload,
                    "endpoint": endpoint,
                    "respuesta": (raw or "")[:500],
                }
            return {
                "ok": False,
                "configurado": True,
                "status": status,
                "mensaje": f"Supabase HTTP {status}: {(raw or 'sin cuerpo')[:400]}",
                "payload": payload,
                "endpoint": endpoint,
            }
    except urllib.error.HTTPError as e:
        try:
            detalle = e.read().decode("utf-8", errors="replace")[:600]
        except Exception:
            detalle = str(e)
        hint = ""
        if e.code in (401, 403):
            hint = (
                " | Pista: use la service_role key o cree una policy RLS de INSERT "
                "en public.historial_reportes."
            )
        elif e.code == 404:
            hint = " | Pista: la tabla public.historial_reportes no existe o el schema no es public."
        elif e.code == 409:
            # Hash único ya en la nube: no es un fallo operativo
            return {
                "ok": True,
                "ya_existia": True,
                "configurado": True,
                "status": 409,
                "mensaje": (
                    "Sello ya registrado en Supabase (hash_sha256 único). "
                    "No se duplicó el registro."
                ),
                "payload": payload,
                "endpoint": endpoint,
            }
        return {
            "ok": False,
            "configurado": True,
            "status": e.code,
            "mensaje": f"Error HTTP {e.code} POST {endpoint}: {detalle}{hint}",
            "payload": payload,
            "endpoint": endpoint,
        }
    except urllib.error.URLError as e:
        return {
            "ok": False,
            "configurado": True,
            "status": None,
            "mensaje": f"Error de red al conectar con Supabase ({endpoint}): {e.reason}",
            "payload": payload,
            "endpoint": endpoint,
        }
    except Exception as e:
        return {
            "ok": False,
            "configurado": True,
            "status": None,
            "mensaje": f"Excepción al enviar a Supabase: {type(e).__name__}: {e}",
            "payload": payload,
            "endpoint": endpoint,
        }


def _replicar_reporte_supabase(registro: dict):
    """Wrapper legacy. Preferir enviar_sello_a_supabase."""
    resultado = enviar_sello_a_supabase(
        fecha=str(registro.get("fecha") or registro.get("fecha_hora") or ""),
        lote=str(registro.get("lote") or "N/D"),
        hash_sha256=str(registro.get("hash_sha256") or ""),
        inspector=str(registro.get("inspector") or registro.get("responsable") or "N/D"),
    )
    if not resultado.get("configurado"):
        return None
    if resultado.get("ok"):
        return "ok"
    return resultado.get("mensaje") or "error Supabase"


def guardar_reporte_historico(
    fecha_hora: str,
    lote: str,
    hash_sha256: str,
    responsable: str,
    archivo: str = "",
    producto: str = "",
    registros: int = 0,
    firma_ecc: str = "",
    llave_publica: str = "",
    mensaje: str = "",
    modo_firma: str = "",
    backend: str = "",
) -> dict:
    """
    SQLite local + copia REST a Supabase (fecha, lote, hash_sha256, inspector).
    """
    inicializar_base_datos()
    conn = _conectar_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM historial_reportes WHERE hash_sha256 = ?", (hash_sha256,)
    )
    existente = cursor.fetchone()

    ya_existia = bool(existente)
    new_id = existente[0] if existente else None

    if not ya_existia:
        cursor.execute(
            """
            INSERT INTO historial_reportes (
                fecha_hora, lote, hash_sha256, responsable, archivo, producto,
                registros, firma_ecc, llave_publica, mensaje, modo_firma, backend
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fecha_hora,
                lote or "N/D",
                hash_sha256,
                responsable or "N/D",
                archivo,
                producto,
                int(registros or 0),
                firma_ecc,
                llave_publica,
                mensaje,
                modo_firma,
                backend,
            ),
        )
        new_id = cursor.lastrowid
        conn.commit()
    conn.close()

    try:
        supabase_result = enviar_sello_a_supabase(
            fecha=fecha_hora,
            lote=lote or "N/D",
            hash_sha256=hash_sha256,
            inspector=responsable or "N/D",
        )
    except Exception as e:
        supabase_result = {
            "ok": False,
            "configurado": True,
            "status": None,
            "mensaje": f"{type(e).__name__}: {e}",
            "payload": {
                "fecha": fecha_hora,
                "lote": lote or "N/D",
                "hash_sha256": hash_sha256,
                "inspector": responsable or "N/D",
            },
            "endpoint": None,
        }

    return {
        "guardado": not ya_existia,
        "ya_existia": ya_existia,
        "id": new_id,
        "hash": hash_sha256,
        "supabase": "ok" if supabase_result.get("ok") else supabase_result.get("mensaje"),
        "supabase_detalle": supabase_result,
    }


def cargar_historial_reportes_db(limite: int = 200) -> list:
    inicializar_base_datos()
    conn = _conectar_db()
    df = pd.read_sql_query(
        """
        SELECT
            fecha_hora AS 'Fecha',
            lote AS 'Lote',
            hash_sha256 AS 'Hash',
            responsable AS 'Responsable',
            archivo AS 'Archivo',
            producto AS 'Producto',
            registros AS 'Registros',
            modo_firma AS 'Modo',
            backend AS 'Backend'
        FROM historial_reportes
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(int(limite),),
    )
    conn.close()
    return df.to_dict("records")


def buscar_reporte_por_hash(hash_sha256: str) -> dict | None:
    inicializar_base_datos()
    conn = _conectar_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT fecha_hora, lote, hash_sha256, responsable, archivo, producto,
               registros, firma_ecc, llave_publica, mensaje, modo_firma, backend
        FROM historial_reportes
        WHERE hash_sha256 = ?
        LIMIT 1
        """,
        (hash_sha256.strip().lower(),),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        # también buscar sin forzar lower en caso de mayúsculas mixtas
        conn = _conectar_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT fecha_hora, lote, hash_sha256, responsable, archivo, producto,
                   registros, firma_ecc, llave_publica, mensaje, modo_firma, backend
            FROM historial_reportes
            WHERE lower(hash_sha256) = lower(?)
            LIMIT 1
            """,
            (hash_sha256.strip(),),
        )
        row = cursor.fetchone()
        conn.close()
    if not row:
        return None
    keys = [
        "fecha_hora", "lote", "hash_sha256", "responsable", "archivo", "producto",
        "registros", "firma_ecc", "llave_publica", "mensaje", "modo_firma", "backend",
    ]
    return dict(zip(keys, row))

