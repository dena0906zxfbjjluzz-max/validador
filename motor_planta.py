"""
Capa de acceso al motor de planta.

Modo real: usa exactamente st.secrets['LLAVE_PRIVADA'].
Preferencia de firma: motor Rust nativo; si no está compilado, cryptography.
Modo demo: sin secret → llave efímera.
"""

from __future__ import annotations

BACKEND = "python"
MODO_FIRMA = "demo"
ULTIMO_DIAGNOSTICO = "Sin diagnóstico aún"

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
            # PyO3 espera enteros para usize
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


def leer_llave_privada_secrets() -> str | None:
    """
    Busca exactamente la clave de primer nivel LLAVE_PRIVADA en st.secrets.
    Guarda diagnóstico legible si falla (para mostrarlo en la UI).
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

    # Acceso exacto pedido: st.secrets['LLAVE_PRIVADA']
    try:
        valor = secrets_obj["LLAVE_PRIVADA"]
    except KeyError:
        try:
            disponibles = sorted(str(k) for k in secrets_obj.keys())
        except Exception:
            disponibles = []
        ULTIMO_DIAGNOSTICO = (
            "No existe st.secrets['LLAVE_PRIVADA']. "
            f"Claves vistas en secrets: {disponibles or '(ninguna)'}. "
            "En Cloud → Settings → Secrets use exactamente:\n"
            'LLAVE_PRIVADA = "tu_hex_de_64_caracteres"'
        )
        return None
    except Exception as e:
        ULTIMO_DIAGNOSTICO = f"Error leyendo st.secrets['LLAVE_PRIVADA']: {e}"
        return None

    texto = str(valor).strip().strip('"').strip("'")
    if not texto:
        ULTIMO_DIAGNOSTICO = "st.secrets['LLAVE_PRIVADA'] está vacío"
        return None

    # Si Cloud guardó el hex sin comillas y TOML lo truncó/alteró, avisar por longitud
    hex_limpia = "".join(texto.split()).lower().removeprefix("0x")
    if "BEGIN" not in texto and len(hex_limpia) != 64:
        ULTIMO_DIAGNOSTICO = (
            f"LLAVE_PRIVADA encontrada pero longitud hex={len(hex_limpia)} (se esperan 64). "
            "Asegúrese de ponerla entre comillas en Secrets."
        )
        return None

    ULTIMO_DIAGNOSTICO = "LLAVE_PRIVADA leída correctamente desde st.secrets"
    return texto


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

    1) Modo real + Rust si hay LLAVE_PRIVADA y motor_rust
    2) Modo real + cryptography si hay LLAVE_PRIVADA pero no Rust
    3) Modo demo efímero (Rust o Python)
    """
    global BACKEND, MODO_FIRMA, ULTIMO_DIAGNOSTICO

    secreta = llave_privada if llave_privada is not None else leer_llave_privada_secrets()

    if secreta:
        # Preferir Rust con la misma llave del secret
        if _motor_rust is not None:
            try:
                pub_hex, firma_hex = _motor_rust.firmar_reporte_ecc(datos_reporte, secreta)
                MODO_FIRMA = "real"
                BACKEND = "rust"
                ULTIMO_DIAGNOSTICO = "Firma real con motor_rust + st.secrets['LLAVE_PRIVADA']"
                return pub_hex, firma_hex
            except Exception as e:
                ULTIMO_DIAGNOSTICO = f"Rust falló con LLAVE_PRIVADA; respaldo cryptography: {e}"

        private_key = _cargar_llave_privada(secreta)
        pub_hex, firma_hex = _firmar_con_cryptography(datos_reporte, private_key)
        MODO_FIRMA = "real"
        BACKEND = "python"
        if "Rust falló" not in ULTIMO_DIAGNOSTICO:
            ULTIMO_DIAGNOSTICO = (
                "Firma real con cryptography + st.secrets['LLAVE_PRIVADA'] "
                "(motor_rust no disponible en este entorno)"
            )
        return pub_hex, firma_hex

    # Modo demo (sin secret)
    MODO_FIRMA = "demo"
    if _motor_rust is not None:
        try:
            pub_hex, firma_hex = _motor_rust.firmar_reporte_ecc(datos_reporte, None)
            BACKEND = "rust"
            ULTIMO_DIAGNOSTICO = (
                "Modo demo: sin LLAVE_PRIVADA. Firma efímera con motor_rust. "
                + ULTIMO_DIAGNOSTICO
            )
            return pub_hex, firma_hex
        except TypeError:
            # Compatibilidad con build viejo sin 2º argumento
            pub_hex, firma_hex = _motor_rust.firmar_reporte_ecc(datos_reporte)
            BACKEND = "rust"
            return pub_hex, firma_hex
        except Exception as e:
            ULTIMO_DIAGNOSTICO = f"Demo Rust falló: {e}"

    from cryptography.hazmat.primitives.asymmetric import ec

    BACKEND = "python"
    private_key = ec.generate_private_key(ec.SECP256R1())
    if "No existe st.secrets" not in ULTIMO_DIAGNOSTICO and "LLAVE_PRIVADA" not in ULTIMO_DIAGNOSTICO:
        ULTIMO_DIAGNOSTICO = "Modo demo: sin LLAVE_PRIVADA y sin motor_rust; firma efímera Python"
    return _firmar_con_cryptography(datos_reporte, private_key)
