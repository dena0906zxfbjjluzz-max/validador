# Validador de planta — Control de calidad, trazabilidad y packing (v1)

Suite AgTech de piso de empaque para packing agroexport:

- **Python + Streamlit** (interfaz de planta)
- **Sello Ed25519** (Rust `motor_rust` o fallback Python)
- **SQLite** local + **Supabase** opcional (nube)

**Estado:** producto **v1 cerrado** (listo para demo, deploy o venta de código).

| Documento | Contenido |
|-----------|-----------|
| Este **README** | Visión general + **instalación completa** |
| [ENTREGA.md](ENTREGA.md) | Checklist al entregar / vender |
| [supabase/schema.sql](supabase/schema.sql) | Tablas para Supabase |
| [demo/packing_demo.csv](demo/packing_demo.csv) | Archivo de prueba packing |
| [.streamlit/secrets.toml.example](.streamlit/secrets.toml.example) | Plantilla de contraseñas |

También: [INSTALACION.md](INSTALACION.md) (misma guía en archivo aparte).

---

## Módulos de la app

| # | Módulo | Qué hace |
|---|--------|----------|
| 1 | Balanza y SSCC | Peso en última fila PESO + búsqueda de código SSCC/caja/pallet/lote |
| 2 | LMR / SENASA | Veredicto de laboratorio o columna LMR del archivo |
| 3 | Trazabilidad inversa | De caja/pallet → fundo, productor, lote, turno |
| 4 | Cadena de frío | Lecturas cámara/túnel/reefer + alertas de rango (SQLite / Supabase) |
| 5 | Contenedores | Booking, ISO 6346, precintos, QR (SQLite / Supabase) |
| 6 | QR pallet | Cámara / foto / texto → validar hash en `historial_reportes` |
| — | Cortafuego | Login, bloqueo, sesión, validación uploads, bitácora |
| — | ECC | Firma de reportes + **Verificación pública de PDF** (sin login de planta) |
| — | Export | PDF ejecutivo, Excel corporativo, Packing List CSV |

**Panel derecho (atajos):** Base de datos · Historial de sellos · Seguridad · Criptografía.

---

## Instalación completa (local / WSL)

### 1. Requisitos

- **Python 3.10+** (recomendado 3.11)
- Git
- (Linux/WSL) paquete `libzbar0` para leer QR
- (Opcional) cuenta [Streamlit Cloud](https://streamlit.io/cloud)
- (Opcional) proyecto [Supabase](https://supabase.com)

### 2. Descargar el código

```bash
git clone https://github.com/dena0906zxfbjjluzz-max/validador.git
cd validador
```

O en GitHub: **Code → Download ZIP** y descomprimir.

### 3. Entorno virtual e instalar librerías

```bash
python -m venv .venv
```

- **Linux / macOS / WSL:** `source .venv/bin/activate`
- **Windows:** `.venv\Scripts\activate`

```bash
pip install -r requirements.txt
```

**QR en Linux/WSL:**

```bash
sudo apt-get update
sudo apt-get install -y libzbar0
```

Lista Python: [`requirements.txt`](requirements.txt)  
Paquetes de sistema (Cloud): [`packages.txt`](packages.txt) (`libzbar0`, Rust, etc.)

### 4. Secrets (login + firma real) — obligatorio

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edite `.streamlit/secrets.toml` (este archivo **no** se sube a Git):

```toml
[credenciales]
usuario = "su_usuario"
clave = "su_clave_secreta"
LLAVE_PRIVADA = "pegue_aqui_hex_de_64_caracteres"
nombre_planta = "Planta Autorizada"
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_KEY = "eyJhbGciOi..."
```

| Clave | Para qué |
|--------|----------|
| `usuario` / `clave` | Entrar a la app de planta |
| `LLAVE_PRIVADA` | Sello Ed25519 real (64 hex = 32 bytes) |
| `nombre_planta` | Nombre en pantallas y PDF |
| `SUPABASE_URL` / `SUPABASE_KEY` | Nube (si los deja vacíos, solo SQLite local) |

**Generar una `LLAVE_PRIVADA` de prueba:**

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Supabase (opcional pero recomendado)

1. Cree un proyecto en [supabase.com](https://supabase.com).
2. Vaya a **SQL Editor** → New query.
3. Pegue todo el contenido de [`supabase/schema.sql`](supabase/schema.sql) → **Run**.
4. **Project Settings → API**: copie
   - Project URL → `SUPABASE_URL`
   - `service_role` (o `anon` con policies) → `SUPABASE_KEY`
5. Guarde en `secrets.toml`.

Tablas que crea el SQL:

- `public.historial_reportes` — sellos / QR (`fecha`, `lote`, `hash_sha256`, `inspector`)
- `public.control_frio` — lecturas de temperatura
- `public.contenedores_despacho` — booking / contenedor / precintos

Sin Supabase la app **funciona igual** con el archivo local `planta_calidad_prod.db` (se crea solo).

### 6. Arrancar la aplicación

```bash
streamlit run app.py
```

Abra en el navegador la URL que salga (normalmente `http://localhost:8501`).

### 7. Primera prueba (demo)

1. Login con el `usuario` y `clave` de secrets.
2. Cargue el archivo de demo:
   - [demo/packing_demo.csv](demo/packing_demo.csv)
   - o [demo/packing_demo.xlsx](demo/packing_demo.xlsx)
3. Pruebe:
   - **Módulo 1:** peso / buscar SSCC `077512345678901234`
   - **Módulo 2:** lote `L-DEMO-001` / LMR
   - **Módulo 3:** caja `CJ-001`
   - **Módulo 4:** registrar temperatura
   - **Módulo 5:** booking + contenedor (panel superior)
4. Genere reporte / sello ECC; panel derecho → **Criptografía** (debería decir modo **real** si la llave es correcta).
5. Barra lateral → **Verificación pública ECC** (sin login de planta) con un PDF firmado.

---

## Publicar en Streamlit Cloud

1. Suba (o use) el repo en GitHub.
2. [share.streamlit.io](https://share.streamlit.io) → **New app** → elija el repo → archivo `app.py`.
3. **Settings → Secrets** → pegue el TOML de `[credenciales]` (igual que en local).
4. Cloud instalará `requirements.txt` y `packages.txt` solo.
5. Deploy y abra la URL pública.

---

## Qué sí viene en Git / qué no

| Sí en el repositorio | No en el repositorio (normal) |
|----------------------|-------------------------------|
| Código (`app.py`, `funciones.py`, …) | `.streamlit/secrets.toml` (contraseñas) |
| Guía y demo | `planta_calidad_prod.db` (datos locales) |
| `secrets.toml.example` | Carpeta `.venv/` |
| SQL Supabase | `motor_rust/target/` (build compilado) |

---

## Alcance v1 (honesto para venta)

| Incluido | No incluido en v1 |
|----------|-------------------|
| App completa + PDF / Excel / CSV | Conector nativo SAP / Oracle |
| SQLite + Supabase opcional | Balanza por puerto serial industrial lista para enchufar |
| Código fuente + GitHub | Secretos y base del vendedor |
| Instalar y demo documentados | Capacitación / soporte 24×7 sin contrato |

CSV limpio exportable para cargar en ERP a mano o con un integrador.

**Referencia de precio venta código (Perú):** ver [ENTREGA.md](ENTREGA.md).

---

## Checklist rápido de “ya quedó instalado”

- [ ] `pip install -r requirements.txt` OK  
- [ ] `secrets.toml` con usuario, clave, `LLAVE_PRIVADA`  
- [ ] `streamlit run app.py` abre login  
- [ ] Login OK  
- [ ] Demo CSV carga  
- [ ] Panel Criptografía en **real** (con llave)  
- [ ] (Opcional) Supabase SQL + URL/KEY  

Checklist formal de entrega: **[ENTREGA.md](ENTREGA.md)**.

---

## Estructura del proyecto

```text
validador/
├── app.py                 # Interfaz Streamlit
├── funciones.py           # SQLite, Supabase, PDF, Excel, QR, frío, contenedores
├── motor_planta.py        # Firma / verificación Ed25519
├── seguridad_cortafuego.py
├── motor_rust/            # Extensión Rust (opcional al compilar)
├── demo/                  # packing de prueba
├── supabase/schema.sql    # tablas nube
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── requirements.txt
├── packages.txt
├── README.md              # este archivo
├── INSTALACION.md
└── ENTREGA.md
```

---

## Soporte

Issues del repo o contacto del vendedor/instalador según contrato de entrega.
