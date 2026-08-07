"""
Capa de acceso al motor de planta.

Intenta usar el módulo nativo Rust (PyO3). Si no está compilado
(p. ej. en Streamlit Cloud sin toolchain), usa respaldo ECDSA P-256
con la librería `cryptography` para que el sello digital siga funcionando.
"""

from __future__ import annotations

BACKEND = "python"

try:
    import motor_rust as _motor_rust

    BACKEND = "rust"
except Exception:
    _motor_rust = None


def motor_activo() -> str:
    return BACKEND


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

    # Misma idea que el motor Rust: eficiencia relativa errores/filas
    porcentaje = max(0.0, min(100.0, (1.0 - (errores / total)) * 100.0))
    estado = (
        "Aprobado - Planta Eficiente"
        if porcentaje > 95.0
        else "Alerta - Revisar Línea de Producción"
    )
    return round(porcentaje, 4), estado


def firmar_reporte_ecc(datos_reporte: str) -> tuple[str, str]:
    """
    Devuelve (llave_publica_hex, firma_hex) con ECDSA sobre curva P-256.
    """
    if _motor_rust is not None:
        try:
            return _motor_rust.firmar_reporte_ecc(datos_reporte)
        except Exception:
            pass

    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

    private_key = ec.generate_private_key(ec.SECP256R1())
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
