"""Datos de muestra para modo demo comercial."""
from __future__ import annotations

import datetime

from planta.db import inicializar_base_datos
from planta.frio import guardar_frio_db


def sembrar_datos_demo(forzar: bool = False) -> dict:
    """Inserta lecturas de frío de muestra si la base está vacía (o forzar=True)."""
    inicializar_base_datos()
    from planta.db import _conectar_db

    conn = _conectar_db()
    n = conn.execute("SELECT COUNT(*) FROM control_frio").fetchone()[0]
    conn.close()
    if n > 0 and not forzar:
        return {"ok": True, "sembrado": False, "mensaje": "Ya hay datos; demo no sobrescribe."}

    ahora = datetime.datetime.now()
    muestras = [
        ("Pre-Cámara 01", 4.2, "FRIO_OPTIMO", "Palta Hass"),
        ("Túnel 02", 8.5, "RUPTURA_CADENA_FRIO", "Palta Hass"),
        ("Cámara 03", 3.8, "FRIO_OPTIMO", "Arándano"),
        ("Pre-Cámara 01", 4.0, "FRIO_OPTIMO", "Palta Hass"),
        ("Túnel 02", 7.1, "RUPTURA_CADENA_FRIO", "Palta Hass"),
    ]
    ids = []
    for i, (cam, temp, est, prod) in enumerate(muestras):
        h = (ahora - datetime.timedelta(hours=i * 2)).strftime("%Y-%m-%d %H:%M:%S")
        ids.append(
            guardar_frio_db(
                camara=cam,
                temperatura=temp,
                hora_registro=h,
                estado=est,
                inspector="Demo Comercial",
                producto=prod,
            )
        )
    return {
        "ok": True,
        "sembrado": True,
        "mensaje": f"Demo: {len(ids)} lecturas de muestra cargadas.",
        "ids": ids,
    }
