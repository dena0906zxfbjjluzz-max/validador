"""Módulo 7: alertas/tendencias + dashboard de turno."""
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

from planta.db import _conectar_db, inicializar_base_datos
from planta.packing import mapear_columnas_trazabilidad, encontrar_columna
# ─── Módulo 7: Alertas y tendencias (inteligencia operativa de planta) ───────
# Fase A: reglas + estadísticas. Fase B: anomalías por z-score (sin sklearn).


def cargar_frio_dataframe(limite: int = 500) -> pd.DataFrame:
    """Devuelve lecturas de control_frio como DataFrame para análisis."""
    inicializar_base_datos()
    conn = _conectar_db()
    try:
        df = pd.read_sql_query(
            """
            SELECT id, camara, temperatura, hora_registro, estado,
                   COALESCE(inspector, '') AS inspector,
                   COALESCE(producto, '') AS producto
            FROM control_frio
            ORDER BY id DESC
            LIMIT ?
            """,
            conn,
            params=(int(limite),),
        )
    except Exception:
        df = pd.read_sql_query(
            """
            SELECT id, camara, temperatura, hora_registro, estado,
                   COALESCE(inspector, '') AS inspector
            FROM control_frio
            ORDER BY id DESC
            LIMIT ?
            """,
            conn,
            params=(int(limite),),
        )
        if not df.empty:
            df["producto"] = ""
    conn.close()
    if df.empty:
        return df
    df["temperatura"] = pd.to_numeric(df["temperatura"], errors="coerce")
    df["hora_dt"] = pd.to_datetime(df["hora_registro"], errors="coerce")
    return df


def _serie_zscore(valores: pd.Series) -> pd.Series:
    """Z-score robusto; NaN si no hay desviación usable."""
    s = pd.to_numeric(valores, errors="coerce")
    media = s.mean()
    std = s.std(ddof=0)
    if pd.isna(std) or std < 1e-9:
        return pd.Series([float("nan")] * len(s), index=s.index)
    return (s - media) / std


def _alerta(severidad: str, origen: str, titulo: str, detalle: str, metrica: str = "") -> dict:
    return {
        "severidad": severidad,  # critica | advertencia | info
        "origen": origen,
        "titulo": titulo,
        "detalle": detalle,
        "metrica": metrica,
    }


def analizar_tendencias_frio(
    limite: int = 500,
    z_umbral: float = 2.5,
    min_muestras_anomalia: int = 8,
) -> dict:
    """
    Analiza historial de cadena de frío (SQLite).
    Reglas: rupturas, % fuera de rango por cámara, tendencia reciente.
    Anomalías: |z-score| > umbral por cámara (cuando hay historial suficiente).
    """
    df = cargar_frio_dataframe(limite=limite)
    alertas: list[dict] = []
    por_camara: list[dict] = []
    serie_chart: pd.DataFrame | None = None

    if df.empty:
        return {
            "ok": True,
            "sin_datos": True,
            "total_lecturas": 0,
            "rupturas": 0,
            "pct_ruptura": 0.0,
            "alertas": [
                _alerta(
                    "info",
                    "frio",
                    "Sin historial de frío",
                    "Registre lecturas en el Módulo 4 para activar tendencias y anomalías.",
                )
            ],
            "por_camara": [],
            "serie_chart": None,
            "resumen": "Sin lecturas de cadena de frío en SQLite.",
        }

    total = len(df)
    es_ruptura = df["estado"].astype(str).str.upper().str.contains("RUPTURA", na=False)
    rupturas = int(es_ruptura.sum())
    pct_ruptura = round((rupturas / total) * 100, 1) if total else 0.0

    if pct_ruptura >= 20:
        alertas.append(
            _alerta(
                "critica",
                "frio",
                "Alta tasa de ruptura de frío",
                f"{rupturas} de {total} lecturas fuera de rango ({pct_ruptura}%).",
                f"{pct_ruptura}%",
            )
        )
    elif pct_ruptura >= 8:
        alertas.append(
            _alerta(
                "advertencia",
                "frio",
                "Rupturas de frío recurrentes",
                f"{rupturas} lecturas fuera de rango ({pct_ruptura}%). Revisar cámaras.",
                f"{pct_ruptura}%",
            )
        )

    # Serie para gráfico (cronológica)
    df_ord = df.dropna(subset=["temperatura"]).sort_values("hora_dt", ascending=True)
    if not df_ord.empty:
        serie_chart = (
            df_ord.assign(etiqueta=df_ord["hora_registro"].astype(str).str[-8:])
            .groupby(["camara", "etiqueta"], as_index=False)["temperatura"]
            .mean()
        )

    for camara, g in df.groupby(df["camara"].astype(str)):
        g = g.dropna(subset=["temperatura"]).copy()
        n = len(g)
        if n == 0:
            continue
        rup_c = int(g["estado"].astype(str).str.upper().str.contains("RUPTURA", na=False).sum())
        pct_c = round((rup_c / n) * 100, 1)
        media = round(float(g["temperatura"].mean()), 2)
        std = round(float(g["temperatura"].std(ddof=0) or 0), 2)

        # Tendencia: últimas 5 vs anteriores (usa id si la hora empata)
        sort_cols = [c for c in ("hora_dt", "id") if c in g.columns]
        g_ord = g.sort_values(sort_cols, ascending=True) if sort_cols else g
        tendencia = "estable"
        delta = 0.0
        if n >= 6:
            ult = g_ord["temperatura"].tail(5).mean()
            prev = g_ord["temperatura"].iloc[:-5]
            ant = prev.tail(5).mean() if len(prev) else ult
            delta = round(float(ult - ant), 2)
            if delta >= 0.8:
                tendencia = "calentamiento"
            elif delta <= -0.8:
                tendencia = "enfriamiento"

        anomalias = 0
        if n >= min_muestras_anomalia:
            z = _serie_zscore(g_ord["temperatura"])
            anomalias = int((z.abs() > z_umbral).sum())

        fila = {
            "camara": camara,
            "lecturas": n,
            "rupturas": rup_c,
            "pct_ruptura": pct_c,
            "temp_media": media,
            "temp_std": std,
            "tendencia": tendencia,
            "delta_reciente": delta,
            "anomalias_z": anomalias,
        }
        por_camara.append(fila)

        if pct_c >= 25 and n >= 4:
            alertas.append(
                _alerta(
                    "critica",
                    "frio",
                    f"Cámara crítica: {camara}",
                    f"{rup_c}/{n} rupturas ({pct_c}%). Media {media} °C.",
                    f"{pct_c}%",
                )
            )
        elif tendencia == "calentamiento" and delta >= 0.8:
            alertas.append(
                _alerta(
                    "advertencia",
                    "frio",
                    f"Tendencia al alza: {camara}",
                    f"Últimas lecturas +{delta} °C vs. tramo anterior. Anticipar revisión.",
                    f"+{delta} °C",
                )
            )
        if anomalias > 0:
            alertas.append(
                _alerta(
                    "advertencia",
                    "frio",
                    f"Anomalía térmica: {camara}",
                    f"{anomalias} lectura(s) con |z-score| > {z_umbral} (patrón atípico).",
                    f"{anomalias} outlier(s)",
                )
            )

    # Detalle de rupturas recientes (máx. 3; evita ruido si la tasa ya es alta)
    if 0 < rupturas <= 8:
        recientes = df.loc[es_ruptura].head(3)
        for _, row in recientes.iterrows():
            alertas.append(
                _alerta(
                    "advertencia",
                    "frio",
                    "Ruptura registrada",
                    f"{row.get('camara')} · {row.get('temperatura')} °C · "
                    f"{row.get('hora_registro')} · {row.get('producto') or 'N/D'}",
                    str(row.get("estado") or ""),
                )
            )

    n_crit = sum(1 for a in alertas if a["severidad"] == "critica")
    n_adv = sum(1 for a in alertas if a["severidad"] == "advertencia")
    resumen = (
        f"{total} lecturas · {rupturas} rupturas ({pct_ruptura}%) · "
        f"{n_crit} crítica(s) · {n_adv} advertencia(s)"
    )

    return {
        "ok": True,
        "sin_datos": False,
        "total_lecturas": total,
        "rupturas": rupturas,
        "pct_ruptura": pct_ruptura,
        "alertas": alertas,
        "por_camara": sorted(por_camara, key=lambda x: (-x["pct_ruptura"], -x["anomalias_z"])),
        "serie_chart": serie_chart,
        "resumen": resumen,
    }


def analizar_patrones_packing(
    df: pd.DataFrame,
    cols_mapa: dict | None = None,
    peso_min_caja: float = 4.0,
    max_merma_permitida: float = 5.0,
    z_umbral_peso: float = 2.5,
) -> dict:
    """
    Patrones del archivo de packing cargado: pesos, LMR por productor/fundo, merma.
    """
    alertas: list[dict] = []
    cols_mapa = cols_mapa or mapear_columnas_trazabilidad(df)
    total = len(df) if df is not None else 0
    if df is None or total == 0:
        return {
            "ok": True,
            "sin_datos": True,
            "alertas": [
                _alerta("info", "packing", "Sin archivo de packing", "Cargue un Excel/CSV para analizar patrones.")
            ],
            "por_productor": [],
            "stats_peso": {},
            "resumen": "Sin datos de packing.",
        }

    # Pesos
    col_peso = cols_mapa.get("peso")
    stats_peso: dict = {}
    if col_peso and col_peso in df.columns:
        pesos = pd.to_numeric(df[col_peso], errors="coerce")
        validos = pesos.dropna()
        bajo_min = int((pesos < float(peso_min_caja)).fillna(False).sum())
        media = round(float(validos.mean()), 2) if len(validos) else 0.0
        std = round(float(validos.std(ddof=0) or 0), 2) if len(validos) else 0.0
        stats_peso = {
            "media": media,
            "std": std,
            "bajo_minimo": bajo_min,
            "n_validos": int(len(validos)),
            "vacios": int(pesos.isna().sum() + (df[col_peso].astype(str).str.strip() == "").sum()),
        }
        if bajo_min > 0:
            sev = "critica" if bajo_min >= max(3, int(total * 0.05)) else "advertencia"
            alertas.append(
                _alerta(
                    sev,
                    "packing",
                    "Cajas bajo peso mínimo",
                    f"{bajo_min} registro(s) < {peso_min_caja} kg (media lote {media} kg).",
                    f"{bajo_min} cajas",
                )
            )
        if len(validos) >= 10 and std > 0:
            z = _serie_zscore(validos)
            outliers = int((z.abs() > z_umbral_peso).sum())
            stats_peso["outliers_z"] = outliers
            if outliers > 0:
                alertas.append(
                    _alerta(
                        "advertencia",
                        "packing",
                        "Pesos atípicos (z-score)",
                        f"{outliers} caja(s) con peso fuera del patrón del lote (|z| > {z_umbral_peso}).",
                        f"{outliers} outlier(s)",
                    )
                )

    # LMR por productor / fundo
    col_lmr = cols_mapa.get("lmr")
    col_prod = cols_mapa.get("productor")
    col_fundo = cols_mapa.get("fundo")
    por_productor: list[dict] = []

    if col_lmr and col_lmr in df.columns:
        estados = df[col_lmr].astype(str).map(interpretar_estado_lmr)
        n_rech = int((estados == "rechazado").sum())
        n_alerta = int((estados == "alerta").sum())
        if n_rech > 0:
            alertas.append(
                _alerta(
                    "critica",
                    "packing",
                    "LMR rechazado en archivo",
                    f"{n_rech} registro(s) con veredicto de rechazo / supera LMR.",
                    f"{n_rech}",
                )
            )
        elif n_alerta > 0:
            alertas.append(
                _alerta(
                    "advertencia",
                    "packing",
                    "LMR en zona de alerta",
                    f"{n_alerta} registro(s) cercanos al límite / cuarentena.",
                    f"{n_alerta}",
                )
            )

        grupo_col = col_prod if col_prod and col_prod in df.columns else None
        if grupo_col:
            tmp = df.copy()
            tmp["_estado_lmr"] = estados
            tmp["_grupo"] = tmp[grupo_col].astype(str).str.strip().replace("", "N/D")
            for nombre, g in tmp.groupby("_grupo"):
                n = len(g)
                rech = int((g["_estado_lmr"] == "rechazado").sum())
                aler = int((g["_estado_lmr"] == "alerta").sum())
                riesgo = round(((rech + aler) / n) * 100, 1) if n else 0.0
                fila = {
                    "productor": nombre,
                    "registros": n,
                    "lmr_alerta": aler,
                    "lmr_rechazo": rech,
                    "pct_riesgo": riesgo,
                }
                if col_fundo and col_fundo in g.columns:
                    fundos = sorted({str(x).strip() for x in g[col_fundo] if str(x).strip()})
                    fila["fundos"] = ", ".join(fundos[:4]) + ("…" if len(fundos) > 4 else "")
                else:
                    fila["fundos"] = "N/D"
                por_productor.append(fila)
                if riesgo >= 30 and n >= 3:
                    alertas.append(
                        _alerta(
                            "critica" if rech > 0 else "advertencia",
                            "packing",
                            f"Productor con patrón LMR: {nombre}",
                            f"{rech} rechazo(s) y {aler} alerta(s) en {n} cajas ({riesgo}%).",
                            f"{riesgo}%",
                        )
                    )
            por_productor.sort(key=lambda x: (-x["pct_riesgo"], -x["lmr_rechazo"]))

    # Merma / descarte
    col_cat = None
    for c in df.columns:
        cu = str(c).upper()
        if "CATEGORIA" in cu or cu in ("CAT", "CATEGORÍA"):
            col_cat = c
            break
    pct_merma = 0.0
    if col_cat:
        cats = df[col_cat].astype(str).str.upper().str.strip()
        descarte = int(cats.isin(["DESCARTE", "MERMA", "RECHAZO"]).sum())
        pct_merma = round((descarte / total) * 100, 2) if total else 0.0
        if pct_merma > float(max_merma_permitida):
            alertas.append(
                _alerta(
                    "critica",
                    "packing",
                    "Merma sobre el límite",
                    f"Merma/descarte {pct_merma}% (límite {max_merma_permitida}%).",
                    f"{pct_merma}%",
                )
            )

    vacios = int((df.astype(str).apply(lambda s: s.str.strip()) == "").sum().sum())
    if total and vacios > total * 2:
        alertas.append(
            _alerta(
                "advertencia",
                "packing",
                "Alta incompleción de datos",
                f"{vacios} celdas vacías en el lote. Revisar antes de congelar.",
                f"{vacios} vacíos",
            )
        )

    n_crit = sum(1 for a in alertas if a["severidad"] == "critica")
    n_adv = sum(1 for a in alertas if a["severidad"] == "advertencia")
    resumen = f"{total} filas · merma {pct_merma}% · {n_crit} crítica(s) · {n_adv} advertencia(s)"

    return {
        "ok": True,
        "sin_datos": False,
        "alertas": alertas,
        "por_productor": por_productor,
        "stats_peso": stats_peso,
        "pct_merma": pct_merma,
        "total_filas": total,
        "resumen": resumen,
    }


def consolidar_inteligencia_planta(
    df_packing: pd.DataFrame | None = None,
    cols_mapa: dict | None = None,
    peso_min_caja: float = 4.0,
    max_merma_permitida: float = 5.0,
    limite_frio: int = 500,
) -> dict:
    """
    Combina tendencias de frío + patrones de packing en un informe único.
    """
    frio = analizar_tendencias_frio(limite=limite_frio)
    packing = (
        analizar_patrones_packing(
            df_packing,
            cols_mapa=cols_mapa,
            peso_min_caja=peso_min_caja,
            max_merma_permitida=max_merma_permitida,
        )
        if df_packing is not None
        else {
            "ok": True,
            "sin_datos": True,
            "alertas": [],
            "por_productor": [],
            "stats_peso": {},
            "resumen": "Packing no cargado en esta sesión.",
        }
    )

    alertas = list(frio.get("alertas") or []) + list(packing.get("alertas") or [])
    orden = {"critica": 0, "advertencia": 1, "info": 2}
    alertas.sort(key=lambda a: (orden.get(a.get("severidad"), 9), a.get("origen", "")))

    n_crit = sum(1 for a in alertas if a["severidad"] == "critica")
    n_adv = sum(1 for a in alertas if a["severidad"] == "advertencia")
    n_info = sum(1 for a in alertas if a["severidad"] == "info")

    if n_crit:
        veredicto = "ACCION_REQUERIDA"
        veredicto_ui = "Se detectaron alertas críticas. Revisar antes de cerrar el lote o despachar."
    elif n_adv:
        veredicto = "VIGILANCIA"
        veredicto_ui = "Hay tendencias a vigilar. Anticipar revisión de frío / calidad."
    else:
        veredicto = "ESTABLE"
        veredicto_ui = "Sin patrones de riesgo relevantes en los datos disponibles."

    return {
        "ok": True,
        "veredicto": veredicto,
        "veredicto_ui": veredicto_ui,
        "contadores": {"criticas": n_crit, "advertencias": n_adv, "info": n_info},
        "alertas": alertas,
        "frio": frio,
        "packing": packing,
    }


# ─── Dashboard de turno + alertas de frío activas ─────────────────────────────


def _parse_fecha_hora_flexible(valor) -> datetime.datetime | None:
    if valor is None:
        return None
    s = str(valor).strip()
    if not s:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%H:%M:%S",
    ):
        try:
            dt = datetime.datetime.strptime(s, fmt)
            if fmt == "%H:%M:%S":
                hoy = datetime.date.today()
                return datetime.datetime.combine(hoy, dt.time())
            return dt
        except ValueError:
            continue
    try:
        return pd.to_datetime(s, errors="coerce").to_pydatetime()
    except Exception:
        return None


def alertas_frio_activas(limite: int = 30, horas_ventana: int = 12) -> dict:
    """
    Rupturas de cadena de frío recientes que requieren atención del turno.
    """
    inicializar_base_datos()
    df = cargar_frio_dataframe(limite=max(limite * 3, 100))
    if df.empty:
        return {
            "ok": True,
            "activas": [],
            "total": 0,
            "nivel": "ESTABLE",
            "mensaje": "Sin lecturas de frío registradas.",
        }

    es_ruptura = df["estado"].astype(str).str.upper().str.contains("RUPTURA", na=False)
    rupturas = df.loc[es_ruptura].copy()
    if rupturas.empty:
        return {
            "ok": True,
            "activas": [],
            "total": 0,
            "nivel": "ESTABLE",
            "mensaje": "Sin rupturas de frío en el historial reciente.",
        }

    ahora = datetime.datetime.now()
    corte = ahora - datetime.timedelta(hours=int(horas_ventana))
    activas = []
    for _, row in rupturas.iterrows():
        dt = _parse_fecha_hora_flexible(row.get("hora_registro"))
        if dt is not None and dt < corte:
            continue
        activas.append(
            {
                "camara": str(row.get("camara") or "N/D"),
                "temperatura": row.get("temperatura"),
                "hora": str(row.get("hora_registro") or ""),
                "producto": str(row.get("producto") or ""),
                "inspector": str(row.get("inspector") or ""),
                "estado": str(row.get("estado") or ""),
            }
        )
        if len(activas) >= limite:
            break

    total = len(activas)
    if total >= 3:
        nivel = "CRITICO"
        mensaje = f"{total} rupturas de frío en las últimas {horas_ventana} h."
    elif total >= 1:
        nivel = "ALERTA"
        mensaje = f"{total} ruptura(s) de frío reciente(s)."
    else:
        nivel = "ESTABLE"
        mensaje = f"Sin rupturas en las últimas {horas_ventana} h."

    return {
        "ok": True,
        "activas": activas,
        "total": total,
        "nivel": nivel,
        "mensaje": mensaje,
        "horas_ventana": horas_ventana,
    }


def resumen_dashboard_turno(fecha: datetime.date | None = None) -> dict:
    """
    KPIs del turno / día para el jefe de planta:
    sellos ECC, rupturas de frío, contenedores, cargas de packing.
    """
    inicializar_base_datos()
    dia = fecha or datetime.date.today()
    dia_str = dia.strftime("%Y-%m-%d")
    conn = _conectar_db()

    def _count_like(sql: str, params=()):
        try:
            cur = conn.execute(sql, params)
            row = cur.fetchone()
            return int(row[0] if row and row[0] is not None else 0)
        except Exception:
            return 0

    # historial_reportes: fecha_hora suele ser 'YYYY-MM-DD HH:MM:SS'
    sellos_hoy = _count_like(
        "SELECT COUNT(*) FROM historial_reportes WHERE substr(fecha_hora, 1, 10) = ?",
        (dia_str,),
    )
    # control_frio
    lecturas_hoy = _count_like(
        "SELECT COUNT(*) FROM control_frio WHERE substr(hora_registro, 1, 10) = ?",
        (dia_str,),
    )
    rupturas_hoy = _count_like(
        """
        SELECT COUNT(*) FROM control_frio
        WHERE substr(hora_registro, 1, 10) = ?
          AND upper(COALESCE(estado, '')) LIKE '%RUPTURA%'
        """,
        (dia_str,),
    )
    # Si hora_registro solo trae HH:MM:SS, contar por id reciente del día vía fallback
    if lecturas_hoy == 0:
        try:
            df_f = pd.read_sql_query(
                "SELECT hora_registro, estado FROM control_frio ORDER BY id DESC LIMIT 200",
                conn,
            )
            n_lec = 0
            n_rup = 0
            for _, r in df_f.iterrows():
                dt = _parse_fecha_hora_flexible(r.get("hora_registro"))
                if dt is None or dt.date() != dia:
                    continue
                n_lec += 1
                if "RUPTURA" in str(r.get("estado") or "").upper():
                    n_rup += 1
            lecturas_hoy = n_lec
            rupturas_hoy = n_rup
        except Exception:
            pass

    contenedores_hoy = _count_like("SELECT COUNT(*) FROM contenedores_despacho")
    # No hay fecha en contenedores: mostrar total reciente (últimos IDs del día no aplica)
    try:
        contenedores_total = _count_like("SELECT COUNT(*) FROM contenedores_despacho")
    except Exception:
        contenedores_total = 0

    cargas_packing = _count_like("SELECT COUNT(*) FROM historial_sesion")

    lotes_sellados = []
    try:
        df_s = pd.read_sql_query(
            """
            SELECT fecha_hora, lote, responsable, producto, registros
            FROM historial_reportes
            WHERE substr(fecha_hora, 1, 10) = ?
            ORDER BY id DESC
            LIMIT 15
            """,
            conn,
            params=(dia_str,),
        )
        lotes_sellados = df_s.to_dict("records") if not df_s.empty else []
    except Exception:
        lotes_sellados = []

    conn.close()

    frio = alertas_frio_activas(limite=10, horas_ventana=12)

    if frio["nivel"] == "CRITICO" or rupturas_hoy >= 3:
        estado_turno = "CRITICO"
    elif frio["nivel"] == "ALERTA" or rupturas_hoy >= 1:
        estado_turno = "VIGILANCIA"
    else:
        estado_turno = "ESTABLE"

    return {
        "ok": True,
        "fecha": dia_str,
        "estado_turno": estado_turno,
        "kpis": {
            "sellos_ecc": sellos_hoy,
            "lecturas_frio": lecturas_hoy,
            "rupturas_frio": rupturas_hoy,
            "contenedores": contenedores_total,
            "cargas_packing": cargas_packing,
        },
        "lotes_sellados": lotes_sellados,
        "alertas_frio": frio,
    }

