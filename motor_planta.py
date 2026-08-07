"""
Capa de acceso al motor de planta.

Modo real: firma con la llave privada de st.secrets['LLAVE_PRIVADA'].
Modo demo: si no hay secret, genera una llave efímera (Rust o cryptography)
para que la app siga demostrando el sello en local / sin configuración.
"""

from __future__ import annotations

BACKEND = "python"
MODO_FIRMA = "demo"

try:
    import motor_rust as _motor_rust

    BACKEND = "rust"
except Exception:
    _motor_rust = None


def motor_activo() -> str:
    return BACKEND


def modo_firma_activo() -> str:
    return MODO_FIRMA


def validar_datos_planta(total_filas: float | int, mermas: float | int) -> tuple[float, str]:
    total = float(total_filas)
    errores = float(mermas)

    if _motor_rust is not None:
        try:
            return _motor_rust.validar_datos_planta(total, errores)
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


def leer_llave_privada_secrets() -> str | None:
    """Lee LLAVE_PRIVADA desde st.secrets sin fallar si Streamlit no está activo."""
    try:
        import streamlit as st

        valor = st.secrets.get("LLAVE_PRIVADA", None)
        if valor is None:
            return None
        texto = str(valor).strip()
        return texto or None
    except Exception:
        return None


def _cargar_llave_privada(llave_privada: str):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    texto = llave_privada.strip()
    if "BEGIN" in texto:
        return serialization.load_pem_private_key(texto.encode("utf-8"), password=None)

    hex_limpia = "".join(texto.split()).lower().removeprefix("0x")
    if len(hex_limpia) != 64:
        raise ValueError(
            "LLAVE_PRIVADA debe ser un hex de 64 caracteres (32 bytes) o un PEM PKCS8."
        )
    valor = int(hex_limpia, 16)
    if valor <= 0:
        raise ValueError("LLAVE_PRIVADA hex inválida.")
    return ec.derive_private_key(valor, ec.SECP256R1())


def _firmar_con_cryptography(datos_reporte: str, private_key) -> tuple[str, str]:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

    public_key = private_key.public_key()
    firma_der = private_key.sign(
        datos_reporte.encode("utf-8"),
        ec.ECDSA(hashes.SHA256()),
    )
    r, s = decode_dss_signature(firma_der)
    firma_hex = f"{r:064x}{s:064x}"
    pub_hex = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    ).hex()
    return pub_hex, firma_hex


def firmar_reporte_ecc(
    datos_reporte: str,
    llave_privada: str | None = None,
) -> tuple[str, str]:
    """
    Devuelve (llave_publica_hex, firma_hex) con ECDSA P-256.

    Prioridad:
    1) Modo real: llave pasada o st.secrets['LLAVE_PRIVADA']
    2) Modo demo: motor Rust efímero, o cryptography con llave temporal
    """
    global BACKEND, MODO_FIRMA

    secreta = llave_privada if llave_privada is not None else leer_llave_privada_secrets()
    if secreta:
        private_key = _cargar_llave_privada(secreta)
        pub_hex, firma_hex = _firmar_con_cryptography(datos_reporte, private_key)
        MODO_FIRMA = "real"
        BACKEND = "secrets"
        return pub_hex, firma_hex

    # Modo demo (sin secret configurado)
    MODO_FIRMA = "demo"
    if _motor_rust is not None:
        try:
            BACKEND = "rust"
            return _motor_rust.firmar_reporte_ecc(datos_reporte)
        except Exception:
            pass

    from cryptography.hazmat.primitives.asymmetric import ec

    BACKEND = "python"
    private_key = ec.generate_private_key(ec.SECP256R1())
    return _firmar_con_cryptography(datos_reporte, private_key)
