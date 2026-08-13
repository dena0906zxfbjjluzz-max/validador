"""Acceso de planta: secrets, roles y helpers de login."""
from __future__ import annotations

import streamlit as st

import funciones
import seguridad_cortafuego as firewall


def cargar_nombre_planta() -> str:
    """Nombre de la planta (secrets opcional; por defecto: Planta Autorizada)."""
    try:
        if "NOMBRE_PLANTA" in st.secrets:
            valor = str(st.secrets["NOMBRE_PLANTA"]).strip()
            if valor:
                return valor
    except Exception:
        pass
    try:
        creds = st.secrets.get("credenciales")
        if creds is not None and "nombre_planta" in creds:
            valor = str(creds["nombre_planta"]).strip()
            if valor:
                return valor
    except Exception:
        pass
    return "Planta Autorizada"



def cargar_credenciales_acceso() -> tuple[str | None, str | None, str | None]:
    """
    Lee el acceso de planta desde st.secrets['credenciales'].
    Retorna (usuario, clave, error_si_falla).
    """
    accesos, err = listar_accesos_planta()
    if err:
        return None, None, err
    if not accesos:
        return None, None, (
            "No se encontraron credenciales en secrets. Configure en Streamlit Cloud "
            "(Settings → Secrets) o en .streamlit/secrets.toml:\n\n"
            "[credenciales]\n"
            'usuario = "su_usuario"\n'
            'clave = "su_clave_secreta"\n'
            'rol = "supervisor"'
        )
    prim = accesos[0]
    return prim["usuario"], prim["clave"], None


def listar_accesos_planta() -> tuple[list[dict], str | None]:
    """
    Usuarios de planta con rol (operario | supervisor).
    Fuentes (en orden):
      - lista [[usuarios]] o tabla [usuarios.*]
      - [credenciales] (+ opcional [credenciales_operario])
    """
    candidatos: list[dict] = []

    def _tabla(nombre: str):
        """Lee una sección de secrets (compatible Streamlit Cloud)."""
        try:
            return st.secrets[nombre]
        except Exception:
            pass
        try:
            return st.secrets.get(nombre)
        except Exception:
            return None

    def _campo(obj, *nombres, default=None):
        if obj is None:
            return default
        for n in nombres:
            try:
                v = obj[n]
                if v is not None and str(v).strip() != "":
                    return v
            except Exception:
                pass
            try:
                v = obj.get(n)
                if v is not None and str(v).strip() != "":
                    return v
            except Exception:
                pass
        return default

    def _push(usuario, clave, rol):
        u = str(usuario or "").strip()
        c = str(clave or "")
        if not u or not c:
            return
        candidatos.append(
            {
                "usuario": u,
                "clave": c,
                "rol": firewall.normalizar_rol(rol),
            }
        )

    try:
        usuarios_sec = _tabla("usuarios")
        if usuarios_sec is not None:
            if isinstance(usuarios_sec, list):
                for item in usuarios_sec:
                    try:
                        _push(
                            _campo(item, "usuario", "user"),
                            _campo(item, "clave", "password", "pass"),
                            _campo(item, "rol", default="supervisor"),
                        )
                    except Exception:
                        pass
            else:
                try:
                    for _k in usuarios_sec:
                        item = usuarios_sec[_k]
                        try:
                            _push(
                                _campo(item, "usuario", "user", default=_k),
                                _campo(item, "clave", "password", "pass"),
                                _campo(item, "rol", default="supervisor"),
                            )
                        except Exception:
                            pass
                except Exception:
                    pass
    except Exception:
        pass

    try:
        creds = _tabla("credenciales")
        if creds is not None:
            _push(
                _campo(creds, "usuario", "user"),
                _campo(creds, "clave", "password", "pass"),
                _campo(creds, "rol", default="supervisor"),
            )
    except Exception:
        pass

    try:
        op = _tabla("credenciales_operario")
        if op is not None:
            _push(
                _campo(op, "usuario", "user"),
                _campo(op, "clave", "password", "pass"),
                _campo(op, "rol", default="operario"),
            )
    except Exception:
        pass

    # Deduplicar por usuario (primera aparición gana)
    vistos = set()
    unicos = []
    for c in candidatos:
        key = c["usuario"].lower()
        if key in vistos:
            continue
        vistos.add(key)
        unicos.append(c)

    if not unicos:
        return [], (
            "No se encontraron credenciales en **Streamlit Secrets**.\n\n"
            "En la nube: menú ⋮ de la app → **Settings** → **Secrets** → pegue:\n\n"
            "[credenciales]\n"
            'usuario = "su_usuario"\n'
            'clave = "su_clave_secreta"\n'
            'rol = "supervisor"\n\n'
            "Guarde y recargue la app. En local use `.streamlit/secrets.toml`."
        )
    return unicos, None


def purgar_frio_local_ui(solo_rupturas: bool = False) -> dict:
    """Llama a funciones.purgar_control_frio_local con recarga si Cloud quedó a medias."""
    fn = getattr(funciones, "purgar_control_frio_local", None)
    if fn is None:
        try:
            import importlib

            importlib.reload(funciones)
            fn = getattr(funciones, "purgar_control_frio_local", None)
        except Exception:
            fn = None
    if fn is None:
        return {
            "ok": False,
            "borradas": 0,
            "mensaje": (
                "Código desactualizado en Cloud. "
                "Vaya a Manage app → Reboot y vuelva a intentar."
            ),
        }
    return fn(solo_rupturas=solo_rupturas)

