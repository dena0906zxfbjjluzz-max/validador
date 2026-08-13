"""Lectura de balanza por puerto serial (opcional) + parseo de peso."""
from __future__ import annotations

import re
from typing import Any


def listar_puertos_serial() -> list[str]:
    """Puertos disponibles (vacío si no hay pyserial o no hay puertos)."""
    try:
        from serial.tools import list_ports
    except Exception:
        return []
    try:
        return [p.device for p in list_ports.comports()]
    except Exception:
        return []


def parsear_peso_desde_texto(texto: str) -> float | None:
    """
    Extrae el primer número razonable (kg) de una trama de balanza.
    Acepta '4.520 kg', 'ST,GS,+  4.52 kg', 'N 4,52' etc.
    """
    if not texto:
        return None
    t = str(texto).replace(",", ".")
    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", t)
    for n in nums:
        try:
            v = float(n)
        except Exception:
            continue
        if 0.01 <= abs(v) <= 500:
            return abs(v)
    return None


def leer_peso_serial(
    puerto: str,
    baudrate: int = 9600,
    timeout: float = 2.0,
    bytes_max: int = 128,
) -> dict[str, Any]:
    """
    Lee una trama desde el puerto serial y parsea peso.
    En Streamlit Cloud suele no haber USB: use captura manual.
    """
    puerto = (puerto or "").strip()
    if not puerto:
        return {"ok": False, "peso": None, "crudo": "", "mensaje": "Indique puerto COM/tty."}
    try:
        import serial
    except Exception:
        return {
            "ok": False,
            "peso": None,
            "crudo": "",
            "mensaje": "Instale pyserial (`pip install pyserial`) para balanza USB.",
        }
    try:
        with serial.Serial(puerto, baudrate=int(baudrate), timeout=float(timeout)) as ser:
            crudo = ser.read(int(bytes_max)).decode("utf-8", errors="ignore").strip()
        if not crudo:
            # algunos equipos solo responden al poll
            try:
                with serial.Serial(puerto, baudrate=int(baudrate), timeout=float(timeout)) as ser:
                    ser.write(b"P\r\n")
                    crudo = ser.read(int(bytes_max)).decode("utf-8", errors="ignore").strip()
            except Exception:
                pass
        peso = parsear_peso_desde_texto(crudo)
        if peso is None:
            return {
                "ok": False,
                "peso": None,
                "crudo": crudo,
                "mensaje": f"Sin peso parseable. Trama: {crudo[:80] or '(vacía)'}",
            }
        return {
            "ok": True,
            "peso": peso,
            "crudo": crudo,
            "mensaje": f"Peso leído: {peso} kg",
        }
    except Exception as e:
        return {
            "ok": False,
            "peso": None,
            "crudo": "",
            "mensaje": f"Error serial: {type(e).__name__}: {e}",
        }
