"""
Capa de acceso al motor de planta.

Modo real: usa st.secrets['LLAVE_PRIVADA'] (seed Ed25519, 32 bytes / 64 hex).
Preferencia de firma/verificación: motor Rust (ed25519-dalek); si no está, cryptography.
"""

from __future__ import annotations

BACKEND = "python"
MODO_FIRMA = "demo"
ULTIMO_DIAGNOSTICO = "Sin diagnóstico aún"
ALGORITMO = "Ed25519"

try:
    import motor_rust as _motor_rust

    _RUST_OK = True
except Exception as _rust_err:
    _motor_rust = None
    _RUST_OK = False
    ULTIMO_DIAGNOSTICO = f"motor_rust no importable: {_rust_err}"


def motor_activo() -> str:
    return BACKEND


def modo_firma_activo() -> str:
    return MODO_FIRMA


def diagnostico() -> str:
    return ULTIMO_DIAGNOSTICO


def rust_disponible() -> bool:
    return _RUST_OK and _motor_rust is not None


def validar_datos_planta(total_filas: float | int, mermas: float | int) -> tuple[float, str]:
    total = float(total_filas)
    errores = float(mermas)

    if _motor_rust is not None:
        try:
            return _motor_rust.validar_datos_planta(int(total), errores)
        except Exception:
            pass

    if total <= 0:
        return 100.0, "Sin registros para auditar"

    porcentaje = max(0.0, min(100.0, (1.0 - (errores / total)) * 100.0))
    estado = (
        "Aprobado - Planta Eficiente"
        if porcentaje > 95.0
        else "Alerta - Revisar Línea de Producción"
    )
    return round(porcentaje, 4), estado


def _normalizar_llave_hex(valor) -> str | None:
    texto = str(valor).strip().strip('"').strip("'")
    if not texto:
        return None
    if "BEGIN" in texto:
        return texto
    hex_limpia = "".join(texto.split()).lower().removeprefix("0x")
    if len(hex_limpia) != 64:
        return None
    return hex_limpia


def _buscar_llave_anidada(obj, nombre: str = "LLAVE_PRIVADA", ruta: str = "st.secrets"):
    try:
        if nombre in obj:
            return obj[nombre], f"{ruta}['{nombre}']"
    except Exception:
        pass

    try:
        keys = list(obj.keys())
    except Exception:
        return None, None

    for k in keys:
        try:
            hijo = obj[k]
        except Exception:
            continue
        if hasattr(hijo, "keys"):
            hallado, ruta_hallada = _buscar_llave_anidada(hijo, nombre, f"{ruta}['{k}']")
            if hallado is not None:
                return hallado, ruta_hallada
    return None, None


def leer_llave_privada_secrets() -> str | None:
    """
    Busca LLAVE_PRIVADA en st.secrets (seed Ed25519 de 32 bytes en hex).
    """
    global ULTIMO_DIAGNOSTICO

    try:
        import streamlit as st
    except Exception as e:
        ULTIMO_DIAGNOSTICO = f"No se pudo importar streamlit para secrets: {e}"
        return None

    try:
        secrets_obj = st.secrets
    except Exception as e:
        ULTIMO_DIAGNOSTICO = f"st.secrets no disponible: {e}"
        return None

    try:
        disponibles = sorted(str(k) for k in secrets_obj.keys())
    except Exception:
        disponibles = []

    valor = None
    origen = None

    try:
        valor = secrets_obj["LLAVE_PRIVADA"]
        origen = "st.secrets['LLAVE_PRIVADA']"
    except Exception:
        valor = None

    if valor is None:
        try:
            valor = secrets_obj["credenciales"]["LLAVE_PRIVADA"]
            origen = "st.secrets['credenciales']['LLAVE_PRIVADA']"
        except Exception:
            valor = None

    if valor is None:
        valor, origen = _buscar_llave_anidada(secrets_obj)

    if valor is None:
        ULTIMO_DIAGNOSTICO = (
            "No existe LLAVE_PRIVADA en secrets. "
            f"Claves vistas en secrets: {disponibles or '(ninguna)'}. "
            "Use un seed Ed25519 hex de 64 caracteres:\n"
            'LLAVE_PRIVADA = "tu_seed_hex_ed25519"'
        )
        return None

    texto = _normalizar_llave_hex(valor)
    if texto is None:
        crudo = str(valor).strip()
        ULTIMO_DIAGNOSTICO = (
            f"Se encontró {origen} pero no es seed hex de 64 caracteres "
            f"(longitud actual={len(''.join(crudo.split()))})."
        )
        return None

    ULTIMO_DIAGNOSTICO = f"LLAVE_PRIVADA (Ed25519) leída desde {origen}"
    return texto


def _cargar_llave_privada(llave_privada: str):
    """Carga seed Ed25519 (hex 32 bytes) o PEM PKCS8."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    texto = llave_privada.strip()
    if "BEGIN" in texto:
        key = serialization.load_pem_private_key(texto.encode("utf-8"), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError("El PEM no es una llave privada Ed25519.")
        return key

    hex_limpia = "".join(texto.split()).lower().removeprefix("0x")
    if len(hex_limpia) != 64:
        raise ValueError("LLAVE_PRIVADA debe ser seed hex de 64 caracteres (32 bytes) o PEM Ed25519.")
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(hex_limpia))


def _firmar_con_cryptography(datos_reporte: str, private_key) -> tuple[str, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    if not isinstance(private_key, Ed25519PrivateKey):
        raise TypeError("Se esperaba Ed25519PrivateKey")

    public_key = private_key.public_key()
    firma = private_key.sign(datos_reporte.encode("utf-8"))
    pub_hex = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()
    return pub_hex, firma.hex()


def llave_publica_oficial_hex() -> str | None:
    """Deriva la llave pública oficial Ed25519 desde st.secrets['LLAVE_PRIVADA']."""
    from cryptography.hazmat.primitives import serialization

    secreta = leer_llave_privada_secrets()
    if not secreta:
        return None
    private_key = _cargar_llave_privada(secreta)
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()


def verificar_firma_ecc(
    mensaje: str,
    firma_hex: str,
    llave_publica_hex: str,
) -> tuple[bool, str]:
    """
    Verifica matemáticamente una firma Ed25519.
    Preferencia: motor Rust; respaldo: cryptography.
    """
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    pub_limpia = "".join(str(llave_publica_hex).split()).lower().removeprefix("0x")
    firma_limpia = "".join(str(firma_hex).split()).lower().removeprefix("0x")

    # Preferir Rust
    if _motor_rust is not None and hasattr(_motor_rust, "verificar_firma_ed25519"):
        try:
            ok, detalle_rust = _motor_rust.verificar_firma_ed25519(
                mensaje, firma_limpia, pub_limpia
            )
            if not ok:
                return False, detalle_rust
            oficial = llave_publica_oficial_hex()
            if oficial and oficial.lower() == pub_limpia.lower():
                return True, "AUTÉNTICO: firma Ed25519 válida y emitida con la llave oficial de planta"
            if oficial:
                return True, (
                    "Firma Ed25519 matemáticamente válida, pero la llave pública NO coincide "
                    "con la llave oficial de planta (posible emisor no autorizado)"
                )
            return True, "AUTÉNTICO: firma Ed25519 válida"
        except Exception as e:
            # Continúa con cryptography
            _ = e

    try:
        if len(firma_limpia) != 128:
            return False, f"Firma inválida: se esperan 128 hex (64 bytes), hay {len(firma_limpia)}"
        if len(pub_limpia) != 64:
            return False, f"Llave pública inválida: se esperan 64 hex (Ed25519), hay {len(pub_limpia)}"

        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_limpia))
        public_key.verify(bytes.fromhex(firma_limpia), mensaje.encode("utf-8"))
    except InvalidSignature:
        return False, "Firma NO válida: el PDF fue alterado o no corresponde al mensaje firmado"
    except Exception as e:
        return False, f"Error al verificar: {e}"

    oficial = llave_publica_oficial_hex()
    if oficial:
        if oficial.lower() == pub_limpia.lower():
            return True, "AUTÉNTICO: firma Ed25519 válida y emitida con la llave oficial de planta"
        return True, (
            "Firma Ed25519 matemáticamente válida, pero la llave pública NO coincide "
            "con la llave oficial de planta (posible emisor no autorizado)"
        )

    return True, "Firma Ed25519 matemáticamente válida (no hay llave oficial en secrets para contrastar emisor)"


def auditar_sello_pdf(datos_sello: dict) -> dict:
    """Evalúa un sello extraído de PDF y devuelve un resultado estructurado."""
    mensaje = (datos_sello.get("mensaje") or "").strip()
    firma = (datos_sello.get("firma") or "").strip()
    publica = (datos_sello.get("llave_publica") or "").strip()

    if not mensaje or not firma or not publica:
        return {
            "ok": False,
            "estado": "INCOMPLETO",
            "detalle": "El PDF no contiene mensaje, firma y llave pública Ed25519 parseables",
            "mensaje": mensaje,
            "firma": firma,
            "llave_publica": publica,
        }

    ok, detalle = verificar_firma_ecc(mensaje, firma, publica)
    return {
        "ok": ok,
        "estado": "AUTENTICO" if ok and "AUTÉNTICO" in detalle else ("VALIDO_DESCONOCIDO" if ok else "ALTERADO"),
        "detalle": detalle,
        "mensaje": mensaje,
        "firma": firma,
        "llave_publica": publica,
    }


def firmar_reporte_ecc(
    datos_reporte: str,
    llave_privada: str | None = None,
) -> tuple[str, str]:
    """
    Devuelve (llave_publica_hex, firma_hex) con Ed25519.

    1) Modo real + Rust si hay LLAVE_PRIVADA y motor_rust
    2) Modo real + cryptography si hay LLAVE_PRIVADA pero no Rust
    3) Modo demo efímero (Rust o Python)
    """
    global BACKEND, MODO_FIRMA, ULTIMO_DIAGNOSTICO

    secreta = llave_privada if llave_privada is not None else leer_llave_privada_secrets()

    if secreta:
        if _motor_rust is not None:
            try:
                pub_hex, firma_hex = _motor_rust.firmar_reporte_ecc(datos_reporte, secreta)
                MODO_FIRMA = "real"
                BACKEND = "rust"
                ULTIMO_DIAGNOSTICO = "Firma Ed25519 real con motor_rust + st.secrets['LLAVE_PRIVADA']"
                return pub_hex, firma_hex
            except Exception as e:
                ULTIMO_DIAGNOSTICO = f"Rust falló con LLAVE_PRIVADA; respaldo cryptography Ed25519: {e}"

        private_key = _cargar_llave_privada(secreta)
        pub_hex, firma_hex = _firmar_con_cryptography(datos_reporte, private_key)
        MODO_FIRMA = "real"
        BACKEND = "python"
        if "Rust falló" not in ULTIMO_DIAGNOSTICO:
            ULTIMO_DIAGNOSTICO = (
                "Firma Ed25519 real con cryptography + st.secrets['LLAVE_PRIVADA'] "
                "(motor_rust no disponible en este entorno)"
            )
        return pub_hex, firma_hex

    MODO_FIRMA = "demo"
    if _motor_rust is not None:
        try:
            pub_hex, firma_hex = _motor_rust.firmar_reporte_ecc(datos_reporte, None)
            BACKEND = "rust"
            ULTIMO_DIAGNOSTICO = (
                "Modo demo: sin LLAVE_PRIVADA. Firma Ed25519 efímera con motor_rust. "
                + ULTIMO_DIAGNOSTICO
            )
            return pub_hex, firma_hex
        except TypeError:
            pub_hex, firma_hex = _motor_rust.firmar_reporte_ecc(datos_reporte)
            BACKEND = "rust"
            return pub_hex, firma_hex
        except Exception as e:
            ULTIMO_DIAGNOSTICO = f"Demo Rust falló: {e}"

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    BACKEND = "python"
    private_key = Ed25519PrivateKey.generate()
    if "No existe st.secrets" not in ULTIMO_DIAGNOSTICO and "LLAVE_PRIVADA" not in ULTIMO_DIAGNOSTICO:
        ULTIMO_DIAGNOSTICO = "Modo demo: sin LLAVE_PRIVADA y sin motor_rust; firma Ed25519 efímera Python"
    return _firmar_con_cryptography(datos_reporte, private_key)
