# Validador de planta (v1)

App Streamlit de control de calidad, trazabilidad y packing (Perú).  
Sello Ed25519 · SQLite · Supabase opcional.

---

## Instalar y correr

### 1. Código

```bash
git clone https://github.com/dena0906zxfbjjluzz-max/validador.git
cd validador
```

### 2. Python

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**WSL / Ubuntu** (cámara QR):

```bash
sudo apt-get update && sudo apt-get install -y libzbar0
```

### 3. Secrets

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edite `.streamlit/secrets.toml` (no se sube a Git):

| Campo | Uso |
|--------|-----|
| `usuario` / `clave` | Login de planta |
| `LLAVE_PRIVADA` | Hex de **64** caracteres (firma real Ed25519) |
| `nombre_planta` | Nombre en la app / PDF |
| `SUPABASE_URL` / `SUPABASE_KEY` | Opcional (sin esto: solo SQLite local) |

Generar llave de prueba:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Supabase (opcional)

En el SQL Editor de su proyecto, ejecute: [`supabase/schema.sql`](supabase/schema.sql).  
Copie URL y API key a secrets.

### 5. Iniciar

```bash
streamlit run app.py
```

Abra la URL local (p. ej. `http://localhost:8501`).

### 6. Probar

1. Inicie sesión con su usuario/clave.  
2. Cargue [`demo/packing_demo.csv`](demo/packing_demo.csv).  
3. Use los módulos 1–6 según la pantalla.

### Streamlit Cloud

App → `app.py` del repo → **Secrets** con el mismo TOML de `[credenciales]`.  
`packages.txt` instala `libzbar0` y Rust en Cloud.

---

## Archivos útiles

| Archivo | Para qué |
|---------|----------|
| [demo/packing_demo.csv](demo/packing_demo.csv) | Excel/CSV de prueba |
| [supabase/schema.sql](supabase/schema.sql) | Tablas en la nube |
| [.streamlit/secrets.toml.example](.streamlit/secrets.toml.example) | Plantilla de secrets |
| [INSTALACION.md](INSTALACION.md) | Guía extendida (si la necesita) |
| [ENTREGA.md](ENTREGA.md) | Checklist de entrega técnica |

**No va en Git:** `secrets.toml` real, `*.db`, `.venv/`.

---

## Módulos (resumen)

1 Balanza/SSCC · 2 LMR · 3 Trazabilidad · 4 Frío · 5 Contenedores · 6 QR pallet · sello ECC · cortafuego · export PDF/Excel/CSV.

v1 lista para uso / entrega de código.
