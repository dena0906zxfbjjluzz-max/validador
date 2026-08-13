"""SQLite local de planta (planta_calidad_prod.db)."""
from __future__ import annotations

import datetime
import hashlib
import io
import json
import os
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd


# Proyecto root (no planta/) para que el .db siga en la raíz del repo / Cloud.
_DB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = "planta_calidad_prod.db"
DB_PATH = os.path.join(_DB_DIR, DB_NAME)

def _conectar_db():
    """Abre (o crea) la base genérica planta_calidad_prod.db."""
    os.makedirs(_DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def inicializar_base_datos():
    """
    Crea la BD y tablas de auditoría si no existen.
    Al usar una base nueva (p. ej. tras el rename genérico), el esquema se
    construye desde cero con la estructura limpia actual.
    """
    es_nueva = not os.path.exists(DB_PATH)
    conn = _conectar_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial_sesion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hora TEXT,
            archivo TEXT,
            registros INTEGER,
            confiabilidad TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bitacora_cambios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT,
            fila_indice INTEGER,
            columna TEXT,
            valor_anterior TEXT,
            nuevo_valor TEXT,
            inspector TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS control_frio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camara TEXT,
            temperatura REAL,
            hora_registro TEXT,
            estado TEXT,
            inspector TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contenedores_despacho (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking TEXT,
            contenedor TEXT,
            precinto_linea TEXT,
            precinto_senasa TEXT,
            destino TEXT,
            estado TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial_reportes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT NOT NULL,
            lote TEXT NOT NULL,
            hash_sha256 TEXT NOT NULL UNIQUE,
            responsable TEXT NOT NULL,
            archivo TEXT,
            producto TEXT,
            registros INTEGER,
            firma_ecc TEXT,
            llave_publica TEXT,
            mensaje TEXT,
            modo_firma TEXT,
            backend TEXT
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_historial_reportes_fecha ON historial_reportes(fecha_hora DESC)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_bitacora_fecha ON bitacora_cambios(fecha_hora)"
    )

    # Solo en bases antiguas con esquema incompleto (no aplica a archivos nuevos)
    if not es_nueva:
        try:
            cursor.execute("ALTER TABLE control_frio ADD COLUMN inspector TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute(
                "DELETE FROM bitacora_cambios WHERE datetime(fecha_hora) < datetime('now', '-7 days')"
            )
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()
    return DB_PATH


def calcular_hash_reporte(mensaje: str, firma: str, llave_publica: str = "") -> str:
    """Huella SHA-256 del sello ECC (mensaje + firma + llave pública)."""
    payload = f"{mensaje}|{firma}|{llave_publica}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def guardar_historial_db(hora, archivo, registros, confiabilidad):
    conn = _conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM historial_sesion WHERE archivo = ?", (archivo,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO historial_sesion (hora, archivo, registros, confiabilidad) VALUES (?, ?, ?, ?)",
                       (hora, archivo, registros, confiabilidad))
        conn.commit()
    conn.close()

def cargar_historial_db():
    conn = _conectar_db()
    df_db = pd.read_sql_query("SELECT hora AS Hora, archivo AS Archivo, registros AS Registros, confiabilidad AS Confiabilidad FROM historial_sesion", conn)
    conn.close()
    return df_db.to_dict("records")

def guardar_cambio_db(fecha_hora, fila_indice, columna, valor_anterior, nuevo_valor, inspector):
    conn = _conectar_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO bitacora_cambios (fecha_hora, fila_indice, columna, valor_anterior, nuevo_valor, inspector) VALUES (?, ?, ?, ?, ?, ?)",
                   (fecha_hora, fila_indice, columna, valor_anterior, nuevo_valor, inspector))
    conn.commit()
    conn.close()

def cargar_bitacora_db():
    conn = _conectar_db()
    df_bit = pd.read_sql_query("SELECT fecha_hora AS 'Fecha/Hora', fila_indice AS 'Fila Índice', columna AS 'Columna Modificada', valor_anterior AS 'Valor Anterior', nuevo_valor AS 'Nuevo Valor', inspector AS 'Inspector' FROM bitacora_cambios", conn)
    conn.close()
    return df_bit.to_dict("records")
