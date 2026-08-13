"""Usuarios locales de planta (SQLite) — alta sin editar Secrets."""
from __future__ import annotations

import datetime
import hashlib

from planta.db import _conectar_db, inicializar_base_datos


def _hash_clave(clave: str) -> str:
    return hashlib.sha256(str(clave or "").encode("utf-8")).hexdigest()


def listar_usuarios_local(solo_activos: bool = True) -> list[dict]:
    inicializar_base_datos()
    conn = _conectar_db()
    sql = "SELECT id, usuario, rol, planta, email, activo, creado_en FROM usuarios_planta"
    if solo_activos:
        sql += " WHERE activo = 1"
    sql += " ORDER BY usuario"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "usuario": r[1],
            "rol": r[2],
            "planta": r[3] or "",
            "email": r[4] or "",
            "activo": bool(r[5]),
            "creado_en": r[6],
            "clave": "",  # nunca devolver hash
        }
        for r in rows
    ]


def accesos_desde_sqlite() -> list[dict]:
    """Candidatos de login (incluye clave hasheada para comparar aparte)."""
    inicializar_base_datos()
    conn = _conectar_db()
    rows = conn.execute(
        """
        SELECT usuario, clave, rol, planta, email
        FROM usuarios_planta WHERE activo = 1
        """
    ).fetchall()
    conn.close()
    out = []
    for u, c, rol, planta, email in rows:
        out.append(
            {
                "usuario": u,
                "clave": c,  # hash sha256
                "clave_es_hash": True,
                "rol": rol or "operario",
                "planta": planta or "",
                "email": email or "",
            }
        )
    return out


def crear_usuario_local(
    usuario: str,
    clave: str,
    rol: str = "operario",
    planta: str = "",
    email: str = "",
) -> dict:
    u = str(usuario or "").strip()
    c = str(clave or "")
    if not u or not c:
        return {"ok": False, "mensaje": "Usuario y clave obligatorios."}
    inicializar_base_datos()
    conn = _conectar_db()
    try:
        conn.execute(
            """
            INSERT INTO usuarios_planta (usuario, clave, rol, planta, email, activo, creado_en)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (
                u,
                _hash_clave(c),
                str(rol or "operario").strip().lower() or "operario",
                str(planta or "").strip(),
                str(email or "").strip(),
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()
        return {"ok": True, "mensaje": f"Usuario `{u}` creado."}
    except Exception as e:
        return {"ok": False, "mensaje": f"No se pudo crear: {e}"}
    finally:
        conn.close()


def desactivar_usuario_local(usuario: str) -> dict:
    u = str(usuario or "").strip()
    if not u:
        return {"ok": False, "mensaje": "Indique usuario."}
    inicializar_base_datos()
    conn = _conectar_db()
    cur = conn.execute(
        "UPDATE usuarios_planta SET activo = 0 WHERE usuario = ?", (u,)
    )
    conn.commit()
    n = cur.rowcount
    conn.close()
    if n:
        return {"ok": True, "mensaje": f"Usuario `{u}` desactivado."}
    return {"ok": False, "mensaje": "Usuario no encontrado."}


def verificar_clave_local(clave_plana: str, clave_guardada: str, es_hash: bool) -> bool:
    if not es_hash:
        return str(clave_plana) == str(clave_guardada)
    return _hash_clave(clave_plana) == str(clave_guardada)
