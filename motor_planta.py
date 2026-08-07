"""
Capa de acceso al motor de planta (Ed25519).

Orden de preferencia:
1) motor_rust (ed25519-dalek)
2) cryptography (Ed25519)
3) paquete puro ed25519 (si cryptography no está o falla)

LLAVE_PRIVADA en secrets = seed de 32 bytes (64 hex) o PEM PKCS8 Ed25519.
"""

from __future__ import annotations

BACKEND = "python"
MODO_FIRMA = "demo"
ULTIMO_DIAGNOSTICO = "Sin diagnóstico aún"
ALGORITMO = "Ed25519"
PYTHON_CRYPTO_LIB = "none"

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


def python_crypto_backend() -> str:
    return PYTHON_CRYPTO_LIB


# ── utilidades de hex ────────────────────────────────────────────────────────

def _hex_to_bytes(valor: str, nbytes: int, etiqueta: str) -> bytes:
    limpia = "".join(str(valor).split()).lower().removeprefix("0x")
    if len(limpia) != nbytes * 2:
        raise ValueError(
            f"{etiqueta}: se esperan {nbytes * 2} hex ({nbytes} bytes), hay {len(limpia)}"
        )
    return bytes.fromhex(limpia)


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
    """Seed Ed25519 (64 hex) o PEM, desde st.secrets."""
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
            f"Claves vistas: {disponibles or '(ninguna)'}. "
            'Use seed Ed25519: LLAVE_PRIVADA = "hex_64_caracteres"'
        )
        return None

    texto = _normalizar_llave_hex(valor)
    if texto is None:
        crudo = str(valor).strip()
        ULTIMO_DIAGNOSTICO = (
            f"Se encontró {origen} pero no es seed hex de 64 caracteres "
            f"(longitud={len(''.join(crudo.split()))})."
        )
        return None

    ULTIMO_DIAGNOSTICO = f"LLAVE_PRIVADA (Ed25519) leída desde {origen}"
    return texto


def _seed_bytes_desde_secreta(secreta: str) -> bytes:
    """Convierte secret (hex o PEM) a seed/raw private de 32 bytes."""
    texto = secreta.strip()
    if "BEGIN" in texto:
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

            key = serialization.load_pem_private_key(texto.encode("utf-8"), password=None)
            if not isinstance(key, Ed25519PrivateKey):
                raise ValueError("PEM no es Ed25519")
            return key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
        except Exception as e:
            raise ValueError(f"No se pudo leer PEM Ed25519: {e}") from e
    return _hex_to_bytes(texto, 32, "LLAVE_PRIVADA")


# ── firma / verificación Python (cryptography → ed25519) ─────────────────────

def _firmar_python(mensaje: bytes, seed: bytes | None) -> tuple[str, str, str]:
    """
    Firma Ed25519 en Python.
    Orden: cryptography → PyNaCl → ed25519 puro (si está instalado).
    Devuelve (pub_hex, firma_hex, lib_usada).
    """
    errores: list[str] = []

    # 1) cryptography
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        sk = (
            Ed25519PrivateKey.generate()
            if seed is None
            else Ed25519PrivateKey.from_private_bytes(seed)
        )
        firma = sk.sign(mensaje)
        pub = sk.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return pub.hex(), firma.hex(), "cryptography"
    except Exception as e:
        errores.append(f"cryptography: {e}")

    # 2) PyNaCl (bindings de libsodium / Ed25519)
    try:
        from nacl.signing import SigningKey

        sk = SigningKey.generate() if seed is None else SigningKey(seed)
        signed = sk.sign(mensaje)
        return bytes(sk.verify_key).hex(), bytes(signed.signature).hex(), "pynacl"
    except Exception as e:
        errores.append(f"pynacl: {e}")

    # 3) Paquete puro `ed25519` (entornos antiguos; no siempre soporta Py 3.13)
    try:
        import ed25519  # type: ignore

        if seed is None:
            sk, vk = ed25519.create_keypair()
        else:
            sk = ed25519.SigningKey(seed)
            vk = sk.get_verifying_key()
        firmado = sk.sign(mensaje)
        sig = firmado if len(firmado) == 64 else firmado[:64]
        return vk.to_bytes().hex(), bytes(sig).hex(), "ed25519"
    except Exception as e:
        errores.append(f"ed25519: {e}")

    raise RuntimeError(
        "Fallback Python Ed25519 no disponible. Instale `cryptography` o `PyNaCl`. "
        + " | ".join(errores)
    )


def _verificar_python(mensaje: bytes, firma: bytes, publica: bytes) -> str:
    """
    Verifica Ed25519 en Python. Devuelve el nombre de la librería usada.
    Lanza excepción si la firma es inválida o no hay backend.
    """
    errores: list[str] = []

    # 1) cryptography
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        vk = Ed25519PublicKey.from_public_bytes(publica)
        try:
            vk.verify(firma, mensaje)
            return "cryptography"
        except InvalidSignature as e:
            raise ValueError("Firma NO válida") from e
    except ValueError:
        raise
    except Exception as e:
        errores.append(f"cryptography: {e}")

    # 2) PyNaCl
    try:
        from nacl.exceptions import BadSignatureError
        from nacl.signing import VerifyKey

        vk = VerifyKey(publica)
        try:
            vk.verify(mensaje, firma)
            return "pynacl"
        except BadSignatureError as e:
            raise ValueError("Firma NO válida") from e
    except ValueError:
        raise
    except Exception as e:
        errores.append(f"pynacl: {e}")

    # 3) pure ed25519
    try:
        import ed25519  # type: ignore

        vk = ed25519.VerifyingKey(publica)
        try:
            try:
                vk.verify(firma, mensaje)
            except TypeError:
                vk.verify(firma + mensaje)
            return "ed25519"
        except Exception as e_inner:
            raise ValueError("Firma NO válida") from e_inner
    except ValueError:
        raise
    except Exception as e:
        errores.append(f"ed25519: {e}")

    raise RuntimeError(
        "No se pudo verificar con backends Python. " + " | ".join(errores)
    )


def _clasificar_emisor(pub_hex: str) -> str:
    oficial = llave_publica_oficial_hex()
    if not oficial:
        return "Firma Ed25519 matemáticamente válida (sin llave oficial en secrets para contrastar)"
    if oficial.lower() == pub_hex.lower():
        return "AUTÉNTICO: firma Ed25519 válida y emitida con la llave oficial de planta"
    return (
        "Firma Ed25519 matemáticamente válida, pero la llave pública NO coincide "
        "con la llave oficial de planta (posible emisor no autorizado)"
    )


# ── API pública ──────────────────────────────────────────────────────────────

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


def llave_publica_oficial_hex() -> str | None:
    """Deriva la pública oficial desde el seed de secrets (sin exponer la privada)."""
    secreta = leer_llave_privada_secrets()
    if not secreta:
        return None
    try:
        seed = _seed_bytes_desde_secreta(secreta)
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

            sk = Ed25519PrivateKey.from_private_bytes(seed)
            return sk.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            ).hex()
        except Exception:
            import ed25519  # type: ignore

            return ed25519.SigningKey(seed).get_verifying_key().to_bytes().hex()
    except Exception:
        return None


def verificar_firma_ecc(
    mensaje: str,
    firma_hex: str,
    llave_publica_hex: str,
) -> tuple[bool, str]:
    """Verifica firma Ed25519: Rust → cryptography → ed25519 puro."""
    global BACKEND, PYTHON_CRYPTO_LIB

    try:
        pub = _hex_to_bytes(llave_publica_hex, 32, "Llave pública")
        firma = _hex_to_bytes(firma_hex, 64, "Firma")
        msg = mensaje.encode("utf-8")
    except ValueError as e:
        return False, str(e)

    # 1) Rust
    if _motor_rust is not None and hasattr(_motor_rust, "verificar_firma_ed25519"):
        try:
            ok, _detalle = _motor_rust.verificar_firma_ed25519(
                mensaje, firma.hex(), pub.hex()
            )
            if not ok:
                return False, "Firma NO válida: el PDF fue alterado o no corresponde al mensaje firmado"
            BACKEND = "rust"
            return True, _clasificar_emisor(pub.hex())
        except Exception:
            pass

    # 2–3) Python
    try:
        lib = _verificar_python(msg, firma, pub)
        PYTHON_CRYPTO_LIB = lib
        BACKEND = f"python-{lib}"
        return True, _clasificar_emisor(pub.hex())
    except Exception as e:
        texto = str(e).lower()
        if "no válida" in texto or "invalid" in texto or "bad" in texto:
            return False, "Firma NO válida: el PDF fue alterado o no corresponde al mensaje firmado"
        return False, f"Error al verificar Ed25519: {e}"


def auditar_sello_pdf(datos_sello: dict) -> dict:
    """Evalúa un sello extraído de PDF (mensaje + firma + pública Ed25519)."""
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
    Firma Ed25519 → (llave_publica_hex 64, firma_hex 128).
    Rust preferente; fallback cryptography / ed25519 puro.
    """
    global BACKEND, MODO_FIRMA, ULTIMO_DIAGNOSTICO, PYTHON_CRYPTO_LIB

    secreta = llave_privada if llave_privada is not None else leer_llave_privada_secrets()
    msg = datos_reporte.encode("utf-8")

    if secreta:
        if _motor_rust is not None:
            try:
                pub_hex, firma_hex = _motor_rust.firmar_reporte_ecc(datos_reporte, secreta)
                MODO_FIRMA = "real"
                BACKEND = "rust"
                ULTIMO_DIAGNOSTICO = "Firma Ed25519 real con motor_rust + LLAVE_PRIVADA"
                return pub_hex, firma_hex
            except Exception as e:
                ULTIMO_DIAGNOSTICO = f"Rust falló; fallback Python Ed25519: {e}"

        seed = _seed_bytes_desde_secreta(secreta)
        pub_hex, firma_hex, lib = _firmar_python(msg, seed)
        MODO_FIRMA = "real"
        PYTHON_CRYPTO_LIB = lib
        BACKEND = f"python-{lib}"
        ULTIMO_DIAGNOSTICO = (
            f"Firma Ed25519 real con {lib} + LLAVE_PRIVADA "
            f"(motor_rust={'ok' if _RUST_OK else 'ausente'})"
        )
        return pub_hex, firma_hex

    # Demo sin secret
    MODO_FIRMA = "demo"
    if _motor_rust is not None:
        try:
            pub_hex, firma_hex = _motor_rust.firmar_reporte_ecc(datos_reporte, None)
            BACKEND = "rust"
            ULTIMO_DIAGNOSTICO = "Modo demo: firma Ed25519 efímera con motor_rust"
            return pub_hex, firma_hex
        except TypeError:
            try:
                pub_hex, firma_hex = _motor_rust.firmar_reporte_ecc(datos_reporte)
                BACKEND = "rust"
                return pub_hex, firma_hex
            except Exception as e:
                ULTIMO_DIAGNOSTICO = f"Demo Rust falló: {e}"
        except Exception as e:
            ULTIMO_DIAGNOSTICO = f"Demo Rust falló: {e}"

    pub_hex, firma_hex, lib = _firmar_python(msg, None)
    PYTHON_CRYPTO_LIB = lib
    BACKEND = f"python-{lib}"
    ULTIMO_DIAGNOSTICO = f"Modo demo: firma Ed25519 efímera con {lib}"
    return pub_hex, firma_hex
