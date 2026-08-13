"""Tests mínimos de humo (sin Streamlit UI)."""
from __future__ import annotations

import pandas as pd

import funciones
from planta.balanza import parsear_peso_desde_texto
from planta.packing import (
    exportar_packing_csv_bytes,
    resolver_mapa_columnas,
    campos_criticos_sin_mapear,
)


def test_parsear_peso_balanza():
    assert parsear_peso_desde_texto("ST,GS,+  4.52 kg") == 4.52
    assert parsear_peso_desde_texto("N 4,52") == 4.52
    assert parsear_peso_desde_texto("") is None


def test_mapeo_columnas_manual():
    df = pd.DataFrame({"BATCH": ["A"], "KG": ["4.1"], "SIZE": ["L"]})
    m = resolver_mapa_columnas(df, {"lote": "BATCH", "peso": "KG", "calibre": "SIZE"})
    assert m["lote"] == "BATCH"
    assert campos_criticos_sin_mapear(m) == []


def test_export_csv_bytes():
    df = pd.DataFrame({"LOTE": ["1"], "PESO": ["4"]})
    raw = exportar_packing_csv_bytes(df)
    assert b"LOTE" in raw
    assert b"PESO" in raw


def test_dashboard_resumen_ok():
    d = funciones.resumen_dashboard_turno()
    assert d.get("ok") is True
    assert "kpis" in d
    assert "estado_turno" in d


def test_hash_reporte():
    h = funciones.calcular_hash_reporte("msg", "sig", "pub")
    assert len(h) == 64


def test_informe_semanal_y_cola():
    info = funciones.consolidar_informe_semanal(7)
    assert info.get("ok") is True
    assert "kpis" in info
    pdf = funciones.generar_pdf_informe_semanal(info, planta_nombre="Test")
    raw = pdf.getvalue() if hasattr(pdf, "getvalue") else pdf
    assert raw[:4] == b"%PDF"
    cola = funciones.listar_cola_sync(5)
    assert isinstance(cola, list)


def test_usuarios_hash_local():
    from planta.usuarios import _hash_clave, verificar_clave_local

    h = _hash_clave("secreto")
    assert verificar_clave_local("secreto", h, True)
    assert not verificar_clave_local("otra", h, True)
