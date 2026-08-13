import streamlit as st
import datetime
import io
import pandas as pd

import funciones
import motor_planta
import seguridad_cortafuego as firewall

st.set_page_config(
    page_title="Sistema Integral de Exportación",
    page_icon="📊",
    layout="wide",
)

# Cortafuego: bootstrap DB de seguridad al cargar la app
try:
    firewall.inicializar_cortafuego_db()
except Exception:
    pass


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


def pagina_ecc_style(titulo: str, descripcion: str = ""):
    """Título limpio; descripción corta opcional (máx. una línea)."""
    st.title(titulo)
    if descripcion:
        st.caption(descripcion)


if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

# Tema visual: dashboard tipo home de Supabase, paleta Cadena de Frío (agroexport)
# Acento teal frío de cámara reefer + sello oro de exportación (no verde SaaS genérico)
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,600;0,9..40,700;0,9..40,800;1,9..40,400&display=swap');

    :root {
        --sb-bg: #060A10;
        --sb-card: #0C1219;
        --sb-card-2: #111925;
        --sb-border: #1A2636;
        --sb-border-soft: #243246;
        --sb-accent: #2BB8A8;
        --sb-accent-hot: #22A396;
        --sb-accent-dim: rgba(43, 184, 168, 0.12);
        --sb-gold: #D4A84B;
        --sb-gold-dim: rgba(212, 168, 75, 0.14);
        --sb-text: #EAF0F6;
        --sb-muted: #8A9BB0;
        --sb-input: #090E15;
        --sb-green: var(--sb-accent);
        --sb-radius: 12px;
    }

    html, body, [data-testid="stAppViewContainer"] {
        font-family: "DM Sans", "Segoe UI", system-ui, sans-serif;
    }

    /* CRÍTICO: no forzar font/color en TODOS los span — rompe Material Icons
       (texto "keyboard_dou…", "uploadupload", solapes de expander) */

    /* Fondo difuminado profesional (sin malla densa) */
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"],
    section.main {
        background-color: var(--sb-bg) !important;
        background-image:
            radial-gradient(ellipse 80% 50% at 10% -10%, rgba(43, 184, 168, 0.16), transparent 55%),
            radial-gradient(ellipse 60% 45% at 95% 5%, rgba(212, 168, 75, 0.08), transparent 50%),
            radial-gradient(ellipse 70% 40% at 50% 110%, rgba(43, 184, 168, 0.06), transparent 55%);
        background-attachment: fixed;
        color: var(--sb-text);
    }

    /* Tarjetas de navegación / workspace */
    .vx-workspace-hero {
        position: relative;
        overflow: hidden;
        border-radius: 18px;
        padding: 1.6rem 1.75rem 1.45rem 1.75rem;
        margin-bottom: 1.1rem;
        border: 1px solid rgba(43, 184, 168, 0.18);
        background:
            linear-gradient(135deg, rgba(43, 184, 168, 0.12), transparent 42%),
            linear-gradient(225deg, rgba(212, 168, 75, 0.08), transparent 40%),
            rgba(12, 18, 25, 0.72);
        backdrop-filter: blur(14px);
        box-shadow: 0 20px 50px rgba(0,0,0,0.28);
    }
    .vx-workspace-hero h1 {
        margin: 0 0 0.35rem 0;
        font-size: 1.65rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        color: #EAF0F6 !important;
    }
    .vx-workspace-hero p {
        margin: 0;
        color: #8A9BB0 !important;
        font-size: 0.92rem;
        max-width: 42rem;
        line-height: 1.45;
    }
    .vx-chip-row { display:flex; flex-wrap:wrap; gap:0.45rem; margin-top:0.95rem; }
    .vx-chip {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        padding: 0.28rem 0.65rem;
        border-radius: 999px;
        border: 1px solid rgba(43,184,168,0.28);
        background: rgba(43,184,168,0.10);
        color: #2BB8A8 !important;
    }
    .vx-chip.gold {
        border-color: rgba(212,168,75,0.35);
        background: rgba(212,168,75,0.12);
        color: #D4A84B !important;
    }
    .vx-lote-bar {
        display:flex; flex-wrap:wrap; gap:0.75rem; align-items:center; justify-content:space-between;
        padding: 0.85rem 1.1rem;
        border-radius: 14px;
        margin-bottom: 1rem;
        border: 1px solid rgba(43,184,168,0.22);
        background: rgba(12,18,25,0.75);
        backdrop-filter: blur(10px);
    }
    .vx-lote-bar .name { font-weight:800; color:#EAF0F6 !important; font-size:1.05rem; }
    .vx-lote-bar .meta { color:#8A9BB0 !important; font-size:0.82rem; }
    [data-testid="stHeader"] {
        background: rgba(6, 10, 16, 0.85) !important;
        backdrop-filter: blur(8px);
    }
    [data-testid="stSidebar"],
    [data-testid="stSidebarContent"] {
        background-color: var(--sb-card) !important;
        border-right: 1px solid var(--sb-border);
        overflow-x: hidden !important;
    }
    [data-testid="stToolbar"] { background: transparent !important; }

    /* Contención de columnas: evita que widgets se salgan al card vecino */
    div[data-testid="stHorizontalBlock"] {
        gap: 0.85rem;
        align-items: flex-start;
    }
    div[data-testid="column"] {
        min-width: 0 !important;
        overflow: hidden !important;
        max-width: 100%;
    }
    section.main .block-container {
        padding-top: 1.25rem;
        max-width: 1400px;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background:
            linear-gradient(180deg, rgba(43, 184, 168, 0.04), transparent 28%),
            var(--sb-card) !important;
        border: 1px solid var(--sb-border) !important;
        border-radius: var(--sb-radius) !important;
        padding: 0.55rem 0.75rem 0.85rem 0.75rem !important;
        box-shadow: 0 1px 0 rgba(255, 255, 255, 0.03), 0 18px 48px rgba(0, 0, 0, 0.22);
        backdrop-filter: blur(8px);
        overflow: hidden !important;
        max-width: 100%;
    }

    /* Tipografía segura (sin romper íconos) */
    [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3,
    [data-testid="stMarkdownContainer"] h4,
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stWidgetLabel"] p,
    .stCaption,
    [data-testid="stCaptionContainer"] {
        color: var(--sb-text) !important;
        font-family: "DM Sans", "Segoe UI", system-ui, sans-serif !important;
    }
    .stCaption, [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p {
        color: var(--sb-muted) !important;
    }

    /* Material Icons: restaurar fuente ligature (evita "keyboard_dou" a texto) */
    [data-testid="stIconMaterial"],
    span[data-testid="stIconMaterial"],
    .material-symbols-rounded,
    .material-symbols-outlined,
    span.material-symbols-rounded,
    span.material-symbols-outlined {
        font-family: "Material Symbols Rounded", "Material Symbols Outlined", sans-serif !important;
        font-weight: normal !important;
        font-style: normal !important;
        font-size: 1.25rem !important;
        line-height: 1 !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        display: inline-block !important;
        white-space: nowrap !important;
        word-wrap: normal !important;
        overflow: hidden !important;
        width: 1.25rem !important;
        max-width: 1.25rem !important;
        height: 1.25rem !important;
        direction: ltr !important;
        -webkit-font-feature-settings: "liga" !important;
        font-feature-settings: "liga" !important;
        -webkit-font-smoothing: antialiased !important;
        color: inherit !important;
        -webkit-text-fill-color: currentColor !important;
        background: none !important;
        background-clip: unset !important;
    }

    /* Botón colapsar sidebar: no se desborda hacia el main */
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] {
        z-index: 100 !important;
        max-width: 2.5rem !important;
        overflow: hidden !important;
    }
    [data-testid="stSidebarCollapsedControl"] [data-testid="stIconMaterial"],
    [data-testid="collapsedControl"] [data-testid="stIconMaterial"] {
        width: 1.25rem !important;
        overflow: hidden !important;
    }

    div[data-baseweb="select"] > div,
    .stTextInput input,
    .stNumberInput input,
    .stTextArea textarea,
    [data-baseweb="input"] {
        background-color: var(--sb-input) !important;
        color: var(--sb-text) !important;
        border-color: var(--sb-border) !important;
        border-radius: 8px !important;
    }

    .stButton > button {
        background-color: var(--sb-card-2);
        color: var(--sb-text);
        border-radius: 8px;
        font-weight: 600;
        border: 1px solid var(--sb-border);
        padding: 0.5rem 1rem;
        font-family: "DM Sans", "Segoe UI", system-ui, sans-serif !important;
        white-space: normal;
        overflow: hidden;
    }
    .stButton > button:hover {
        background-color: #162030;
        border-color: var(--sb-border-soft);
        color: white;
    }

    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {
        background: linear-gradient(180deg, #34C9B8 0%, var(--sb-accent) 100%) !important;
        color: #04110F !important;
        border: none !important;
        font-weight: 700 !important;
        border-radius: 8px !important;
        box-shadow: 0 0 0 1px rgba(43, 184, 168, 0.25), 0 8px 20px rgba(43, 184, 168, 0.18);
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover {
        background: linear-gradient(180deg, #3FD4C3 0%, var(--sb-accent-hot) 100%) !important;
        color: #04110F !important;
    }

    /* Expand / file uploader: contener overflow y texto doble */
    [data-testid="stExpander"] {
        overflow: hidden !important;
        border-radius: 10px !important;
        border: 1px solid var(--sb-border) !important;
        background: var(--sb-input) !important;
    }
    [data-testid="stExpander"] details,
    [data-testid="stExpander"] summary {
        overflow: hidden !important;
        max-width: 100% !important;
    }
    [data-testid="stExpander"] summary {
        white-space: normal !important;
        word-break: break-word !important;
    }
    [data-testid="stFileUploader"] {
        background: var(--sb-input) !important;
        border: 1px dashed var(--sb-border-soft) !important;
        border-radius: 12px !important;
        padding: 0.65rem !important;
        overflow: hidden !important;
        max-width: 100% !important;
    }
    [data-testid="stFileUploader"] section,
    [data-testid="stFileUploaderDropzone"] {
        overflow: hidden !important;
        max-width: 100% !important;
    }
    [data-testid="stFileUploader"] button {
        overflow: hidden !important;
        max-width: 100% !important;
    }
    [data-testid="stCameraInput"] {
        overflow: hidden !important;
        max-width: 100% !important;
        border-radius: 10px;
    }
    [data-testid="stCameraInput"] img,
    [data-testid="stCameraInput"] video {
        max-width: 100% !important;
        height: auto !important;
        border-radius: 8px;
    }

    .sb-card-title {
        font-size: 0.7rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--sb-muted) !important;
        font-weight: 700;
        margin: 0 0 0.3rem 0;
    }
    .sb-card-heading {
        font-size: 1.08rem;
        font-weight: 700;
        color: var(--sb-text) !important;
        margin: 0 0 0.75rem 0;
        line-height: 1.3;
        word-break: break-word;
    }
    .sb-pill {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 6px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        border: 1px solid var(--sb-border);
        background: var(--sb-input);
        color: var(--sb-muted) !important;
        margin: 0 0.3rem 0.55rem 0;
    }
    .sb-pill.ok {
        color: #04110F !important;
        background: var(--sb-accent);
        border-color: transparent;
    }
    .sb-pill.gold {
        color: #1A1406 !important;
        background: var(--sb-gold);
        border-color: transparent;
    }
    .sb-pill.warn {
        color: #F5D07A !important;
        border-color: #3A3118;
        background: #151208;
    }
    .sb-status-row {
        display: grid;
        grid-template-columns: minmax(0, 42%) minmax(0, 58%);
        gap: 0.35rem 0.65rem;
        padding: 0.5rem 0;
        border-bottom: 1px solid var(--sb-border);
        font-size: 0.82rem;
        align-items: start;
    }
    .sb-status-row span:first-child {
        color: var(--sb-muted) !important;
        font-weight: 600;
    }
    .sb-status-row span:last-child {
        color: var(--sb-text) !important;
        font-weight: 600;
        text-align: right;
        overflow-wrap: anywhere;
        word-break: break-word;
        min-width: 0;
    }

    /* ── Hero ── */
    .sb-hero-bar {
        position: relative;
        margin-bottom: 1.25rem;
        padding: 1.5rem 1.6rem 1.4rem 1.6rem;
        background:
            radial-gradient(ellipse 70% 120% at 0% 0%, rgba(43, 184, 168, 0.14), transparent 55%),
            radial-gradient(ellipse 50% 80% at 100% 100%, rgba(212, 168, 75, 0.08), transparent 50%),
            var(--sb-card);
        border: 1px solid var(--sb-border);
        border-radius: 14px;
        box-shadow: 0 16px 48px rgba(0, 0, 0, 0.4);
        overflow: hidden;
    }
    .sb-hero-bar::before {
        content: "";
        position: absolute;
        inset: 0;
        background-image:
            linear-gradient(rgba(43, 184, 168, 0.04) 1px, transparent 1px),
            linear-gradient(90deg, rgba(43, 184, 168, 0.04) 1px, transparent 1px);
        background-size: 32px 32px;
        pointer-events: none;
        mask-image: linear-gradient(180deg, #000 0%, transparent 85%);
    }
    .sb-hero-top-row {
        position: relative;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 0.65rem 1rem;
        margin-bottom: 0.85rem;
    }
    .sb-hero-crumbs {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.4rem 0.5rem;
        font-size: 0.78rem;
        color: var(--sb-muted) !important;
        font-weight: 600;
        letter-spacing: 0.02em;
        min-width: 0;
        flex: 1 1 auto;
    }
    .sb-hero-crumbs .dot { opacity: 0.45; color: var(--sb-muted) !important; }
    .sb-hero-crumbs .crumb {
        color: var(--sb-muted) !important;
        max-width: 14rem;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .sb-hero-date {
        flex: 0 0 auto;
        font-size: 0.78rem;
        font-weight: 700;
        color: var(--sb-gold) !important;
        background: var(--sb-gold-dim);
        border: 1px solid rgba(212, 168, 75, 0.35);
        border-radius: 6px;
        padding: 0.25rem 0.55rem;
        white-space: nowrap;
    }
    .sb-tag-prod {
        display: inline-flex;
        align-items: center;
        padding: 0.12rem 0.45rem;
        border-radius: 4px;
        font-size: 0.65rem;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        background: var(--sb-gold-dim);
        color: var(--sb-gold) !important;
        border: 1px solid rgba(212, 168, 75, 0.35);
        white-space: nowrap;
    }
    .sb-hero-top {
        position: relative;
        display: flex;
        flex-wrap: wrap;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1rem 1.5rem;
    }
    .sb-hero-bar h1 {
        font-size: clamp(1.85rem, 3.8vw, 2.75rem) !important;
        margin: 0 0 0.4rem 0 !important;
        font-weight: 800 !important;
        letter-spacing: -0.04em !important;
        line-height: 1.08 !important;
        background: linear-gradient(105deg, #FFFFFF 0%, #EAF0F6 40%, #2BB8A8 78%, #D4A84B 118%);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        color: transparent !important;
        max-width: 100%;
        word-break: break-word;
    }
    .sb-hero-meta {
        position: relative;
        color: var(--sb-muted) !important;
        font-size: 0.92rem;
        max-width: 40rem;
        line-height: 1.45;
    }
    .sb-hero-badge {
        position: relative;
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        padding: 0.55rem 1rem;
        border-radius: 8px;
        border: 1px solid rgba(43, 184, 168, 0.35);
        background: var(--sb-accent-dim);
        color: var(--sb-accent) !important;
        font-size: 0.84rem;
        font-weight: 700;
        white-space: nowrap;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .sb-status-grid {
        position: relative;
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(118px, 1fr));
        gap: 0.5rem;
        margin-top: 1.1rem;
    }
    .sb-mini-card {
        background: var(--sb-input);
        border: 1px solid var(--sb-border);
        border-radius: 10px;
        padding: 0.6rem 0.7rem;
        min-height: 4rem;
        min-width: 0;
        overflow: hidden;
    }
    .sb-mini-card .k {
        font-size: 0.62rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--sb-muted) !important;
        font-weight: 700;
        margin-bottom: 0.3rem;
    }
    .sb-mini-card .v {
        font-size: 0.88rem;
        font-weight: 700;
        color: var(--sb-text) !important;
        display: flex;
        align-items: center;
        gap: 0.35rem;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .sb-mini-card .v.ok { color: var(--sb-accent) !important; }
    .sb-mini-card .v.gold { color: var(--sb-gold) !important; }
    .sb-dot {
        width: 0.45rem; height: 0.45rem; border-radius: 50%;
        background: var(--sb-accent);
        box-shadow: 0 0 0 3px rgba(43, 184, 168, 0.2);
        display: inline-block;
        flex-shrink: 0;
    }

    .sb-ops-banner {
        margin: 0.85rem 0 1rem 0;
        padding: 1.1rem 1.25rem;
        border-radius: 12px;
        border: 1px solid var(--sb-border);
        background:
            radial-gradient(ellipse 60% 100% at 0% 50%, rgba(43, 184, 168, 0.1), transparent 60%),
            var(--sb-card);
        overflow: hidden;
    }
    [data-testid="stMarkdownContainer"] h3 {
        font-size: 1.12rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.01em;
        margin: 0.35rem 0 0.85rem 0 !important;
        padding: 0.55rem 0.75rem 0.55rem 0.9rem !important;
        border-left: 3px solid var(--sb-accent) !important;
        border-radius: 0 10px 10px 0;
        background: linear-gradient(90deg, var(--sb-accent-dim), transparent 72%);
        color: var(--sb-text) !important;
        word-break: break-word;
    }
    hr {
        border: none !important;
        border-top: 1px solid var(--sb-border) !important;
        margin: 1.25rem 0 !important;
    }

    /* Navegación lateral — sin span globales */
    [data-testid="stSidebar"] > div:first-child {
        background-color: var(--sb-card) !important;
        padding-top: 1rem;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
        color: var(--sb-text) !important;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: var(--sb-muted) !important;
    }
    .sb-nav-label {
        font-size: 0.7rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--sb-muted) !important;
        font-weight: 700;
        margin: 0 0 0.25rem 0;
    }
    .sb-nav-title {
        font-size: 1.08rem !important;
        font-weight: 700 !important;
        color: var(--sb-text) !important;
        margin: 0 0 0.85rem 0 !important;
    }

    .stRadio label,
    [data-testid="stSidebar"] .stRadio label,
    div[data-baseweb="radio"] {
        color: var(--sb-text) !important;
    }
    div[data-baseweb="radio"] > div:first-child {
        background-color: transparent !important;
        border-color: var(--sb-border) !important;
    }
    div[data-baseweb="radio"] input:checked + div,
    div[role="radiogroup"] label[data-baseweb="radio"] > div:first-child {
        background-color: var(--sb-accent) !important;
        border-color: var(--sb-accent) !important;
    }
    div[data-baseweb="radio"] svg {
        fill: #04110F !important;
        color: #04110F !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label {
        background-color: var(--sb-input) !important;
        border: 1px solid var(--sb-border) !important;
        border-radius: 10px !important;
        padding: 0.55rem 0.7rem !important;
        margin-bottom: 0.45rem !important;
        transition: border-color 0.15s ease, background 0.15s ease;
        overflow: hidden !important;
        max-width: 100% !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        border-color: var(--sb-border-soft) !important;
        background-color: #0F1722 !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
        border-color: var(--sb-accent) !important;
        background-color: var(--sb-accent-dim) !important;
        box-shadow: 0 0 0 1px rgba(43, 184, 168, 0.22);
    }

    *:focus-visible { outline-color: var(--sb-accent) !important; }
    [data-baseweb="radio"] input:focus + div {
        box-shadow: 0 0 0 2px rgba(43, 184, 168, 0.4) !important;
        border-color: var(--sb-accent) !important;
    }

    [data-testid="stMetricValue"] {
        color: var(--sb-text) !important;
        font-weight: 700 !important;
    }
    /* Alertas no invaden columnas */
    [data-testid="stAlert"] {
        overflow: hidden !important;
        max-width: 100% !important;
        word-break: break-word !important;
    }

    /* Bitácora cortafuego: filas contenidas (sin code-badge de Streamlit) */
    .fw-event-row {
        border: 1px solid var(--sb-border);
        border-radius: 8px;
        background: var(--sb-input);
        padding: 0.55rem 0.7rem;
        margin: 0.45rem 0;
        max-width: 100%;
        overflow: hidden;
        box-sizing: border-box;
    }
    .fw-event-time {
        font-size: 0.72rem;
        font-weight: 700;
        color: var(--sb-accent) !important;
        letter-spacing: 0.02em;
        margin-bottom: 0.25rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .fw-event-main {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.4rem 0.55rem;
        margin-bottom: 0.15rem;
    }
    .fw-event-name {
        font-size: 0.82rem;
        font-weight: 800;
        color: var(--sb-text) !important;
        letter-spacing: 0.04em;
    }
    .fw-event-sev {
        font-size: 0.68rem;
        font-weight: 700;
        text-transform: uppercase;
        color: var(--sb-muted) !important;
        border: 1px solid var(--sb-border);
        border-radius: 4px;
        padding: 0.08rem 0.35rem;
    }
    .fw-event-det {
        font-size: 0.78rem;
        color: var(--sb-muted) !important;
        word-break: break-word;
        line-height: 1.35;
    }
    .sb-side-nav-hint {
        font-size: 0.7rem;
        color: var(--sb-muted) !important;
        margin: 0 0 0.5rem 0;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.sidebar.markdown(
    """
    <p class="sb-nav-label">Workspace</p>
    <p class="sb-nav-title">Navegación</p>
    """,
    unsafe_allow_html=True,
)
modo_app = st.sidebar.radio(
    "Seleccione el módulo:",
    ["Planta / Packing (login)", "Verificación pública ECC"],
    index=0,
    key="nav_modo_app",
)

# Cortafuego: cerrar sesión (solo si autenticado)
if st.session_state.get("autenticado"):
    st.sidebar.markdown("---")
    st.sidebar.caption("🛡️ Cortafuego de planta")
    _fw_user = st.session_state.get("fw_usuario") or "inspector"
    _fw_rol = st.session_state.get("rol_planta") or "supervisor"
    st.sidebar.caption(f"Sesión: `{_fw_user}` · {_fw_rol}")
    if st.sidebar.button("Cerrar sesión segura", key="btn_fw_logout"):
        firewall.cerrar_sesion(st.session_state, "logout_manual")
        st.session_state["rol_planta"] = None
        st.rerun()

# ---------- MÓDULO PÚBLICO: verificación de PDF firmado (sin login) ----------
if modo_app == "Verificación pública ECC":
    st.title("Verificación pública de sello ECC")
    st.write(
        "Suba el PDF ejecutivo firmado para comprobar matemáticamente si la firma "
        "Ed25519 es auténtica o si el documento fue alterado."
    )

    pdf_verif = st.file_uploader(
        "PDF ejecutivo firmado",
        type=["pdf"],
        key="uploader_verificacion_ecc",
    )

    with st.expander("Verificación manual (si el PDF no se puede leer)"):
        mensaje_manual = st.text_input("Mensaje firmado", key="msg_manual_ecc")
        firma_manual = st.text_area("Firma hex Ed25519 (128 caracteres)", key="firma_manual_ecc")
        pub_manual = st.text_area("Llave pública hex Ed25519 (64 caracteres)", key="pub_manual_ecc")
        usar_manual = st.checkbox("Usar datos manuales en lugar del PDF", key="usar_manual_ecc")

    if st.button("Verificar autenticidad ECC", type="primary"):
        try:
            if usar_manual:
                datos = {
                    "mensaje": mensaje_manual,
                    "firma": firma_manual,
                    "llave_publica": pub_manual,
                }
            elif pdf_verif is not None:
                datos = funciones.extraer_sello_ecc_pdf(pdf_verif.getvalue())
            else:
                st.error("Suba un PDF o active la verificación manual.")
                st.stop()

            resultado = motor_planta.auditar_sello_pdf(datos)

            st.markdown("#### Resultado de la auditoría criptográfica")
            if resultado["ok"] and resultado["estado"] == "AUTENTICO":
                st.success(resultado["detalle"])
            elif resultado["ok"]:
                st.warning(resultado["detalle"])
            else:
                st.error(resultado["detalle"])

            st.caption(f"Estado: `{resultado['estado']}`")
            st.code(f"Mensaje: {resultado['mensaje']}")
            st.code(f"Firma: {resultado['firma']}")
            st.code(f"Llave pública: {resultado['llave_publica']}")

            oficial = motor_planta.llave_publica_oficial_hex()
            if oficial:
                st.caption(f"Llave pública oficial de planta (derivada de secrets): `{oficial}`")

            # Cruce con registro histórico permanente (si el sello ya fue archivado)
            try:
                hash_pdf = funciones.calcular_hash_reporte(
                    resultado["mensaje"], resultado["firma"], resultado["llave_publica"]
                )
                st.caption(f"Hash del sello (SHA-256): `{hash_pdf}`")
                hist = funciones.buscar_reporte_por_hash(hash_pdf)
                if hist:
                    st.success(
                        f"Registro histórico encontrado · Fecha: {hist['fecha_hora']} · "
                        f"Lote: {hist['lote']} · Responsable: {hist['responsable']}"
                    )
                else:
                    st.info(
                        "No hay entrada en el historial SQLite para este hash "
                        "(puede ser un PDF anterior al registro histórico, o se generó en otra instancia)."
                    )
            except Exception:
                pass
        except Exception as e:
            st.error(f"No se pudo verificar el PDF: {e}")

    st.markdown("---")
    st.subheader("Consulta de historial por hash")
    hash_busqueda = st.text_input("Pegue el hash SHA-256 del reporte", key="hash_hist_public")
    if st.button("Buscar en historial", key="btn_hash_hist_public"):
        if not hash_busqueda.strip():
            st.warning("Ingrese un hash.")
        else:
            hist = funciones.buscar_reporte_por_hash(hash_busqueda.strip())
            if hist:
                st.success("Registro encontrado en historial permanente")
                st.json({
                    "fecha": hist["fecha_hora"],
                    "lote": hist["lote"],
                    "hash": hist["hash_sha256"],
                    "responsable": hist["responsable"],
                    "archivo": hist["archivo"],
                    "producto": hist["producto"],
                })
            else:
                st.error("Hash no encontrado en el historial de reportes.")

    st.stop()

# ---------- ACCESO PLANTA ----------
if not st.session_state["autenticado"]:
    st.title("Acceso restringido - Control de Calidad")
    st.caption("Credenciales de planta. Para PDF use Verificación pública ECC.")

    accesos_planta, error_creds = listar_accesos_planta()
    if error_creds:
        st.error(error_creds)
        st.stop()

    # Estado del cortafuego (bloqueo por fuerza bruta)
    _bloq, _segs_bloq = firewall.estado_bloqueo(st.session_state)
    if _bloq:
        st.error(
            f"🔒 Cortafuego activo: demasiados intentos fallidos. "
            f"Espere {_segs_bloq // 60}m {_segs_bloq % 60}s."
        )
        st.caption("Los intentos se registran en la bitácora de seguridad local.")
        st.stop()

    usuarioInput = st.text_input("Usuario:", key="login_usuario")
    passwordInput = st.text_input("Contraseña:", type="password", key="login_clave")

    if st.button("Ingresar", type="primary", key="btn_login_planta"):
        resultado_login = firewall.intentar_login_lista(
            st.session_state,
            usuario_in=usuarioInput,
            clave_in=passwordInput,
            candidatos=accesos_planta,
        )
        if resultado_login.get("ok"):
            st.session_state["rol_planta"] = resultado_login.get("rol") or "supervisor"
            st.success(resultado_login.get("mensaje") or "Acceso concedido.")
            st.rerun()
        else:
            st.error(resultado_login.get("mensaje") or "Credenciales incorrectas.")
            if resultado_login.get("bloqueado"):
                st.rerun()
    st.caption(f"Cortafuego · máx. {firewall.politica()['max_intentos']} intentos")
    st.stop()

# Rol de sesión (compat: sesiones previas sin rol → supervisor)
if "rol_planta" not in st.session_state or not st.session_state.get("rol_planta"):
    st.session_state["rol_planta"] = "supervisor"
_es_supervisor = firewall.es_supervisor(st.session_state)
_rol_label = st.session_state.get("rol_planta") or "supervisor"

# Sesión autenticada: validar token + timeout en cada rerun
_sesion_ok, _motivo_sesion = firewall.sesion_valida(st.session_state)
if not _sesion_ok:
    st.warning(
        "Sesión cerrada por el cortafuego"
        + (f" ({_motivo_sesion})." if _motivo_sesion not in ("no_auth",) else ".")
        + " Vuelva a iniciar sesión."
    )
    st.session_state["autenticado"] = False
    st.stop()

nombre_planta = cargar_nombre_planta()
_plant_label = nombre_planta or "Planta Autorizada"
_fecha_hoy = datetime.date.today().strftime("%d/%m/%Y")
# El encabezado se dibuja después de resolver la pantalla activa (sidebar).

funciones.inicializar_base_datos()

if "lote_congelado" not in st.session_state:
    st.session_state["lote_congelado"] = False

if "mostrar_vacios" not in st.session_state:
    st.session_state["mostrar_vacios"] = False

# Navegación por pantallas (no lista infinita de módulos)
if "vista_planta" not in st.session_state:
    st.session_state["vista_planta"] = "inicio"
if "modulo_nav" not in st.session_state:
    st.session_state["modulo_nav"] = "Resumen del lote"

# Cámara QR apagada por defecto
if "camara_qr_activa" not in st.session_state:
    st.session_state["camara_qr_activa"] = False
if "camera_qr_token" not in st.session_state:
    st.session_state["camera_qr_token"] = 0
if "camara_cnt_activa" not in st.session_state:
    st.session_state["camara_cnt_activa"] = False
if "camera_cnt_token" not in st.session_state:
    st.session_state["camera_cnt_token"] = 0
for _ck in (
    "cnt_form_booking",
    "cnt_form_contenedor",
    "cnt_form_plinea",
    "cnt_form_psenasa",
):
    if _ck not in st.session_state:
        st.session_state[_ck] = ""


def _apagar_camara_qr():
    """Desmonta st.camera_input y libera el lente del dispositivo."""
    st.session_state["camara_qr_activa"] = False
    st.session_state["camera_qr_token"] = int(st.session_state.get("camera_qr_token") or 0) + 1
    for k in list(st.session_state.keys()):
        if str(k).startswith("camera_escaneo_qr_"):
            try:
                del st.session_state[k]
            except Exception:
                pass


def _apagar_camara_cnt():
    """Apaga cámara del módulo de contenedores."""
    st.session_state["camara_cnt_activa"] = False
    st.session_state["camera_cnt_token"] = int(st.session_state.get("camera_cnt_token") or 0) + 1
    for k in list(st.session_state.keys()):
        if str(k).startswith("camera_escaneo_cnt_"):
            try:
                del st.session_state[k]
            except Exception:
                pass


def _cnt_aplicar_prefill(pl=None, reg=None):
    """Rellena los campos del formulario M5 (widgets key=) desde QR o registro."""
    pl = pl or {}
    reg = reg or {}

    def _pick(*keys):
        for src in (reg, pl):
            for k in keys:
                v = src.get(k) if isinstance(src, dict) else None
                if v is not None and str(v).strip():
                    return str(v).strip()
        return ""

    booking = _pick("booking", "Booking")
    contenedor = _pick("contenedor", "Contenedor", "container")
    plinea = _pick("precinto_linea", "Precinto Línea", "precinto linea")
    psenasa = _pick("precinto_senasa", "Precinto SENASA", "precinto senasa")
    if booking:
        st.session_state["cnt_form_booking"] = booking
    if contenedor:
        st.session_state["cnt_form_contenedor"] = contenedor
    if plinea:
        st.session_state["cnt_form_plinea"] = plinea
    if psenasa:
        st.session_state["cnt_form_psenasa"] = psenasa


def render_modulo_alertas_tendencias(
    df_packing=None,
    cols_mapa=None,
    peso_min_caja: float = 4.0,
    max_merma_permitida: float = 5.0,
    key_prefix: str = "m7",
):
    """Módulo 7 — Alertas y tendencias (frío SQLite + packing cargado)."""
    with st.container():
        informe = funciones.consolidar_inteligencia_planta(
            df_packing=df_packing,
            cols_mapa=cols_mapa,
            peso_min_caja=peso_min_caja,
            max_merma_permitida=max_merma_permitida,
        )
        cont = informe.get("contadores") or {}
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Críticas", cont.get("criticas", 0))
        with c2:
            st.metric("Advertencias", cont.get("advertencias", 0))
        with c3:
            frio = informe.get("frio") or {}
            st.metric("Lecturas frío", frio.get("total_lecturas", 0))
        with c4:
            st.metric("% ruptura frío", f"{frio.get('pct_ruptura', 0)}%")

        veredicto = informe.get("veredicto")
        if veredicto == "ACCION_REQUERIDA":
            st.error(veredicto)
        elif veredicto == "VIGILANCIA":
            st.warning(veredicto)
        else:
            st.success(veredicto)

        alertas = [a for a in (informe.get("alertas") or []) if a.get("severidad") != "info"]
        if alertas:
            with st.expander(f"Alertas ({len(alertas)})", expanded=False):
                for a in alertas[:12]:
                    st.write(f"{a.get('titulo')} — {a.get('detalle')}")

        por_cam = (informe.get("frio") or {}).get("por_camara") or []
        packing = informe.get("packing") or {}
        with st.expander("Detalle frío / packing", expanded=False):
            if por_cam:
                st.dataframe(pd.DataFrame(por_cam), width="stretch", hide_index=True)
            prod = packing.get("por_productor") or []
            if prod:
                st.dataframe(pd.DataFrame(prod), width="stretch", hide_index=True)
            serie = (informe.get("frio") or {}).get("serie_chart")
            if isinstance(serie, pd.DataFrame) and not serie.empty and "camara" in serie.columns:
                cams = sorted(serie["camara"].astype(str).unique().tolist())
                cam_sel = st.selectbox("Cámara", options=cams, key=f"{key_prefix}_cam_chart")
                sub = serie[serie["camara"].astype(str) == str(cam_sel)]
                if not sub.empty and "etiqueta" in sub.columns:
                    st.line_chart(sub.set_index("etiqueta")[["temperatura"]])



# ─── Navegación por botones (solo vista_planta / modulo_nav en session_state) ─
st.sidebar.markdown("---")
st.sidebar.caption("Navegación")

_tiene_lote = st.session_state.get("df_trabajo") is not None
_MODULOS_OP = [
    "Resumen del lote",
    "1 · Balanza / SSCC",
    "2 · LMR / SENASA",
    "3 · Trazabilidad",
    "4 · Cadena de frío",
    "7 · Alertas y tendencias",
    "Limpieza y cierre",
]
_MODULOS_BTNS = [
    ("Resumen", "Resumen del lote", "nav_mod_resumen"),
    ("Balanza", "1 · Balanza / SSCC", "nav_mod_balanza"),
    ("LMR", "2 · LMR / SENASA", "nav_mod_lmr"),
    ("Trazabilidad", "3 · Trazabilidad", "nav_mod_traz"),
    ("Frío", "4 · Cadena de frío", "nav_mod_frio"),
    ("Alertas lote", "7 · Alertas y tendencias", "nav_mod_alertas_lote"),
    ("Cierre", "Limpieza y cierre", "nav_mod_cierre"),
]

if st.session_state.get("vista_planta") == "operacion" and not _tiene_lote:
    st.session_state["vista_planta"] = "inicio"
if st.session_state.get("modulo_nav") not in _MODULOS_OP:
    st.session_state["modulo_nav"] = "Resumen del lote"

_nav_vistas = [
    ("Inicio", "inicio", "nav_btn_inicio"),
    ("Dashboard", "dashboard", "nav_btn_dashboard"),
]
if _tiene_lote:
    _nav_vistas.append(("Operación del lote", "operacion", "nav_btn_operacion"))
_nav_vistas.extend(
    [
        ("QR pallet", "qr", "nav_btn_qr"),
        ("Contenedores", "contenedores", "nav_btn_cnt"),
        ("Alertas", "alertas", "nav_btn_alertas"),
    ]
)

for _lab, _vid, _key in _nav_vistas:
    _active = st.session_state.get("vista_planta") == _vid
    if st.sidebar.button(
        _lab,
        key=_key,
        type="primary" if _active else "secondary",
        use_container_width=True,
    ):
        st.session_state["vista_planta"] = _vid
        if _vid == "operacion":
            st.session_state["modulo_nav"] = st.session_state.get("modulo_nav") or "Resumen del lote"
        st.rerun()

vista = st.session_state.get("vista_planta", "inicio")

if vista == "operacion":
    st.sidebar.caption("Módulo")
    for _lab, _mod, _key in _MODULOS_BTNS:
        _active = st.session_state.get("modulo_nav") == _mod
        if st.sidebar.button(
            _lab,
            key=_key,
            type="primary" if _active else "secondary",
            use_container_width=True,
        ):
            st.session_state["modulo_nav"] = _mod
            st.rerun()
    if st.sidebar.button("Volver al inicio", key="btn_volver_inicio", use_container_width=True):
        st.session_state["vista_planta"] = "inicio"
        st.rerun()

with st.sidebar.expander("Parámetros de planta", expanded=(vista == "inicio")):
    auditor_nombre = st.text_input("Inspector asignado:", value="Control de Calidad", key="dash_inspector")
    producto_sel = st.selectbox(
        "Cultivo / fruta:",
        ["Palta Hass", "Arándano", "Espárrago", "Uva Red Globe", "Personalizado"],
        key="dash_producto",
    )
    mercado_destino = st.selectbox(
        "Mercado de destino:",
        ["Europa (GlobalGAP/UE)", "Estados Unidos (FDA/USDA)", "Asia / China", "Chile / Local"],
        key="dash_mercado",
    )
    if producto_sel == "Palta Hass":
        limit_temp_default = 5.0
        limit_brix_default = 21.0
    elif producto_sel == "Arándano":
        limit_temp_default = 0.0
        limit_brix_default = 11.5
    elif producto_sel == "Espárrago":
        limit_temp_default = 3.0
        limit_brix_default = 8.0
    elif producto_sel == "Uva Red Globe":
        limit_temp_default = -0.5
        limit_brix_default = 16.0
    else:
        limit_temp_default = 4.0
        limit_brix_default = 10.0
    _tmin_fruta, _tmax_fruta = funciones.obtener_rango_frio_fruta(producto_sel)
    if producto_sel == "Personalizado":
        temp_min_limite = st.number_input(
            "Temp. mínima cámara (°C):", value=limit_temp_default, step=0.5, key="dash_tmin"
        )
        temp_max_limite = st.number_input(
            "Temp. máxima cámara (°C):", value=limit_temp_default + 2.0, step=0.5, key="dash_tmax"
        )
    else:
        temp_min_limite = _tmin_fruta
        temp_max_limite = _tmax_fruta
        st.caption(f"Cadena de frío: **{temp_min_limite} °C** a **{temp_max_limite} °C**")
    brix_min_limite = st.number_input(
        "Materia seca / Brix mínimo:", value=limit_brix_default, step=0.5, key="dash_brix"
    )
    st.caption("Tolerancias logísticas")
    peso_min_caja = st.number_input(
        "Peso mínimo neto caja (kg):", value=4.0, step=0.1, key="dash_peso"
    )
    max_merma_permitida = st.number_input(
        "Límite máximo de merma (%):", value=5.0, step=0.5, key="dash_merma"
    )

st.sidebar.markdown("---")
st.sidebar.caption("Cargar lote")
archivo = st.sidebar.file_uploader(
    "Excel / CSV de packing",
    type=["xlsx", "csv"],
    key="uploader_recepcion_empaque",
)

if archivo is not None:
    try:
        _bytes_arch = archivo.getvalue()
        _ok_up, _msg_up = firewall.validar_upload_bytes(archivo.name, _bytes_arch)
        if not _ok_up:
            st.error(f"🛡️ Cortafuego bloqueó el archivo: {_msg_up}")
            firewall.registrar_evento(
                "UPLOAD_BLOCK",
                f"{archivo.name}: {_msg_up}",
                severidad="warn",
                usuario=st.session_state.get("fw_usuario") or "",
            )
        else:
            archivo_key = f"{archivo.name}_{archivo.size}"
            if st.session_state.get("archivo_activo") != archivo_key:
                st.session_state["archivo_activo"] = archivo_key
                st.session_state["df_trabajo"] = funciones.cargar_datos_archivo(archivo)
                st.session_state["lote_congelado"] = False
                st.session_state["nombre_archivo"] = archivo.name
                st.session_state["mapeo_columnas_manual"] = {}
                for _c in funciones.CAMPOS_MAPEO_UI:
                    st.session_state.pop(f"map_col_{_c}", None)
                st.session_state["vista_planta"] = "operacion"
                st.session_state["modulo_nav"] = "Resumen del lote"
                firewall.registrar_evento(
                    "UPLOAD_OK",
                    f"Archivo {archivo.name} ({archivo.size} bytes)",
                    severidad="info",
                    usuario=st.session_state.get("fw_usuario") or "",
                )
                st.rerun()
            st.session_state["nombre_archivo"] = archivo.name
    except Exception as _e_up:
        st.error(f"No se pudo leer el archivo: {_e_up}")

vista = st.session_state.get("vista_planta", "inicio")
modulo_nav = st.session_state.get("modulo_nav", "Resumen del lote")


# ─── Pantalla Inicio ──────────────────────────────────────────────────────────
if vista == "inicio":
    pagina_ecc_style(_plant_label, "Cargue el packing en la barra lateral.")

    _af_home = funciones.alertas_frio_activas(limite=5, horas_ventana=12)
    if _af_home.get("nivel") == "CRITICO":
        st.error(_af_home.get("mensaje"))
        if st.button("Ver dashboard de turno", key="btn_home_dash_crit"):
            st.session_state["vista_planta"] = "dashboard"
            st.rerun()
    elif _af_home.get("nivel") == "ALERTA":
        st.warning(_af_home.get("mensaje"))
        if st.button("Ver dashboard de turno", key="btn_home_dash_alerta"):
            st.session_state["vista_planta"] = "dashboard"
            st.rerun()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Dashboard de turno", type="primary", key="tile_dash", use_container_width=True):
            st.session_state["vista_planta"] = "dashboard"
            st.rerun()
        if st.button("QR pallet", key="tile_qr", use_container_width=True):
            st.session_state["vista_planta"] = "qr"
            st.rerun()
        if st.button("Contenedores", key="tile_cnt", use_container_width=True):
            st.session_state["vista_planta"] = "contenedores"
            st.rerun()
    with c2:
        if st.button("Alertas", key="tile_alertas", use_container_width=True):
            st.session_state["vista_planta"] = "alertas"
            st.rerun()
        if st.session_state.get("df_trabajo") is not None:
            if st.button("Operación del lote", type="primary", key="btn_ir_operacion", use_container_width=True):
                st.session_state["vista_planta"] = "operacion"
                st.session_state["modulo_nav"] = "Resumen del lote"
                st.rerun()

    if st.session_state.get("df_trabajo") is not None:
        st.success(f"Lote activo: **{st.session_state.get('nombre_archivo', 'archivo')}**")

# ─── Dashboard de turno + alertas de frío ─────────────────────────────────────
if vista == "dashboard":
    dash = funciones.resumen_dashboard_turno()
    pagina_ecc_style("Dashboard de turno", f"Resumen del {dash.get('fecha')} · frío y sellos ECC")

    estado = dash.get("estado_turno")
    if estado == "CRITICO":
        st.error(f"Estado del turno: {estado}")
    elif estado == "VIGILANCIA":
        st.warning(f"Estado del turno: {estado}")
    else:
        st.success(f"Estado del turno: {estado}")

    k = dash.get("kpis") or {}
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Sellos ECC hoy", k.get("sellos_ecc", 0))
    m2.metric("Lecturas frío hoy", k.get("lecturas_frio", 0))
    m3.metric("Rupturas frío hoy", k.get("rupturas_frio", 0))
    m4.metric("Contenedores", k.get("contenedores", 0))
    m5.metric("Cargas packing", k.get("cargas_packing", 0))

    st.markdown("---")
    st.subheader("Alertas de frío activas")
    af = dash.get("alertas_frio") or {}
    st.caption(af.get("mensaje") or "")
    activas = af.get("activas") or []
    if activas:
        st.dataframe(pd.DataFrame(activas), width="stretch", hide_index=True)
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Ir a cadena de frío", key="dash_ir_frio", use_container_width=True):
                if st.session_state.get("df_trabajo") is not None:
                    st.session_state["vista_planta"] = "operacion"
                    st.session_state["modulo_nav"] = "4 · Cadena de frío"
                else:
                    st.session_state["vista_planta"] = "alertas"
                st.rerun()
        with b2:
            if st.button("Ver tendencias", key="dash_ir_alertas", use_container_width=True):
                st.session_state["vista_planta"] = "alertas"
                st.rerun()
    else:
        st.info("Sin rupturas recientes en la ventana de alerta.")

    if _es_supervisor:
        with st.expander("Borrar alertas de frío (SQLite local)"):
            st.caption(
                "Las alertas se leen de la base local de la app, no solo de Supabase. "
                "Si borró en Supabase y siguen apareciendo, limpie aquí."
            )
            c_del1, c_del2 = st.columns(2)
            with c_del1:
                if st.button("Borrar solo rupturas", key="dash_del_rupturas"):
                    r = purgar_frio_local_ui(solo_rupturas=True)
                    (st.success if r.get("ok") else st.error)(r.get("mensaje"))
                    if r.get("ok"):
                        st.rerun()
            with c_del2:
                if st.button("Borrar todas las lecturas de frío", key="dash_del_frio_all"):
                    r = purgar_frio_local_ui(solo_rupturas=False)
                    (st.success if r.get("ok") else st.error)(r.get("mensaje"))
                    if r.get("ok"):
                        st.rerun()

    cfg_av = funciones._config_avisos()
    st.caption(
        "Avisos: "
        + (
            "email "
            + ("✓" if cfg_av.get("email_ok") else "—")
            + " · WhatsApp "
            + ("✓" if cfg_av.get("whatsapp_ok") else "—")
        )
    )
    if activas and cfg_av.get("habilitado"):
        if _es_supervisor:
            if st.button("Reenviar aviso de la última ruptura", key="dash_reenviar_aviso"):
                ult = activas[0]
                r = funciones.notificar_ruptura_frio(
                    {
                        "camara": ult.get("camara"),
                        "temperatura": ult.get("temperatura"),
                        "temp_min": "?",
                        "temp_max": "?",
                        "producto": ult.get("producto"),
                        "inspector": ult.get("inspector"),
                        "hora_registro": ult.get("hora"),
                        "estado": ult.get("estado"),
                    },
                    forzar=True,
                )
                if r.get("ok"):
                    st.success(r.get("mensaje"))
                else:
                    st.warning(r.get("mensaje") or "No enviado")
        else:
            st.caption("Reenvío de avisos: solo supervisor.")

    lotes = dash.get("lotes_sellados") or []
    with st.expander(f"Sellos ECC de hoy ({len(lotes)})"):
        if lotes:
            st.dataframe(pd.DataFrame(lotes), width="stretch", hide_index=True)
        else:
            st.caption("Aún no hay sellos archivados hoy.")

    _insp_dash = st.session_state.get("fw_usuario") or "Inspector"
    _k = dash.get("kpis") or {}
    _msg_dash = (
        f"Dashboard turno {dash.get('fecha')} | Planta: {_plant_label} | "
        f"Estado: {dash.get('estado_turno')} | Rupturas: {_k.get('rupturas_frio', 0)} | "
        f"Lecturas frío: {_k.get('lecturas_frio', 0)} | "
        f"Sellos ECC: {_k.get('sellos_ecc', 0)} | Emisor: {_insp_dash}"
    )
    try:
        _pub_dash, _sig_dash = motor_planta.firmar_reporte_ecc(_msg_dash)
        _modo_dash = motor_planta.modo_firma_activo()
        if _modo_dash == "real":
            st.caption(f"PDF del turno con sello Ed25519 real · `{motor_planta.motor_activo()}`")
        else:
            st.caption("PDF del turno firmado en modo demo (revise LLAVE_PRIVADA en secrets).")
    except Exception as _e_sig:
        _pub_dash, _sig_dash = "", ""
        st.caption(f"No se pudo firmar el PDF del turno: {_e_sig}")

    pdf_dash = funciones.generar_pdf_dashboard_turno(
        dash,
        planta_nombre=_plant_label,
        inspector=_insp_dash,
        rol=_rol_label,
        firma_ECDSA=_sig_dash,
        llave_publica=_pub_dash,
        mensaje_firmado=_msg_dash,
    )
    st.download_button(
        "Descargar PDF del turno (firmado ECC)",
        data=pdf_dash,
        file_name=f"dashboard_turno_{dash.get('fecha', 'hoy')}.pdf",
        mime="application/pdf",
        key="dl_pdf_dashboard_turno",
        type="primary",
    )

if vista == "qr":
    col_cen = st.container()
    with col_cen:
        pagina_ecc_style("QR pallet", "historial_reportes")
        with st.container():

            if not st.session_state["camara_qr_activa"]:
                if st.button(
                    "Activar escáner QR",
                    type="primary",
                    key="btn_activar_escaner_qr",
                ):
                    st.session_state["camara_qr_activa"] = True
                    st.rerun()
            else:
                foto_qr = st.camera_input(
                    "Cámara QR",
                    key=f"camera_escaneo_qr_{st.session_state['camera_qr_token']}",
                )
                if st.button("Apagar cámara", key="btn_apagar_camara_qr"):
                    _apagar_camara_qr()
                    st.rerun()

                if foto_qr is not None:
                    try:
                        with st.spinner("Decodificando QR y consultando Supabase…"):
                            resultado_qr = funciones.procesar_escaneo_qr_camara(foto_qr.getvalue())
                        st.session_state["ultimo_resultado_qr"] = resultado_qr
                    except Exception as e:
                        st.session_state["ultimo_resultado_qr"] = {
                            "verificado": False,
                            "tipo_ui": "error",
                            "mensaje_ui": f"Error en escaneo QR: {e}",
                        }
                    _apagar_camara_qr()
                    st.rerun()

            st.markdown("---")
            with st.expander("Validación manual / foto del QR (si no usa cámara)"):
                img_qr_upload = st.file_uploader(
                    "Subir foto del QR",
                    type=["png", "jpg", "jpeg", "webp"],
                    key="upload_foto_qr_pallet",
                )
                texto_qr_manual = st.text_area(
                    "Texto del QR (JSON / hash / lote|hash)",
                    height=90,
                    key="texto_manual_qr_pallet",
                    placeholder='{"lote":"L-001","hash_sha256":"abc...64 hex"}',
                )
                if st.button("Validar respaldo en Supabase", key="btn_validar_qr_respaldo"):
                    imagen_bytes = img_qr_upload.getvalue() if img_qr_upload is not None else None
                    try:
                        if imagen_bytes is not None and img_qr_upload is not None:
                            _ok_img, _msg_img = firewall.validar_upload_bytes(
                                img_qr_upload.name, imagen_bytes
                            )
                            if not _ok_img:
                                st.error(f"🛡️ Cortafuego: {_msg_img}")
                                resultado_qr = None
                            else:
                                resultado_qr = funciones.procesar_escaneo_qr_camara(imagen_bytes)
                        elif texto_qr_manual and texto_qr_manual.strip():
                            _ok_txt, _txt_o_err = firewall.validar_entrada_operativa(
                                texto_qr_manual.strip()
                            )
                            if not _ok_txt:
                                st.error(f"🛡️ Cortafuego: {_txt_o_err}")
                                resultado_qr = None
                            else:
                                resultado_qr = funciones.validar_pallet_por_qr(texto_qr=_txt_o_err)
                        else:
                            st.warning("Suba una imagen o pegue el texto del QR.")
                            resultado_qr = None
                        if resultado_qr is not None:
                            st.session_state["ultimo_resultado_qr"] = resultado_qr
                    except Exception as e:
                        st.error(f"Error en escaneo QR: {e}")

            resultado_qr_ui = st.session_state.get("ultimo_resultado_qr")
            if resultado_qr_ui:
                if resultado_qr_ui.get("tipo_ui") == "success":
                    st.success(
                        resultado_qr_ui.get("mensaje_ui")
                        or "✅ Pallet verificado de forma segura mediante QR en Supabase."
                    )
                else:
                    st.error(
                        resultado_qr_ui.get("mensaje_ui")
                        or "🚨 ALERTA: no se pudo verificar el pallet contra Supabase."
                    )

                payload_qr = resultado_qr_ui.get("payload") or {}
                if payload_qr:
                    st.caption(
                        f"Lote extraído: `{payload_qr.get('lote') or 'N/D'}` · "
                        f"Hash: `{(payload_qr.get('hash_sha256') or 'N/D')[:24]}"
                        f"{'…' if payload_qr.get('hash_sha256') and len(payload_qr.get('hash_sha256') or '') > 24 else ''}`"
                    )
                reg = resultado_qr_ui.get("registro")
                if reg:
                    with st.expander("Registro en historial_reportes (Supabase)"):
                        st.json(reg)
                sb_qr = resultado_qr_ui.get("supabase") or {}
                if sb_qr and not resultado_qr_ui.get("verificado"):
                    with st.expander("Detalle consulta Supabase"):
                        st.write(sb_qr.get("mensaje"))
                        st.caption(f"Endpoint: `{sb_qr.get('endpoint')}`")
                        if sb_qr.get("filas") is not None:
                            st.json(sb_qr.get("filas"))

if vista == "inicio":
    st.markdown("---")
    st.subheader("Servicios de planta")
    col_der = st.container()
    with col_der:
        if "panel_der" not in st.session_state:
            st.session_state["panel_der"] = None

        def _abrir_panel_der(pid: str):
            if st.session_state.get("panel_der") == pid:
                st.session_state["panel_der"] = None
            else:
                st.session_state["panel_der"] = pid

        # id del panel → etiqueta del botón (key Streamlit único por id)
        _ATAJOS_DER = (
            ("db", "Base de datos", "nav_der_db"),
            ("hist", "Historial de sellos", "nav_der_hist"),
            ("seg", "Seguridad", "nav_der_seg"),
            ("ecc", "Criptografía", "nav_der_ecc"),
        )

        _p = st.session_state.get("panel_der")
        for _pid, _label, _key in _ATAJOS_DER:
            if st.button(
                _label,
                key=_key,
                type="primary" if _p == _pid else "secondary",
                use_container_width=True,
            ):
                _abrir_panel_der(_pid)
                st.rerun()

        # —— Panel: Base de datos (solo DB / KPI) ——
        if st.session_state.get("panel_der") == "db":
            with st.container(border=True):
                st.markdown(
                    '<p class="sb-card-title">Infraestructura</p>'
                    '<p class="sb-card-heading">Estado de base de datos</p>',
                    unsafe_allow_html=True,
                )

                _sb_url, _sb_key, _sb_err = None, None, None
                try:
                    _sb_url, _sb_key, _sb_err = funciones._supabase_config()
                except Exception as _e_sb:
                    _sb_err = str(_e_sb)

                if _sb_url and _sb_key and not _sb_err:
                    st.markdown(
                        '<span class="sb-pill ok">Supabase conectado</span>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"""
                        <div class="sb-status-row"><span>Proyecto</span><span>{(_sb_url or "")[:36]}…</span></div>
                        <div class="sb-status-row"><span>Tabla sellos</span><span>historial_reportes</span></div>
                        <div class="sb-status-row"><span>API key</span><span>configurada</span></div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<span class="sb-pill warn">Supabase no configurado</span>',
                        unsafe_allow_html=True,
                    )
                    if _sb_err:
                        st.caption(str(_sb_err)[:180])

                st.markdown(
                    f"""
                    <div class="sb-status-row"><span>SQLite local</span><span>planta_calidad_prod.db</span></div>
                    <div class="sb-status-row"><span>Último POST sello</span>
                    <span>{"OK" if (st.session_state.get("ultimo_supabase") or {}).get("ok") else (st.session_state.get("ultimo_supabase") or {}).get("mensaje", "—")[:40]}</span></div>
                    """,
                    unsafe_allow_html=True,
                )

                ultimo_hash = st.session_state.get("ultimo_hash_reporte")
                if ultimo_hash:
                    st.caption(f"Último hash de sesión: `{str(ultimo_hash)[:20]}…`")

                _kpi = st.session_state.get("kpi_archivo") or {}
                if _kpi:
                    st.markdown("---")
                    st.markdown(
                        '<p class="sb-card-title">Archivo activo</p>',
                        unsafe_allow_html=True,
                    )
                    st.metric("Total registros", _kpi.get("filas", "—"))
                    st.metric("Campos vacíos", _kpi.get("errores", "—"))
                    st.metric(
                        "Confiabilidad",
                        f"{_kpi.get('porcentaje', '—')}%",
                        delta=_kpi.get("motor", ""),
                    )
                    if _kpi.get("historial"):
                        with st.expander("Historial de cargas (SQLite)"):
                            st.dataframe(
                                pd.DataFrame(_kpi["historial"]),
                                width="stretch",
                                hide_index=True,
                            )

        # —— Panel: Criptografía (solo ECC) ——
        if st.session_state.get("panel_der") == "ecc":
            with st.container(border=True):
                st.markdown(
                    '<p class="sb-card-title">Criptografía</p>'
                    '<p class="sb-card-heading">Verificación ECC</p>',
                    unsafe_allow_html=True,
                )

                try:
                    _modo_ecc = motor_planta.modo_firma_activo()
                    _backend_ecc = motor_planta.motor_activo()
                    _diag_ecc = motor_planta.diagnostico()
                    _pub_oficial = motor_planta.llave_publica_oficial_hex()
                except Exception:
                    _modo_ecc, _backend_ecc, _diag_ecc, _pub_oficial = "n/d", "n/d", "n/d", None

                if _modo_ecc == "real":
                    st.markdown(
                        '<span class="sb-pill ok">Ed25519 real</span>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<span class="sb-pill warn">Modo demo / revisión</span>',
                        unsafe_allow_html=True,
                    )

                _backend_ui = _backend_ecc
                if _modo_ecc == "real" and str(_backend_ecc) in ("python", "n/d"):
                    _backend_ui = "rust" if motor_planta.rust_disponible() else _backend_ecc

                st.markdown(
                    f"""
                    <div class="sb-status-row"><span>Modo firma</span><span>{_modo_ecc}</span></div>
                    <div class="sb-status-row"><span>Backend</span><span>{_backend_ui}</span></div>
                    """,
                    unsafe_allow_html=True,
                )
                if _pub_oficial:
                    st.caption(f"Llave pública oficial: `{_pub_oficial[:16]}…`")
                    st.caption(
                        "La llave de secrets ya está activa. El sello del PDF se firmará "
                        "con ella al generar el reporte."
                    )
                st.caption(f"Diagnóstico: {_diag_ecc}")
                st.caption(
                    "PDF firmado: use **Verificación pública ECC** en la barra de navegación."
                )

        # —— Panel: Historial de sellos ——
        if st.session_state.get("panel_der") == "hist":
            with st.container(border=True):
                st.markdown(
                    '<p class="sb-card-title">SQLite · Sellos firmados</p>'
                    '<p class="sb-card-heading">Historial de reportes</p>',
                    unsafe_allow_html=True,
                )
                st.caption("Fecha, lote, hash y responsable de cada sello ECC.")
                historial_reportes = funciones.cargar_historial_reportes_db(200)
                _n_hist = len(historial_reportes) if historial_reportes else 0
                st.markdown(
                    f'<div class="sb-status-row"><span>Registros</span><span>{_n_hist}</span></div>',
                    unsafe_allow_html=True,
                )
                if historial_reportes:
                    df_hist = pd.DataFrame(historial_reportes)
                    _cols_pref = [
                        c
                        for c in (
                            "Fecha",
                            "fecha_hora",
                            "Lote",
                            "lote",
                            "Hash",
                            "hash_sha256",
                            "Responsable",
                            "responsable",
                            "Archivo",
                            "archivo",
                        )
                        if c in df_hist.columns
                    ]
                    df_show = df_hist[_cols_pref].copy() if _cols_pref else df_hist
                    for _hc in ("Hash", "hash_sha256"):
                        if _hc in df_show.columns:
                            df_show[_hc] = df_show[_hc].astype(str).str.slice(0, 12) + "…"
                    st.dataframe(df_show, width="stretch", hide_index=True, height=280)
                    if st.session_state.get("ultimo_hash_reporte"):
                        st.caption(
                            f"Último hash sesión: "
                            f"`{str(st.session_state['ultimo_hash_reporte'])[:20]}…`"
                        )
                else:
                    st.info("Sin reportes archivados. Genere un sello ECC al cargar un Excel.")

        # —— Contenido: Seguridad ——
        if st.session_state.get("panel_der") == "seg":
            with st.container(border=True):
                st.markdown(
                    '<p class="sb-card-title">Seguridad</p>'
                    '<p class="sb-card-heading">Cortafuego de planta</p>',
                    unsafe_allow_html=True,
                )
                _fw = firewall.resumen_panel(st.session_state)
                st.markdown(
                    '<span class="sb-pill ok">Firewall ON</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"""
                    <div class="sb-status-row"><span>Usuario sesión</span><span>{_fw.get('usuario')}</span></div>
                    <div class="sb-status-row"><span>Token</span><span>{_fw.get('token_corto')}</span></div>
                    <div class="sb-status-row"><span>Timeout</span><span>{_fw.get('timeout_min')} min</span></div>
                    <div class="sb-status-row"><span>Max login fails</span><span>{_fw.get('max_intentos')}</span></div>
                    <div class="sb-status-row"><span>Upload máx.</span><span>{_fw.get('max_upload_mb')} MB</span></div>
                    """,
                    unsafe_allow_html=True,
                )
                _ev = firewall.ultimos_eventos(5)
                if _ev:
                    with st.expander("Últimos eventos de seguridad"):
                        for e in _ev:
                            import html as _html

                            fecha = _html.escape(str(e.get("fecha") or "—"))
                            evento = _html.escape(str(e.get("evento") or "—"))
                            sev = _html.escape(str(e.get("severidad") or "info"))
                            det = _html.escape(str(e.get("detalle") or "").strip())
                            st.markdown(
                                f"""
                                <div class="fw-event-row">
                                  <div class="fw-event-time">{fecha}</div>
                                  <div class="fw-event-main">
                                    <span class="fw-event-name">{evento}</span>
                                    <span class="fw-event-sev">{sev}</span>
                                  </div>
                                  <div class="fw-event-det">{det}</div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

if vista == "contenedores":
    pagina_ecc_style("Contenedores", "Booking · ISO 6346 · precintos")
    with st.container():

        col_c_scan, col_c_form = st.columns([1, 1])

        with col_c_scan:
            if not st.session_state["camara_cnt_activa"]:
                if st.button(
                    "Activar escáner",
                    type="primary",
                    key="btn_activar_escaner_cnt",
                ):
                    st.session_state["camara_cnt_activa"] = True
                    st.rerun()
            else:
                foto_cnt = st.camera_input(
                    "Cámara contenedor",
                    key=f"camera_escaneo_cnt_{st.session_state['camera_cnt_token']}",
                )
                if st.button("Apagar cámara", key="btn_apagar_camara_cnt"):
                    _apagar_camara_cnt()
                    st.rerun()

                if foto_cnt is not None:
                    try:
                        with st.spinner("Leyendo QR y consultando contenedor…"):
                            res_cnt = funciones.procesar_escaneo_contenedor_camara(
                                foto_cnt.getvalue()
                            )
                        st.session_state["ultimo_resultado_cnt"] = res_cnt
                        _cnt_aplicar_prefill(
                            res_cnt.get("payload"),
                            res_cnt.get("registro") or res_cnt.get("local"),
                        )
                    except Exception as e:
                        st.session_state["ultimo_resultado_cnt"] = {
                            "verificado": False,
                            "tipo_ui": "error",
                            "mensaje_ui": f"Error de escaneo: {e}",
                        }
                    _apagar_camara_cnt()
                    st.rerun()

            st.markdown("---")
            texto_cnt = st.text_input(
                "Booking o contenedor",
                placeholder="TGBU1234567 · BKG-998",
                key="cnt_lookup_manual",
            )
            if st.button("Buscar contenedor", key="btn_cnt_lookup"):
                if not (texto_cnt or "").strip():
                    st.warning("Escriba un booking o contenedor.")
                else:
                    ok_in, txt_ok = firewall.validar_entrada_operativa(texto_cnt.strip())
                    if not ok_in:
                        st.error(f"Cortafuego: {txt_ok}")
                    else:
                        res_cnt = funciones.validar_y_consultar_contenedor(texto_qr=txt_ok)
                        st.session_state["ultimo_resultado_cnt"] = res_cnt
                        _cnt_aplicar_prefill(
                            res_cnt.get("payload"),
                            res_cnt.get("registro") or res_cnt.get("local"),
                        )
                        st.rerun()

            res_ui = st.session_state.get("ultimo_resultado_cnt")
            if res_ui:
                if res_ui.get("tipo_ui") == "success":
                    st.success(res_ui.get("mensaje_ui") or "Contenedor OK")
                else:
                    st.error(res_ui.get("mensaje_ui") or "No encontrado")
                pl = res_ui.get("payload") or {}
                if pl:
                    st.caption(
                        f"Leído · booking `{pl.get('booking') or 'N/D'}` · "
                        f"contenedor `{(pl.get('contenedor') or 'N/D')}`"
                    )

        with col_c_form:
            booking_input = st.text_input(
                "Booking *",
                placeholder="BKG-998231",
                key="cnt_form_booking",
            )
            contenedor_input = st.text_input(
                "Contenedor reefer * (ISO 6346)",
                placeholder="TGBU1234567",
                key="cnt_form_contenedor",
            )
            precinto_linea_input = st.text_input(
                "Precinto línea naviera *",
                placeholder="MSC-L99821",
                key="cnt_form_plinea",
            )
            precinto_senasa_input = st.text_input(
                "Precinto SENASA",
                placeholder="SENASA-004821",
                key="cnt_form_psenasa",
            )
            st.caption(f"Destino: {mercado_destino}")

            if st.button(
                "Sellar y registrar contenedor",
                type="primary",
                key="btn_cnt_sellar",
            ):
                try:
                    resultado_cnt = funciones.registrar_contenedor_despacho(
                        booking=booking_input,
                        contenedor=contenedor_input,
                        precinto_linea=precinto_linea_input,
                        precinto_senasa=precinto_senasa_input,
                        destino=mercado_destino,
                        estado="SELLADO Y LISTO",
                        inspector=auditor_nombre,
                    )
                    if resultado_cnt.get("tipo_ui") == "success":
                        st.success(resultado_cnt.get("mensaje_ui"))
                    else:
                        st.error(resultado_cnt.get("mensaje_ui"))
                    sb_c = resultado_cnt.get("supabase") or {}
                    if sb_c.get("ok"):
                        if sb_c.get("ya_existia") or sb_c.get("status") == 409:
                            st.info("☁️ Supabase: contenedor ya estaba en la nube.")
                        else:
                            st.caption(f"☁️ Supabase: {sb_c.get('mensaje')}")
                    elif sb_c.get("configurado") is False:
                        st.caption("☁️ Supabase no configurado (solo SQLite local).")
                    elif sb_c:
                        st.warning(sb_c.get("mensaje") or "Error remoto contenedores_despacho")
                except Exception as e:
                    st.error(e)

        lista_cont_db = funciones.cargar_contenedores_db(50)
        if lista_cont_db:
            with st.expander(f"Contenedores registrados ({len(lista_cont_db)})"):
                st.dataframe(pd.DataFrame(lista_cont_db), width="stretch", hide_index=True)

# ─── Alertas (pantalla propia) ────────────────────────────────────────────────
if vista == "alertas":
    pagina_ecc_style("Alertas", "Frío · pesos · LMR")
    if _es_supervisor:
        with st.expander("Borrar alertas de frío (SQLite local)"):
            st.caption(
                "Supabase ≠ alertas de pantalla. Esta app usa `planta_calidad_prod.db`."
            )
            if st.button("Borrar rupturas locales", key="alertas_del_rupturas"):
                r = purgar_frio_local_ui(solo_rupturas=True)
                (st.success if r.get("ok") else st.error)(r.get("mensaje"))
                if r.get("ok"):
                    st.rerun()
            if st.button("Borrar todo el frío local", key="alertas_del_frio_all"):
                r = purgar_frio_local_ui(solo_rupturas=False)
                (st.success if r.get("ok") else st.error)(r.get("mensaje"))
                if r.get("ok"):
                    st.rerun()
    _df_al = st.session_state.get("df_trabajo")
    _cols_al = (
        funciones.resolver_mapa_columnas(_df_al, st.session_state.get("mapeo_columnas_manual"))
        if _df_al is not None
        else None
    )
    render_modulo_alertas_tendencias(
        df_packing=_df_al,
        cols_mapa=_cols_al,
        peso_min_caja=peso_min_caja,
        max_merma_permitida=max_merma_permitida,
        key_prefix="m7_vista_alertas",
    )

# ─── Operación del lote (un módulo a la vez) ──────────────────────────────────
if vista == "operacion" and st.session_state.get("df_trabajo") is not None:
    try:
        df_original = st.session_state["df_trabajo"]
        archivo_nombre = st.session_state.get("nombre_archivo") or (archivo.name if archivo is not None else "lote.csv")
        # compat: código legacy usa archivo.name
        class _ArchivoProxy:
            def __init__(self, name):
                self.name = name
        archivo = archivo if archivo is not None else _ArchivoProxy(archivo_nombre)
        if "mapeo_columnas_manual" not in st.session_state:
            st.session_state["mapeo_columnas_manual"] = {}
        cols_traza = funciones.resolver_mapa_columnas(
            df_original,
            st.session_state.get("mapeo_columnas_manual"),
        )

        columnas_faltantes = funciones.campos_criticos_sin_mapear(cols_traza)

        if len(columnas_faltantes) > 0:
            st.warning(
                f"Faltan columnas clave: **{', '.join(columnas_faltantes)}**. "
                "Asigne el mapeo abajo o continue en modo flexible."
            )
        else:
            st.caption(
                "Columnas clave: "
                + " · ".join(
                    f"{k.upper()}→`{cols_traza[k]}`"
                    for k in ("lote", "peso", "calibre")
                    if cols_traza.get(k)
                )
            )

        with st.expander("Mapear columnas del packing", expanded=bool(columnas_faltantes)):
            st.caption("Si el Excel usa otros nombres, elija la columna real de cada campo.")
            opts_base = ["(auto)", "(ninguna)"] + [str(c) for c in df_original.columns]
            manual_prev = dict(st.session_state.get("mapeo_columnas_manual") or {})
            nuevo_manual = {}
            grid = st.columns(3)
            for i, campo in enumerate(funciones.CAMPOS_MAPEO_UI):
                with grid[i % 3]:
                    actual = manual_prev.get(campo)
                    if actual and actual in opts_base:
                        idx = opts_base.index(actual)
                    elif cols_traza.get(campo) and cols_traza[campo] in opts_base:
                        # mostrar auto detectado como selección visual en (auto)
                        idx = 0
                    else:
                        idx = 0
                    elegido = st.selectbox(
                        campo.replace("_", " ").title(),
                        opts_base,
                        index=idx,
                        key=f"map_col_{campo}",
                    )
                    if elegido == "(auto)":
                        nuevo_manual.pop(campo, None)
                    else:
                        nuevo_manual[campo] = elegido
            bmap1, bmap2 = st.columns(2)
            with bmap1:
                if st.button("Aplicar mapeo", type="primary", key="btn_aplicar_mapeo"):
                    st.session_state["mapeo_columnas_manual"] = {
                        k: v for k, v in nuevo_manual.items() if v not in (None, "", "(auto)")
                    }
                    st.success("Mapeo aplicado.")
                    st.rerun()
            with bmap2:
                if st.button("Restablecer auto", key="btn_reset_mapeo"):
                    st.session_state["mapeo_columnas_manual"] = {}
                    for _c in funciones.CAMPOS_MAPEO_UI:
                        st.session_state.pop(f"map_col_{_c}", None)
                    st.rerun()

        if "Observaciones_Rechazo" not in df_original.columns:
            df_original["Observaciones_Rechazo"] = ""
            st.session_state["df_trabajo"] = df_original

        total_filas = len(df_original)
        total_columnas = len(df_original.columns)
        total_duplicados = int(df_original.duplicated().sum())

        vacios_por_columna = (df_original == "").sum()
        total_errores = int(vacios_por_columna.sum())

        celdas_totales = total_filas * total_columnas
        
        try:
            eficiencia_rust, estado_rust = motor_planta.validar_datos_planta(
                float(total_filas), float(total_errores)
            )
            porcentaje_limpio = round(eficiencia_rust, 1)
            estado_rust = f"{estado_rust} [{motor_planta.motor_activo()}]"
        except Exception:
            porcentaje_limpio = (
                round(((celdas_totales - total_errores) / celdas_totales) * 100, 1)
                if celdas_totales > 0
                else 100
            )
            estado_rust = "Motor Python Respaldo"

        hora_actual = datetime.datetime.now().strftime("%H:%M:%S")
        funciones.guardar_historial_db(hora_actual, archivo.name, total_filas, f"{porcentaje_limpio}%")

        st.session_state["kpi_archivo"] = {
            "filas": total_filas,
            "errores": total_errores,
            "porcentaje": porcentaje_limpio,
            "motor": estado_rust,
            "historial": funciones.cargar_historial_db(),
            "archivo": archivo.name,
        }
        historial_db_data = st.session_state["kpi_archivo"]["historial"]

        pagina_ecc_style(
            modulo_nav,
            f"{archivo.name} · {total_filas} filas · {porcentaje_limpio}% limpio",
        )


        if modulo_nav == "Resumen del lote":
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Filas", total_filas)
            c2.metric("Columnas", total_columnas)
            c3.metric("Duplicados", total_duplicados)
            c4.metric("Confiabilidad", f"{porcentaje_limpio}%")
            with st.expander("Vista previa", expanded=False):
                st.dataframe(df_original.head(30), width="stretch", hide_index=True)
            if st.button("Alertas", key="btn_resumen_a_m7"):
                st.session_state["vista_planta"] = "operacion"
                st.session_state["modulo_nav"] = "7 · Alertas y tendencias"
                st.rerun()
            if st.button("Cierre", key="btn_resumen_a_cierre"):
                st.session_state["vista_planta"] = "operacion"
                st.session_state["modulo_nav"] = "Limpieza y cierre"
                st.rerun()


        if modulo_nav == "1 · Balanza / SSCC":
            # MÓDULO 1
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                peso_capturado = st.number_input("Peso neto (kg)", value=4.5, step=0.1)
                if st.button("Registrar peso", type="primary"):
                    df_nuevo, ok_peso, col_peso_usada = funciones.registrar_peso_ultima_fila(df_original, peso_capturado)
                    if ok_peso:
                        st.session_state["df_trabajo"] = df_nuevo
                        df_original = df_nuevo
                        funciones.guardar_cambio_db(
                            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            len(df_original) - 1,
                            col_peso_usada,
                            "(balanza)",
                            str(peso_capturado),
                            auditor_nombre,
                        )
                        st.success(f"Peso de {peso_capturado} kg registrado en la última fila (columna `{col_peso_usada}`).")
                        st.rerun()
                    else:
                        st.error("No se encontró una columna de PESO en el archivo, o el archivo está vacío.")
            with col_b2:
                sscc_input = st.text_input("SSCC / caja / pallet", placeholder="077512345678901234")
                if sscc_input:
                    df_sscc = funciones.buscar_registros_por_codigo(df_original, sscc_input)
                    if df_sscc.empty:
                        st.error(f"Código `{sscc_input}` no encontrado en la base cargada.")
                    else:
                        st.success(f"Unidad encontrada: **{sscc_input}** ({len(df_sscc)} registro(s))")
                        st.dataframe(df_sscc, width="stretch", hide_index=True)


        if modulo_nav == "2 · LMR / SENASA":
            # MÓDULO 2
            lotes_disponibles = []
            if cols_traza["lote"]:
                lotes_disponibles = sorted(
                    [x for x in df_original[cols_traza["lote"]].astype(str).str.strip().unique() if x and x != "nan"]
                )
            lote_default = lotes_disponibles[0] if lotes_disponibles else ""
            col_mle1, col_mle2, col_mle3 = st.columns(3)
            with col_mle1:
                if lotes_disponibles:
                    lote_lmr_sel = st.selectbox("Lote a consultar LMR:", options=lotes_disponibles, index=0)
                else:
                    lote_lmr_sel = st.text_input("Ingrese Lote a Consultar LMR:", value=lote_default, placeholder="Ej: LOTE-001")
            with col_mle2:
                analisis_lab = st.selectbox(
                    "Resultado de laboratorio (manual / respaldo):",
                    ["Usar dato del archivo", "Conforme (Bajo LMR)", "Alerta (Cercano al Límite)", "Rechazado (Supera LMR)"],
                )
            with col_mle3:
                estado_lmr = "sin_dato"
                detalle_lmr = "Sin lote consultado"
                df_lote_lmr = pd.DataFrame()
                if lote_lmr_sel:
                    df_lote_lmr = funciones.buscar_registros_por_codigo(df_original, lote_lmr_sel)
                    if cols_traza["lote"] and df_lote_lmr.empty:
                        mask_lote = df_original[cols_traza["lote"]].astype(str).str.strip().str.fullmatch(
                            str(lote_lmr_sel).strip(), case=False, na=False
                        )
                        df_lote_lmr = df_original.loc[mask_lote].copy()

                    if analisis_lab != "Usar dato del archivo":
                        if "Conforme" in analisis_lab:
                            estado_lmr = "conforme"
                        elif "Alerta" in analisis_lab:
                            estado_lmr = "alerta"
                        else:
                            estado_lmr = "rechazado"
                        detalle_lmr = analisis_lab
                    elif not df_lote_lmr.empty and cols_traza["lmr"]:
                        valores_lmr = df_lote_lmr[cols_traza["lmr"]].astype(str).str.strip()
                        estados = [funciones.interpretar_estado_lmr(v) for v in valores_lmr if v and v != "nan"]
                        if "rechazado" in estados:
                            estado_lmr = "rechazado"
                        elif "alerta" in estados:
                            estado_lmr = "alerta"
                        elif "conforme" in estados:
                            estado_lmr = "conforme"
                        detalle_lmr = ", ".join(sorted(set(valores_lmr.head(5))))
                    elif df_lote_lmr.empty:
                        detalle_lmr = "Lote no encontrado en archivo"
                    else:
                        detalle_lmr = "Lote hallado, sin columna LMR; use el selector manual"

            if estado_lmr == "conforme":
                st.success("APROBADO")
            elif estado_lmr == "alerta":
                st.warning("EN CUARENTENA")
            elif estado_lmr == "rechazado":
                st.error("BLOQUEADO")
            else:
                st.info("Sin veredicto")
            if detalle_lmr:
                st.caption(detalle_lmr)

            if lote_lmr_sel and not df_lote_lmr.empty:
                with st.expander(f"Registros del lote `{lote_lmr_sel}` ({len(df_lote_lmr)})"):
                    st.dataframe(df_lote_lmr, width="stretch", hide_index=True)


        if modulo_nav == "3 · Trazabilidad":
            # MÓDULO 3
            col_inv1, col_inv2 = st.columns([2, 3])
            with col_inv1:
                caja_busqueda_inversa = st.text_input(
                    "Caja o pallet",
                    placeholder="CJ-9842 / SSCC / LOTE",
                )
                cols_detectadas = [f"`{v}` ({k})" for k, v in cols_traza.items() if v]
            with col_inv2:
                if caja_busqueda_inversa:
                    df_traza = funciones.buscar_registros_por_codigo(df_original, caja_busqueda_inversa)
                    if df_traza.empty:
                        st.error("No encontrado")
                    else:
                        arbol = funciones.armar_arbol_trazabilidad(
                            df_traza.iloc[0], cols_traza, auditor_nombre, caja_busqueda_inversa
                        )
                        st.markdown(
                            f"""
**`{arbol['codigo']}`**

- Fundo: {arbol['fundo']} · Productor: {arbol['productor']}
- Lote: {arbol['lote']} · Turno: {arbol['turno']}
- Cosecha: {arbol['cosecha']} · LMR: {arbol['lmr']}
"""
                        )
                        if len(df_traza) > 1:
                            st.dataframe(df_traza, width="stretch", hide_index=True)


        if modulo_nav == "4 · Cadena de frío":
            # MÓDULO 4
            t_min_f, t_max_f = funciones.obtener_rango_frio_fruta(
                producto_sel,
                temp_min_override=temp_min_limite,
                temp_max_override=temp_max_limite if producto_sel == "Personalizado" else temp_max_limite,
            )
            st.caption(f"{producto_sel}: {t_min_f}–{t_max_f} °C")

            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                camara_sel = st.selectbox(
                    "Cámara Frigorífica / Túnel:",
                    ["Pre-Cámara 01", "Túnel de Enfriamiento 03", "Cámara de Almacenamiento 05", "Contenedor Reefer Puerto"],
                )
            with col_f2:
                valor_temp_default = float(
                    max(t_min_f, min(limit_temp_default, t_max_f))
                )
                temp_actual_camara = st.number_input(
                    "Temperatura Registrada (°C):",
                    value=valor_temp_default,
                    step=0.5,
                    format="%.1f",
                )
            with col_f3:
                prev = funciones.validar_temperatura_fruta(
                    temp_actual_camara,
                    producto_sel,
                    temp_min_override=t_min_f,
                    temp_max_override=t_max_f,
                )
                if prev["en_rango"]:
                    st.success(
                        f"✅ En rango ({prev['temp_min']}–{prev['temp_max']} °C) · "
                        f"lectura {prev['temperatura']} °C"
                    )
                else:
                    st.error(
                        f"🚨 Fuera de rango ({prev['temp_min']}–{prev['temp_max']} °C) · "
                        f"lectura {prev['temperatura']} °C"
                    )

                if st.button("💾 Registrar lectura de frío"):
                    try:
                        resultado_frio = funciones.registrar_control_frio(
                            camara=camara_sel,
                            temperatura=float(temp_actual_camara),
                            producto=producto_sel,
                            inspector=auditor_nombre,
                            temp_min_override=t_min_f,
                            temp_max_override=t_max_f,
                        )
                        if resultado_frio["tipo_ui"] == "success":
                            st.success(resultado_frio["mensaje_ui"])
                        else:
                            st.error(resultado_frio["mensaje_ui"])
                            av = resultado_frio.get("aviso") or {}
                            if av.get("ok"):
                                st.warning(f"📲 {av.get('mensaje')}")
                            elif av.get("omitido"):
                                st.caption(av.get("mensaje") or "")
                            elif av.get("configurado") is False:
                                st.caption(
                                    "Avisos WA/email no configurados "
                                    "(secrets [avisos])."
                                )
                            elif av.get("mensaje"):
                                st.caption(av.get("mensaje"))

                        if resultado_frio.get("sqlite_ok"):
                            pass
                        else:
                            st.warning(resultado_frio.get("sqlite_msg", "Error SQLite"))

                        sb_f = resultado_frio.get("supabase") or {}
                        if sb_f.get("ok"):
                            pass
                        elif sb_f.get("configurado") is False:
                            pass
                        else:
                            st.error(sb_f.get("mensaje") or "Error Supabase")
                    except Exception as e:
                        st.error(e)

            historial_frio = funciones.cargar_frio_db()
            if historial_frio:
                with st.expander("Historial de control de frío (SQLite)"):
                    st.dataframe(pd.DataFrame(historial_frio), width="stretch", hide_index=True)


        if modulo_nav == "7 · Alertas y tendencias":
            # MÓDULO 7 — con packing cargado (frío + patrones del lote)
            render_modulo_alertas_tendencias(
                df_packing=df_original,
                cols_mapa=cols_traza,
                peso_min_caja=peso_min_caja,
                max_merma_permitida=max_merma_permitida,
                key_prefix="m7_packing",
            )


        if modulo_nav == "Limpieza y cierre":
            st.subheader("Columnas a exportar")
            todas_cols = list(df_original.columns)

            default_cols = [
                c for c in todas_cols if any(k in c.upper() for k in ["CAJA", "PESO", "LOTE", "CODIGO", "OBServaciones"])
            ]
            if not default_cols:
                default_cols = todas_cols[: min(4, len(todas_cols))]

            cols_elegidas = st.multiselect(
                "Selecciona las columnas que formarán parte del Packing List y Reporte Final:",
                options=todas_cols,
                default=default_cols,
            )

            df_export = df_original[cols_elegidas].copy() if cols_elegidas else df_original.copy()

            st.subheader("Limpieza, auditoría y errores")
            col_l1, col_l2, col_l3, col_l4 = st.columns([1, 1, 1, 1])
            with col_l1:
                if not st.session_state["lote_congelado"]:
                    if st.button("🧹 Limpiar Espacios Ocultos"):
                        df_original = df_original.map(lambda x: str(x).strip() if pd.notna(x) else "")
                        df_export = df_original[cols_elegidas].copy() if cols_elegidas else df_original.copy()
                        st.success("¡Espacios eliminados!")
            with col_l2:
                if not st.session_state["lote_congelado"]:
                    if st.button("📝 Rellenar Vacíos con (-)"):
                        df_original = df_original.replace("", "-")
                        df_export = df_original[cols_elegidas].copy() if cols_elegidas else df_original.copy()
                        st.success("¡Vacíos reemplazados!")
            with col_l3:
                if st.button("🔍 Ver Registros con Vacíos"):
                    st.session_state["mostrar_vacios"] = not st.session_state["mostrar_vacios"]
            with col_l4:
                mask_errores_gen = (df_original == "").any(axis=1)
                col_peso_chk_aux = [c for c in df_original.columns if "PESO" in c.upper()]
                if col_peso_chk_aux:
                    pesos_num_aux = pd.to_numeric(df_original[col_peso_chk_aux[0]], errors="coerce")
                    mask_errores_gen = mask_errores_gen | (pesos_num_aux < peso_min_caja)
            
                df_solo_errores_dl = df_original[mask_errores_gen]
                pdf_errores_buffer = funciones.generar_pdf_errores(df_solo_errores_dl, archivo.name, producto_sel, auditor_nombre)
            
                st.download_button(
                    label="📥 Descargar Solo Errores (PDF)",
                    data=pdf_errores_buffer.getvalue(),
                    file_name="Reporte_Errores_Planta.pdf",
                    mime="application/pdf",
                )

            if st.session_state["mostrar_vacios"]:
                st.warning("⚠️ **Mostrando únicamente filas que contienen campos vacíos o incompletos:**")
                mask_vacios = (df_original == "").any(axis=1)
                df_solo_vacios = df_original[mask_vacios]
                if not df_solo_vacios.empty:
                    st.dataframe(df_solo_vacios.style.map(funciones.resaltar_errores_celdas), use_container_width=True)
                else:
                    st.success("¡Excelente! No hay registros con celdas vacías en este archivo.")

            st.subheader("Control de calidad y estadísticas")
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_pallet_chk = [c for c in df_original.columns if "PALLET" in c.upper()]
            total_pallets = df_original[col_pallet_chk[0]].nunique() if col_pallet_chk else "N/D"
        
            col_lote_chk = [c for c in df_original.columns if "LOTE" in c.upper()]
            total_lotes = df_original[col_lote_chk[0]].nunique() if col_lote_chk else "N/D"

            col_prod_chk = [c for c in df_original.columns if "PRODUCTOR" in c.upper()]
            total_productores = df_original[col_prod_chk[0]].nunique() if col_prod_chk else "N/D"

            with col_m1:
                st.metric("Total Pallets (SSCC)", total_pallets)
            with col_m2:
                st.metric("Lotes en Proceso", total_lotes)
            with col_m3:
                st.metric("Productores Implicados", total_productores)
            with col_m4:
                st.metric("Duplicados Detectados", total_duplicados)

            col_peso_chk = [c for c in df_original.columns if "PESO" in c.upper()]
            if col_peso_chk:
                pesos_num = pd.to_numeric(df_original[col_peso_chk[0]], errors="coerce")
                cajas_livianas = (pesos_num < peso_min_caja).sum()
                peso_promedio = round(pesos_num.mean(), 2) if not pesos_num.empty else 0
                peso_std = round(pesos_num.std(), 2) if not pesos_num.empty else 0
                st.caption(f"Peso medio {peso_promedio} kg · σ {peso_std}")

                if cajas_livianas > 0:
                    st.error(f"⚠️ **Alerta Crítica de Pesaje:** Se encontraron {cajas_livianas} registros por debajo del peso mínimo de {peso_min_caja} kg.")

            col1, col2 = st.columns(2)
            with col1:
                col_calibre = [c for c in df_original.columns if "CALIBRE" in c.upper()]
                if col_calibre:
                    conteo_calibres = df_original[col_calibre[0]].value_counts().reset_index()
                    conteo_calibres.columns = ["Calibre", "Cajas"]
                    st.caption("Calibres")
                    st.dataframe(conteo_calibres.T, use_container_width=True)
                    
                    st.bar_chart(conteo_calibres.set_index("Calibre"))

            with col2:
                col_cat = [c for c in df_original.columns if "CATEGORIA" in c.upper() or "CAT" in c.upper()]
                if col_cat:
                    conteo_cat = df_original[col_cat[0]].value_counts()
                    descarte = conteo_cat.get("DESCARTE", 0) + conteo_cat.get("MERMA", 0)
                    porcentaje_merma = round((descarte / total_filas) * 100, 2)

                    if porcentaje_merma > max_merma_permitida:
                        st.error(f"🚨 **Alerta de Merma Elevada:** {porcentaje_merma}% de descarte (Límite: {max_merma_permitida}%).")
                    else:
                        st.success(f"✅ **Merma Bajo Control:** {porcentaje_merma}% de descarte.")

            st.markdown("---")
            st.subheader("Sello criptográfico ECC del lote")
            resumen_datos = f"Auditoría de Planta - Cultivo: {producto_sel} - Fecha: {datetime.date.today()} - Registros: {total_filas}"

            try:
                # Reutilizar el mismo sello en reruns de Streamlit
                cache_sello = st.session_state.get("cache_sello_ecc")
                if (
                    not cache_sello
                    or cache_sello.get("mensaje") != resumen_datos
                    or cache_sello.get("archivo") != archivo.name
                    or cache_sello.get("algo") != "Ed25519"
                ):
                    llave_publica, sello_digital = motor_planta.firmar_reporte_ecc(resumen_datos)
                    st.session_state["cache_sello_ecc"] = {
                        "mensaje": resumen_datos,
                        "archivo": archivo.name,
                        "llave_publica": llave_publica,
                        "sello_digital": sello_digital,
                        "modo": motor_planta.modo_firma_activo(),
                        "backend": motor_planta.motor_activo(),
                        "algo": "Ed25519",
                    }
                else:
                    llave_publica = cache_sello["llave_publica"]
                    sello_digital = cache_sello["sello_digital"]

                modo = st.session_state["cache_sello_ecc"].get("modo") or motor_planta.modo_firma_activo()
                backend = st.session_state["cache_sello_ecc"].get("backend") or motor_planta.motor_activo()
                if modo == "real":
                    st.success(f"🔒 Sello real Ed25519 · secrets + backend `{backend}`")
                    if str(backend).startswith("python"):
                        st.caption("Motor Rust no activo; fallback Python (cryptography / PyNaCl / ed25519).")
                else:
                    st.warning(
                        "🧪 Modo demo: no se pudo usar `st.secrets['LLAVE_PRIVADA']`. "
                        "Se firmó con llave Ed25519 efímera."
                    )
                st.code(f"Sello Digital (Firma ECC): {sello_digital}")
                st.caption(f"Llave Pública de Verificación: {llave_publica}")
                st.caption(f"Modo de firma: `{modo}` · Backend: `{backend}`")
                st.caption(f"Diagnóstico: {motor_planta.diagnostico()}")

                # Lote(s) detectados en el archivo
                if cols_traza.get("lote"):
                    lotes_vals = [
                        v for v in df_original[cols_traza["lote"]].astype(str).str.strip().unique()
                        if v and v.lower() != "nan"
                    ]
                    if not lotes_vals:
                        lote_reporte = "SIN-LOTE"
                    elif len(lotes_vals) <= 3:
                        lote_reporte = ", ".join(lotes_vals)
                    else:
                        lote_reporte = f"{lotes_vals[0]} … (+{len(lotes_vals) - 1} lotes)"
                else:
                    lote_reporte = archivo.name

                hash_reporte = funciones.calcular_hash_reporte(
                    resumen_datos, sello_digital, llave_publica
                )
                fecha_firma = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                try:
                    resultado_hist = funciones.guardar_reporte_historico(
                        fecha_hora=fecha_firma,
                        lote=lote_reporte,
                        hash_sha256=hash_reporte,
                        responsable=auditor_nombre,
                        archivo=archivo.name,
                        producto=producto_sel,
                        registros=total_filas,
                        firma_ecc=sello_digital,
                        llave_publica=llave_publica,
                        mensaje=resumen_datos,
                        modo_firma=modo,
                        backend=backend,
                    )
                except Exception as e:
                    st.error(e)
                    resultado_hist = {"guardado": False, "supabase_detalle": {}}

                st.session_state["ultimo_hash_reporte"] = hash_reporte
                st.session_state["ultimo_supabase"] = resultado_hist.get("supabase_detalle") or {}

                if resultado_hist.get("guardado"):
                    st.info(
                        f"📂 Historial local: archivado (id `{resultado_hist.get('id')}`) · "
                        f"Hash `{hash_reporte[:16]}…`"
                    )
                elif resultado_hist.get("ya_existia"):
                    st.caption(
                        f"📂 Historial local: sello ya registrado (hash `{hash_reporte[:16]}…`)"
                    )

                # --- Envío explícito a Supabase (también reintenta si el guardado falló en remoto) ---
                try:
                    sb = resultado_hist.get("supabase_detalle") or {}
                    # Reintento directo para forzar POST solo con fecha/lote/hash_sha256/inspector
                    if not sb.get("ok"):
                        sb = funciones.enviar_sello_a_supabase(
                            fecha=fecha_firma,
                            lote=lote_reporte,
                            hash_sha256=hash_reporte,
                            inspector=auditor_nombre,
                        )
                        st.session_state["ultimo_supabase"] = sb

                    if sb.get("ok"):
                        if sb.get("ya_existia") or sb.get("status") == 409:
                            st.info(
                                "☁️ Supabase · sello **ya registrado** (hash único). "
                                "No es un error — no se duplicó el registro."
                            )
                        else:
                            st.success(
                                f"☁️ Supabase OK · public.historial_reportes · {sb.get('mensaje', '')}"
                            )
                        with st.expander("Detalle payload Supabase"):
                            st.json(sb.get("payload") or {})
                            st.caption(f"Endpoint: `{sb.get('endpoint')}` · HTTP {sb.get('status')}")
                    else:
                        msg = sb.get("mensaje") or "Error desconocido al insertar en Supabase"
                        st.error(msg)
                        with st.expander("Detalle del error Supabase"):
                            st.write(f"Configurado: {sb.get('configurado')}")
                            st.write(f"HTTP status: {sb.get('status')}")
                            st.write(f"Endpoint: {sb.get('endpoint')}")
                            st.json(sb.get("payload") or {})
                except Exception as e:
                    st.error(e)
            except Exception as e:
                llave_publica = "LLAVE_NO_DISPONIBLE"
                sello_digital = "SELLO_NO_DISPONIBLE"
                st.error(f"No se pudo generar el sello criptográfico: {e}")
                st.caption(f"Diagnóstico: {motor_planta.diagnostico()}")

            st.subheader("Observaciones de turno, edición y cierre")
            col_bus1, col_bus2, col_bus3 = st.columns(3)
            with col_bus1:
                texto_busqueda = st.text_input("🔍 Búsqueda Global (Lote/Contenedor):")
            with col_bus2:
                if col_prod_chk:
                    lista_prod = ["TODOS"] + list(df_original[col_prod_chk[0]].unique())
                    prod_filtro_sel = st.selectbox("🎯 Filtrar por Productor:", lista_prod)
                else:
                    prod_filtro_sel = "TODOS"
            with col_bus3:
                turno_sel = st.selectbox("🕒 Filtrar por Turno de Trabajo:", ["TODOS", "Mañana (06:00 - 14:00)", "Tarde (14:00 - 22:00)", "Noche (22:00 - 06:00)"])

            df_mostrar = df_export
            if texto_busqueda.strip() != "":
                mask_busq = df_mostrar.astype(str).apply(
                    lambda row: row.str.contains(texto_busqueda, case=False, na=False).any(),
                    axis=1,
                )
                df_mostrar = df_mostrar[mask_busq]

            if col_prod_chk and prod_filtro_sel != "TODOS":
                mask_prod = df_original[col_prod_chk[0]] == prod_filtro_sel
                indices_validos = df_original[mask_prod].index
                df_mostrar = df_mostrar.loc[df_mostrar.index.isin(indices_validos)]

            TAMANO_PAGINA = 100
            total_registros_visibles = len(df_mostrar)
        
            if total_registros_visibles > TAMANO_PAGINA:
                total_paginas = (total_registros_visibles // TAMANO_PAGINA) + (1 if total_registros_visibles % TAMANO_PAGINA > 0 else 0)
                pagina_actual = st.number_input("Página de visualización:", min_value=1, max_value=total_paginas, step=1)
                inicio = (pagina_actual - 1) * TAMANO_PAGINA
                fin = inicio + TAMANO_PAGINA
                df_paginado = df_mostrar.iloc[inicio:fin]
                st.caption(f"Mostrando registros {inicio + 1} al {min(fin, total_registros_visibles)} de un total de {total_registros_visibles} filtrados.")
            else:
                df_paginado = df_mostrar

            if st.session_state["lote_congelado"]:
                st.warning("🔒 **Lote Congelado:** La tabla está en modo solo lectura. Para editar, desbloquee el lote abajo.")
                df_editado = df_mostrar
            else:
                df_editado_pag = st.data_editor(df_paginado, use_container_width=True, key="editor_datos_pag")
            
                df_editado = df_mostrar.copy()
                if total_registros_visibles > TAMANO_PAGINA:
                    df_editado.iloc[inicio:fin] = df_editado_pag
                else:
                    df_editado = df_editado_pag

                def _valores_iguales(valor_original, valor_nuevo):
                    if pd.isna(valor_original) and pd.isna(valor_nuevo):
                        return True
                    return str(valor_original).strip() == str(valor_nuevo).strip()

                for i in range(len(df_mostrar)):
                    fila_indice = df_mostrar.index[i]
                    for col in df_mostrar.columns:
                        val_orig = df_mostrar.iloc[i][col]
                        val_nuevo = df_editado.iloc[i][col]
                        if not _valores_iguales(val_orig, val_nuevo):
                            fecha_hora_cambio = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            funciones.guardar_cambio_db(
                                fecha_hora_cambio,
                                int(fila_indice) if isinstance(fila_indice, (int, float)) and not pd.isna(fila_indice) else i,
                                col,
                                val_orig,
                                val_nuevo,
                                auditor_nombre,
                            )

            st.markdown("#### ✅ Verificaciones Fitosanitarias Obligatorias")
            chk_pulpa = st.checkbox("Se verificó la temperatura de pulpa y los límites máximos de residuos (LMR).")
            chk_cuerpo = st.checkbox("El lote se encuentra libre de materias extrañas y plagas cuarentenarias exigidas por SENASA.")
        
            capa_texto = st.text_area("📝 Registro General de Acciones Correctivas (CAPA) / Resumen de Incidencias:", placeholder="Escribir observaciones generales de turno...")

            col_c1, col_c2 = st.columns(2)
            with col_c1:
                if not st.session_state["lote_congelado"]:
                    if _es_supervisor:
                        if st.button("🔒 Congelar y Aprobar Lote (Cierre Oficial)"):
                            if chk_pulpa and chk_cuerpo:
                                st.session_state["lote_congelado"] = True
                                st.success("¡Lote aprobado, firmado y congelado correctamente para gerencia!")
                                st.rerun()
                            else:
                                st.error("⚠️ Debe marcar todas las verificaciones del checklist obligatorio antes de aprobar el lote.")
                    else:
                        st.caption("Congelar/aprobar: solo supervisor.")
                else:
                    if _es_supervisor:
                        if st.button("🔓 Descongelar Lote (Habilitar Edición)"):
                            st.session_state["lote_congelado"] = False
                            st.warning("Lote habilitado para modificaciones.")
                            st.rerun()
                    else:
                        st.caption("Lote congelado. Solo un supervisor puede descongelarlo.")

            bitacora_db_data = funciones.cargar_bitacora_db()
            if bitacora_db_data:
                with st.expander("📜 Ver Bitácora de Auditoría Persistente (SQLite Audit Trail)"):
                    st.dataframe(pd.DataFrame(bitacora_db_data), use_container_width=True)

            st.markdown("### 5️⃣ Exportación de Reportes Oficiales")
            col_ex1, col_ex2, col_ex3 = st.columns(3)

            with col_ex1:
                estado_lote = "CONGELADO / APROBADO" if st.session_state["lote_congelado"] else "EN REVISIÓN"
                df_resumen = pd.DataFrame({
                    "Parámetro de Control": [
                        "Fecha de Emisión",
                        "Cultivo Procesado",
                        "Mercado Destino",
                        "Total Registros Exportados",
                        "Errores Iniciales Detectados",
                        "Confiabilidad del Proceso",
                        "Estado del Lote",
                        "Inspector Responsable",
                        "Planta",
                    ],
                    "Detalle": [
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        producto_sel,
                        mercado_destino,
                        total_filas,
                        total_errores,
                        f"{porcentaje_limpio}%",
                        estado_lote,
                        auditor_nombre,
                        nombre_planta or "Planta Autorizada",
                    ],
                })
                hojas_excel = {
                    "Packing_List": (
                        df_editado,
                        f"Packing List — {nombre_planta or 'Planta Autorizada'} | {producto_sel}",
                    ),
                    "Trazabilidad_Resumen": (
                        df_resumen,
                        f"Resumen de Trazabilidad — {archivo.name}",
                    ),
                }
                if bitacora_db_data:
                    hojas_excel["Audit_Trail"] = (
                        pd.DataFrame(bitacora_db_data),
                        "Bitácora de Auditoría (Audit Trail)",
                    )

                buffer_completo = funciones.generar_excel_corporativo(
                    hojas_excel,
                    titulo_general="Reporte Corporativo de Exportación",
                )
                st.download_button(
                    label="📥 Descargar Excel corporativo",
                    data=buffer_completo.getvalue(),
                    file_name="Reporte_Completo_Exportacion.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            with col_ex2:
                pdf_buffer = funciones.generar_pdf_resumen(
                    archivo.name,
                    total_filas,
                    total_errores,
                    total_duplicados,
                    porcentaje_limpio,
                    producto_sel,
                    auditor_nombre,
                    st.session_state["lote_congelado"],
                    mercado_destino,
                    capa_texto,
                    sello_digital,
                    llave_publica,
                    mensaje_firmado=resumen_datos,
                    planta_nombre=nombre_planta,
                )
                st.download_button(
                    label="📄 Descargar PDF Ejecutivo Firmado",
                    data=pdf_buffer.getvalue(),
                    file_name="Resumen_Ejecutivo_Firmado_ECC.pdf",
                    mime="application/pdf",
                )

            with col_ex3:
                buffer_packing = io.BytesIO()
                df_editado.to_csv(buffer_packing, index=False)
                st.download_button(
                    label="🚢 Descargar Packing List (CSV)",
                    data=buffer_packing.getvalue(),
                    file_name="Packing_List_Oficial.csv",
                    mime="text/csv",
                )

    except Exception as e:
        st.error(f"Ocurrió un error al procesar el archivo: {e}")