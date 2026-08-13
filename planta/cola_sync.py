"""Cola offline: reintentar POSTs a Supabase cuando vuelve la red."""
from __future__ import annotations

import datetime
import json

from planta.db import _conectar_db, inicializar_base_datos


def encolar_sync(tipo: str, payload: dict, error: str = "") -> int:
    inicializar_base_datos()
    conn = _conectar_db()
    cur = conn.execute(
        """
        INSERT INTO cola_sync (tipo, payload_json, intentos, ultimo_error, creado_en, estado)
        VALUES (?, ?, 0, ?, ?, 'pendiente')
        """,
        (
            str(tipo),
            json.dumps(payload or {}, ensure_ascii=False),
            str(error or "")[:500],
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    conn.commit()
    row_id = int(cur.lastrowid or 0)
    conn.close()
    return row_id


def listar_cola_sync(limite: int = 50) -> list[dict]:
    inicializar_base_datos()
    conn = _conectar_db()
    rows = conn.execute(
        """
        SELECT id, tipo, payload_json, intentos, ultimo_error, creado_en, estado
        FROM cola_sync
        WHERE estado = 'pendiente'
        ORDER BY id ASC
        LIMIT ?
        """,
        (int(limite),),
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        try:
            payload = json.loads(r[2] or "{}")
        except Exception:
            payload = {}
        out.append(
            {
                "id": r[0],
                "tipo": r[1],
                "payload": payload,
                "intentos": r[3],
                "ultimo_error": r[4],
                "creado_en": r[5],
                "estado": r[6],
            }
        )
    return out


def _marcar(conn, row_id: int, estado: str, error: str = "", intentos: int | None = None):
    if intentos is None:
        conn.execute(
            "UPDATE cola_sync SET estado = ?, ultimo_error = ? WHERE id = ?",
            (estado, error[:500], row_id),
        )
    else:
        conn.execute(
            "UPDATE cola_sync SET estado = ?, ultimo_error = ?, intentos = ? WHERE id = ?",
            (estado, error[:500], intentos, row_id),
        )


def procesar_cola_sync(limite: int = 30) -> dict:
    """Reintenta ítems pendientes (frío / contenedores)."""
    pendientes = listar_cola_sync(limite)
    ok_n = 0
    fail_n = 0
    detalles = []
    if not pendientes:
        return {"ok": True, "procesados": 0, "ok_n": 0, "fail_n": 0, "mensaje": "Cola vacía."}

    from planta.frio import enviar_control_frio_supabase
    from planta.contenedores import enviar_contenedor_supabase

    conn = _conectar_db()
    for item in pendientes:
        tipo = item["tipo"]
        payload = item["payload"]
        row_id = item["id"]
        intentos = int(item.get("intentos") or 0) + 1
        try:
            if tipo == "control_frio":
                r = enviar_control_frio_supabase(payload)
            elif tipo == "contenedor":
                r = enviar_contenedor_supabase(payload)
            else:
                _marcar(conn, row_id, "error", f"tipo desconocido: {tipo}", intentos)
                fail_n += 1
                continue
            if r.get("ok") or r.get("ya_existia") or r.get("status") == 409:
                _marcar(conn, row_id, "ok", r.get("mensaje") or "OK", intentos)
                ok_n += 1
            else:
                _marcar(conn, row_id, "pendiente", r.get("mensaje") or "fallo", intentos)
                fail_n += 1
                detalles.append(r.get("mensaje"))
        except Exception as e:
            _marcar(conn, row_id, "pendiente", str(e), intentos)
            fail_n += 1
            detalles.append(str(e))
    conn.commit()
    conn.close()
    return {
        "ok": fail_n == 0,
        "procesados": len(pendientes),
        "ok_n": ok_n,
        "fail_n": fail_n,
        "mensaje": f"Sincronizados {ok_n}/{len(pendientes)}. Fallidos: {fail_n}.",
        "detalles": detalles[:5],
    }
