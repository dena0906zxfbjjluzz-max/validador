"""
Cortafuego de seguridad de aplicación (capa software).

Protege el acceso a planta, endurece la sesión, valida entradas y
registra eventos de seguridad. No reemplaza WAF/hosting, pero
bloquea abuso común dentro de Streamlit.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from typing import Any

# ─── Política por defecto (ajustable por secrets) ────────────────────────────
MAX_INTENTOS_LOGIN = 5
VENTANA_INTENTOS_SEG = 15 * 60  # 15 minutos
BLOQUEO_SEG = 15 * 60  # 15 minutos de lockout
MAX_LONGITUD_TEXTO = 4_000
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
SESSION_TIMEOUT_SEG = 8 * 60 * 60  # 8 horas de inactividad
EXT_ARCHIVO_OK = frozenset({".xlsx", ".csv", ".pdf", ".png", ".jpg", ".jpeg", ".webp"})

# Controles de path / inyección superficial
_RE_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_RE_SOLO_HASH = re.compile(r"^[a-fA-F0-9]{64}$")
_RE_ALNUM_OP = re.compile(r"^[\w\s\-./:#@+|{}[\],\"'=]{1,4000}$", re.UNICODE)

_DB_DIR = os.path.dirname(os.path.abspath(__file__))
_DB_PATH = os.path.join(_DB_DIR, "planta_calidad_prod.db")


def _conectar_db():
    os.makedirs(_DB_DIR, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    return conn


def inicializar_cortafuego_db() -> None:
    """Tabla de bitácora de seguridad (intentos, bloqueos, sesión)."""
    conn = _conectar_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS bitacora_seguridad (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT NOT NULL,
            evento TEXT NOT NULL,
            detalle TEXT,
            severidad TEXT DEFAULT 'info',
            ip_session TEXT,
            usuario TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bitacora_seguridad_fecha
        ON bitacora_seguridad(fecha_hora DESC)
        """
    )
    conn.commit()
    conn.close()


def registrar_evento(
    evento: str,
    detalle: str = "",
    severidad: str = "info",
    usuario: str = "",
    session_id: str = "",
) -> None:
    try:
        inicializar_cortafuego_db()
        conn = _conectar_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO bitacora_seguridad
                (fecha_hora, evento, detalle, severidad, ip_session, usuario)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                str(evento)[:120],
                str(detalle)[:800],
                severidad[:20],
                (session_id or "")[:64],
                (usuario or "")[:120],
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        # Nunca tumbar la app por un fallo de bitácora
        pass


def _leer_int_secret(nombre: str, default: int) -> int:
    try:
        import streamlit as st

        secrets_obj = st.secrets
        try:
            creds = secrets_obj["credenciales"]
            if nombre in creds:
                return int(creds[nombre])
        except Exception:
            pass
        try:
            if nombre in secrets_obj:
                return int(secrets_obj[nombre])
        except Exception:
            pass
    except Exception:
        pass
    return default


def politica() -> dict[str, int]:
    return {
        "max_intentos": _leer_int_secret("FIREWALL_MAX_LOGIN", MAX_INTENTOS_LOGIN),
        "ventana_seg": _leer_int_secret("FIREWALL_VENTANA_SEG", VENTANA_INTENTOS_SEG),
        "bloqueo_seg": _leer_int_secret("FIREWALL_BLOQUEO_SEG", BLOQUEO_SEG),
        "timeout_sesion_seg": _leer_int_secret(
            "FIREWALL_TIMEOUT_SEG", SESSION_TIMEOUT_SEG
        ),
        "max_upload_bytes": _leer_int_secret(
            "FIREWALL_MAX_UPLOAD_MB", MAX_UPLOAD_BYTES // (1024 * 1024)
        )
        * 1024
        * 1024,
    }


def _ahora() -> float:
    return time.time()


def _init_state(session_state: Any) -> None:
    if "fw_intentos_login" not in session_state:
        session_state["fw_intentos_login"] = []  # timestamps de fallos
    if "fw_bloqueado_hasta" not in session_state:
        session_state["fw_bloqueado_hasta"] = 0.0
    if "fw_session_token" not in session_state:
        session_state["fw_session_token"] = ""
    if "fw_ultimo_pulso" not in session_state:
        session_state["fw_ultimo_pulso"] = 0.0
    if "fw_usuario" not in session_state:
        session_state["fw_usuario"] = ""
    if "fw_login_ok_count" not in session_state:
        session_state["fw_login_ok_count"] = 0


def sanitizar_texto(valor: str, max_len: int = MAX_LONGITUD_TEXTO) -> str:
    """Quita controles, recorta longitud (anti overflow)."""
    if valor is None:
        return ""
    s = str(valor)
    s = _RE_CONTROL.sub("", s)
    s = s.replace("\x00", "")
    if len(s) > max_len:
        s = s[:max_len]
    return s.strip()


def validar_hash_sha256(valor: str) -> bool:
    return bool(_RE_SOLO_HASH.fullmatch((valor or "").strip()))


def validar_entrada_operativa(valor: str) -> tuple[bool, str]:
    """
    Valida IDs de caja/lote/SSCC/texto QR de uso diario.
    Permite JSON simple y hashes.
    """
    s = sanitizar_texto(valor)
    if not s:
        return False, "Entrada vacía."
    if len(s) > MAX_LONGITUD_TEXTO:
        return False, "Entrada demasiado larga."
    # Permitir JSON de QR o hash puro
    if s.startswith("{") and s.endswith("}"):
        if len(s) > 2_000:
            return False, "JSON QR demasiado extenso."
        return True, s
    if validar_hash_sha256(s):
        return True, s.lower()
    if not _RE_ALNUM_OP.fullmatch(s):
        return False, "Caracteres no permitidos en la entrada."
    return True, s


def validar_nombre_archivo(nombre: str) -> tuple[bool, str]:
    nombre = sanitizar_texto(nombre or "", 240)
    if not nombre or nombre in (".", ".."):
        return False, "Nombre de archivo inválido."
    if "/" in nombre or "\\" in nombre or ".." in nombre:
        return False, "Ruta de archivo no permitida."
    ext = os.path.splitext(nombre)[1].lower()
    if ext not in EXT_ARCHIVO_OK:
        return False, f"Extensión no permitida ({ext or 'sin extensión'})."
    return True, nombre


def validar_upload_bytes(
    nombre: str, data: bytes | None, max_bytes: int | None = None
) -> tuple[bool, str]:
    ok, msg = validar_nombre_archivo(nombre)
    if not ok:
        return False, msg
    if data is None:
        return False, "Archivo sin contenido."
    limite = max_bytes or politica()["max_upload_bytes"]
    if len(data) > limite:
        mb = limite / (1024 * 1024)
        return False, f"Archivo excede el límite de {mb:.0f} MB del cortafuego."
    if len(data) == 0:
        return False, "Archivo vacío."
    return True, "OK"


def comparar_secretos(a: str, b: str) -> bool:
    """Comparación de credenciales en tiempo constante (misma longitud)."""
    aa = (a or "").encode("utf-8")
    bb = (b or "").encode("utf-8")
    # Trabajo constante incluso si longitudes difieren
    dig_a = hashlib.sha256(aa).digest()
    dig_b = hashlib.sha256(bb).digest()
    digests_iguales = hmac.compare_digest(dig_a, dig_b)
    if len(aa) != len(bb):
        return False
    return hmac.compare_digest(aa, bb) and digests_iguales


def credenciales_validas(
    usuario_in: str, clave_in: str, usuario_ok: str, clave_ok: str
) -> bool:
    u_ok = comparar_secretos(
        sanitizar_texto(usuario_in, 120), sanitizar_texto(usuario_ok, 120)
    )
    c_ok = comparar_secretos(clave_in or "", clave_ok or "")
    return bool(u_ok and c_ok)


def estado_bloqueo(session_state: Any) -> tuple[bool, int]:
    """(bloqueado, segundos_restantes)."""
    _init_state(session_state)
    hasta = float(session_state.get("fw_bloqueado_hasta") or 0)
    ahora = _ahora()
    if hasta > ahora:
        return True, int(hasta - ahora)
    return False, 0


def _purgar_intentos(session_state: Any, ventana_seg: int) -> list[float]:
    ahora = _ahora()
    prev = list(session_state.get("fw_intentos_login") or [])
    vivos = [t for t in prev if ahora - float(t) <= ventana_seg]
    session_state["fw_intentos_login"] = vivos
    return vivos


def registrar_fallo_login(session_state: Any, usuario: str = "") -> dict:
    """Registra intento fallido y aplica lockout si corresponde."""
    _init_state(session_state)
    pol = politica()
    vivos = _purgar_intentos(session_state, pol["ventana_seg"])
    vivos.append(_ahora())
    session_state["fw_intentos_login"] = vivos

    registrar_evento(
        "LOGIN_FAIL",
        f"Intento fallido ({len(vivos)}/{pol['max_intentos']})",
        severidad="warn",
        usuario=sanitizar_texto(usuario, 80),
        session_id=str(session_state.get("fw_session_token") or ""),
    )

    if len(vivos) >= pol["max_intentos"]:
        session_state["fw_bloqueado_hasta"] = _ahora() + pol["bloqueo_seg"]
        session_state["fw_intentos_login"] = []
        registrar_evento(
            "LOGIN_LOCKOUT",
            f"Bloqueo temporal {pol['bloqueo_seg']}s tras {pol['max_intentos']} fallos",
            severidad="critical",
            usuario=sanitizar_texto(usuario, 80),
        )
        return {
            "bloqueado": True,
            "segundos": pol["bloqueo_seg"],
            "intentos": pol["max_intentos"],
            "max": pol["max_intentos"],
        }

    return {
        "bloqueado": False,
        "segundos": 0,
        "intentos": len(vivos),
        "max": pol["max_intentos"],
    }


def registrar_login_ok(session_state: Any, usuario: str) -> str:
    """Abre sesión endurecida (token + pulso)."""
    _init_state(session_state)
    token = secrets.token_hex(24)
    session_state["autenticado"] = True
    session_state["fw_session_token"] = token
    session_state["fw_ultimo_pulso"] = _ahora()
    session_state["fw_usuario"] = sanitizar_texto(usuario, 120)
    session_state["fw_intentos_login"] = []
    session_state["fw_bloqueado_hasta"] = 0.0
    session_state["fw_login_ok_count"] = int(session_state.get("fw_login_ok_count") or 0) + 1
    registrar_evento(
        "LOGIN_OK",
        "Acceso de planta concedido",
        severidad="info",
        usuario=session_state["fw_usuario"],
        session_id=token[:16],
    )
    return token


def cerrar_sesion(session_state: Any, motivo: str = "logout") -> None:
    usuario = session_state.get("fw_usuario") or ""
    token = str(session_state.get("fw_session_token") or "")[:16]
    session_state["autenticado"] = False
    session_state["fw_session_token"] = ""
    session_state["fw_ultimo_pulso"] = 0.0
    session_state["fw_usuario"] = ""
    registrar_evento(
        "LOGOUT",
        motivo,
        severidad="info",
        usuario=usuario,
        session_id=token,
    )


def sesion_valida(session_state: Any) -> tuple[bool, str]:
    """
    Verifica autenticación + timeout + token de sesión.
    Debe llamarse en cada rerun de area protegida.
    """
    _init_state(session_state)
    if not session_state.get("autenticado"):
        return False, "no_auth"

    token = session_state.get("fw_session_token") or ""
    # Migración suave: sesión anterior al cortafuego (autenticado sin token)
    if not token or len(str(token)) < 16:
        token = secrets.token_hex(24)
        session_state["fw_session_token"] = token
        session_state["fw_ultimo_pulso"] = _ahora()
        if not session_state.get("fw_usuario"):
            session_state["fw_usuario"] = "inspector"
        registrar_evento(
            "SESSION_MIGRATE",
            "Token de sesión emitido (sesión previa al cortafuego)",
            severidad="info",
            usuario=session_state.get("fw_usuario") or "",
            session_id=token[:16],
        )
        return True, "migrated"

    pol = politica()
    ultimo = float(session_state.get("fw_ultimo_pulso") or 0)
    ahora = _ahora()
    if ultimo > 0 and (ahora - ultimo) > pol["timeout_sesion_seg"]:
        cerrar_sesion(session_state, "timeout_inactividad")
        return False, "timeout"

    # Pulso de actividad
    session_state["fw_ultimo_pulso"] = ahora
    return True, "ok"


def intentar_login(
    session_state: Any,
    usuario_in: str,
    clave_in: str,
    usuario_ok: str,
    clave_ok: str,
) -> dict:
    """
    Pipeline completo de login con cortafuego.
    Returns: ok, mensaje, bloqueado, intentos, max, segundos_bloqueo
    """
    _init_state(session_state)
    bloqueado, segs = estado_bloqueo(session_state)
    if bloqueado:
        return {
            "ok": False,
            "bloqueado": True,
            "segundos_bloqueo": segs,
            "mensaje": (
                f"🔒 Cortafuego: acceso temporalmente bloqueado. "
                f"Reintente en {segs // 60}m {segs % 60}s."
            ),
            "intentos": 0,
            "max": politica()["max_intentos"],
        }

    usuario_in = sanitizar_texto(usuario_in, 120)
    # No sanitizar agresivo la clave (puede tener símbolos) — solo quitar nulls
    clave_in = (clave_in or "").replace("\x00", "")[:256]

    if not usuario_in or not clave_in:
        return {
            "ok": False,
            "bloqueado": False,
            "segundos_bloqueo": 0,
            "mensaje": "Indique usuario y contraseña.",
            "intentos": 0,
            "max": politica()["max_intentos"],
        }

    if credenciales_validas(usuario_in, clave_in, usuario_ok, clave_ok):
        registrar_login_ok(session_state, usuario_in)
        return {
            "ok": True,
            "bloqueado": False,
            "segundos_bloqueo": 0,
            "mensaje": "✅ Acceso concedido · sesión protegida por cortafuego.",
            "intentos": 0,
            "max": politica()["max_intentos"],
            "rol": None,
        }

    info = registrar_fallo_login(session_state, usuario_in)
    if info["bloqueado"]:
        return {
            "ok": False,
            "bloqueado": True,
            "segundos_bloqueo": info["segundos"],
            "mensaje": (
                f"🚨 Cortafuego: demasiados intentos fallidos. "
                f"Bloqueo {info['segundos'] // 60} minutos."
            ),
            "intentos": info["intentos"],
            "max": info["max"],
            "rol": None,
        }

    resto = info["max"] - info["intentos"]
    return {
        "ok": False,
        "bloqueado": False,
        "segundos_bloqueo": 0,
        "mensaje": (
            f"Usuario o contraseña incorrectos. "
            f"Intentos restantes: {resto} (antes del bloqueo)."
        ),
        "intentos": info["intentos"],
        "max": info["max"],
        "rol": None,
    }


def intentar_login_lista(
    session_state: Any,
    usuario_in: str,
    clave_in: str,
    candidatos: list[dict],
    *,
    abrir_sesion: bool = True,
) -> dict:
    """
    Login contra varios usuarios de planta.
    cada candidato: {usuario, clave, rol} con rol 'operario' | 'supervisor'.
    Si abrir_sesion=False, solo valida (para flujo OTP).
    """
    _init_state(session_state)
    bloqueado, segs = estado_bloqueo(session_state)
    if bloqueado:
        return {
            "ok": False,
            "bloqueado": True,
            "segundos_bloqueo": segs,
            "mensaje": (
                f"🔒 Cortafuego: acceso temporalmente bloqueado. "
                f"Reintente en {segs // 60}m {segs % 60}s."
            ),
            "intentos": 0,
            "max": politica()["max_intentos"],
            "rol": None,
        }

    usuario_in = sanitizar_texto(usuario_in, 120)
    clave_in = (clave_in or "").replace("\x00", "")[:256]
    if not usuario_in or not clave_in:
        return {
            "ok": False,
            "bloqueado": False,
            "segundos_bloqueo": 0,
            "mensaje": "Indique usuario y contraseña.",
            "intentos": 0,
            "max": politica()["max_intentos"],
            "rol": None,
        }

    for cand in candidatos or []:
        u_ok = str(cand.get("usuario") or "").strip()
        c_ok = str(cand.get("clave") or "")
        rol = normalizar_rol(cand.get("rol"))
        if u_ok and credenciales_validas(usuario_in, clave_in, u_ok, c_ok):
            planta = str(cand.get("planta") or "").strip()
            if abrir_sesion:
                registrar_login_ok(session_state, usuario_in)
                session_state["rol_planta"] = rol
                if planta:
                    session_state["nombre_planta_sesion"] = planta
                mensaje = (
                    f"✅ Acceso concedido · rol {rol}"
                    + (f" · {planta}" if planta else "")
                    + "."
                )
            else:
                mensaje = "Credenciales válidas. Confirme el código OTP."
            return {
                "ok": True,
                "bloqueado": False,
                "segundos_bloqueo": 0,
                "mensaje": mensaje,
                "intentos": 0,
                "max": politica()["max_intentos"],
                "rol": rol,
                "planta": planta or None,
                "usuario": usuario_in,
            }

    info = registrar_fallo_login(session_state, usuario_in)
    if info["bloqueado"]:
        return {
            "ok": False,
            "bloqueado": True,
            "segundos_bloqueo": info["segundos"],
            "mensaje": (
                f"🚨 Cortafuego: demasiados intentos fallidos. "
                f"Bloqueo {info['segundos'] // 60} minutos."
            ),
            "intentos": info["intentos"],
            "max": info["max"],
            "rol": None,
        }
    resto = info["max"] - info["intentos"]
    return {
        "ok": False,
        "bloqueado": False,
        "segundos_bloqueo": 0,
        "mensaje": (
            f"Usuario o contraseña incorrectos. "
            f"Intentos restantes: {resto} (antes del bloqueo)."
        ),
        "intentos": info["intentos"],
        "max": info["max"],
        "rol": None,
    }


def _leer_secret_seguridad(clave: str, default: str = "") -> str:
    try:
        import streamlit as st

        for ruta in (("seguridad", clave), ("credenciales", clave), (clave,)):
            cur = st.secrets
            ok = True
            for parte in ruta:
                try:
                    cur = cur[parte]
                except Exception:
                    ok = False
                    break
            if ok and str(cur).strip():
                return str(cur).strip()
    except Exception:
        pass
    return default


def otp_esta_habilitado() -> bool:
    """
    OTP por correo:
      [seguridad] otp_habilitado = "true" | "false" | "auto"
    auto (default): activo si hay SMTP/email en [avisos].
    """
    flag = _leer_secret_seguridad("otp_habilitado", "auto").lower()
    if flag in ("0", "false", "no", "off"):
        return False
    if flag in ("1", "true", "yes", "on", "si", "sí"):
        return True
    # auto
    try:
        from planta.avisos import _config_avisos

        return bool(_config_avisos().get("email_ok"))
    except Exception:
        return False


def otp_email_destino() -> str:
    dest = _leer_secret_seguridad("otp_email", "")
    if dest:
        return dest
    try:
        from planta.avisos import _config_avisos

        return str(_config_avisos().get("email_to") or "").strip()
    except Exception:
        return ""


def iniciar_otp_pendiente(
    session_state: Any,
    *,
    usuario: str,
    rol: str,
    planta: str = "",
    minutos: int = 10,
) -> dict:
    """
    Genera OTP de 6 dígitos, lo guarda hasheado en sesión y lo envía por email.
    No abre sesión aún.
    """
    _init_state(session_state)
    codigo = f"{secrets.randbelow(1_000_000):06d}"
    digests = hashlib.sha256(codigo.encode("utf-8")).hexdigest()
    session_state["otp_pendiente"] = True
    session_state["otp_hash"] = digests
    session_state["otp_expira"] = _ahora() + max(60, int(minutos) * 60)
    session_state["otp_intentos"] = 0
    session_state["otp_usuario"] = sanitizar_texto(usuario, 120)
    session_state["otp_rol"] = normalizar_rol(rol)
    session_state["otp_planta"] = str(planta or "").strip()
    session_state["autenticado"] = False

    destino = otp_email_destino()
    if not destino:
        limpiar_otp_pendiente(session_state)
        return {
            "ok": False,
            "mensaje": "OTP activo pero falta email destino (seguridad.otp_email o avisos.email_to).",
        }

    try:
        from planta.avisos import enviar_aviso_email

        asunto = "Validador · código de acceso"
        cuerpo = (
            f"Código de acceso (OTP): {codigo}\n"
            f"Usuario: {usuario}\n"
            f"Válido {minutos} minutos.\n"
            "Si no solicitó el ingreso, ignore este correo."
        )
        envio = enviar_aviso_email(asunto, cuerpo, para=destino)
    except Exception as e:
        limpiar_otp_pendiente(session_state)
        return {"ok": False, "mensaje": f"No se pudo enviar OTP: {e}"}

    if not envio.get("ok"):
        limpiar_otp_pendiente(session_state)
        return {
            "ok": False,
            "mensaje": envio.get("mensaje") or "Fallo al enviar el correo OTP.",
        }

    registrar_evento(
        "OTP_ENVIADO",
        f"OTP enviado a {destino[:3]}***",
        severidad="info",
        usuario=usuario,
    )
    enmascarado = destino
    if "@" in destino:
        nom, dom = destino.split("@", 1)
        enmascarado = (nom[:2] + "***@" + dom) if nom else "***@" + dom
    return {
        "ok": True,
        "mensaje": f"Código enviado a {enmascarado}. Revise su correo.",
        "destino": enmascarado,
    }


def limpiar_otp_pendiente(session_state: Any) -> None:
    for k in (
        "otp_pendiente",
        "otp_hash",
        "otp_expira",
        "otp_intentos",
        "otp_usuario",
        "otp_rol",
        "otp_planta",
    ):
        session_state.pop(k, None)


def verificar_otp_y_abrir_sesion(session_state: Any, codigo_in: str) -> dict:
    """Valida OTP pendiente y abre sesión de planta."""
    _init_state(session_state)
    if not session_state.get("otp_pendiente"):
        return {"ok": False, "mensaje": "No hay verificación OTP pendiente."}

    expira = float(session_state.get("otp_expira") or 0)
    if _ahora() > expira:
        limpiar_otp_pendiente(session_state)
        return {"ok": False, "mensaje": "El código OTP expiró. Vuelva a ingresar."}

    intentos = int(session_state.get("otp_intentos") or 0)
    if intentos >= 5:
        limpiar_otp_pendiente(session_state)
        registrar_fallo_login(session_state, session_state.get("otp_usuario") or "")
        return {"ok": False, "mensaje": "Demasiados intentos OTP. Reinicie el login."}

    codigo = re.sub(r"\D", "", str(codigo_in or ""))[:8]
    esperado = str(session_state.get("otp_hash") or "")
    digests = hashlib.sha256(codigo.encode("utf-8")).hexdigest()
    if not codigo or not hmac.compare_digest(digests, esperado):
        session_state["otp_intentos"] = intentos + 1
        resto = 5 - (intentos + 1)
        return {
            "ok": False,
            "mensaje": f"Código incorrecto. Intentos OTP restantes: {max(0, resto)}.",
        }

    usuario = session_state.get("otp_usuario") or ""
    rol = normalizar_rol(session_state.get("otp_rol"))
    planta = str(session_state.get("otp_planta") or "").strip()
    limpiar_otp_pendiente(session_state)
    registrar_login_ok(session_state, usuario)
    session_state["rol_planta"] = rol
    if planta:
        session_state["nombre_planta_sesion"] = planta
    registrar_evento("OTP_OK", "OTP verificado", severidad="info", usuario=usuario)
    return {
        "ok": True,
        "mensaje": f"✅ Acceso concedido · rol {rol}" + (f" · {planta}" if planta else "") + ".",
        "rol": rol,
        "planta": planta or None,
    }


def normalizar_rol(rol: Any) -> str:
    r = str(rol or "supervisor").strip().lower()
    if r in ("operario", "operador", "op", "linea", "línea"):
        return "operario"
    return "supervisor"


def es_supervisor(session_state: Any) -> bool:
    return normalizar_rol(session_state.get("rol_planta")) == "supervisor"


def resumen_panel(session_state: Any) -> dict:
    """Datos seguros para UI (sin secretos)."""
    _init_state(session_state)
    pol = politica()
    bloqueado, segs = estado_bloqueo(session_state)
    return {
        "activo": True,
        "usuario": session_state.get("fw_usuario") or "—",
        "token_corto": (session_state.get("fw_session_token") or "")[:8] + "…"
        if session_state.get("fw_session_token")
        else "—",
        "timeout_min": pol["timeout_sesion_seg"] // 60,
        "max_intentos": pol["max_intentos"],
        "bloqueado": bloqueado,
        "bloqueo_seg": segs,
        "max_upload_mb": pol["max_upload_bytes"] // (1024 * 1024),
    }


def ultimos_eventos(limite: int = 15) -> list[dict]:
    try:
        inicializar_cortafuego_db()
        conn = _conectar_db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT fecha_hora, evento, detalle, severidad, usuario
            FROM bitacora_seguridad
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limite),),
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "fecha": r[0],
                "evento": r[1],
                "detalle": r[2],
                "severidad": r[3],
                "usuario": r[4],
            }
            for r in rows
        ]
    except Exception:
        return []
