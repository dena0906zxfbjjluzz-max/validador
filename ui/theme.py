"""Tema visual Cadena de Frío / Supabase-like."""
import streamlit as st


def apply_theme() -> None:
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
