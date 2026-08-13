# Instalación y puesta en marcha — Validador de planta

Paquete listo para **cerrar entrega**: código + GitHub + esta guía.  
No incluye contraseñas de producción del autor (cada operador usa las suyas).

---

## 1. Requisitos

- Python 3.10+ (recomendado 3.11)
- Cuenta [Streamlit Community Cloud](https://streamlit.io/cloud) **o** PC/servidor local
- (Opcional) Proyecto [Supabase](https://supabase.com) gratuito/pago
- (Opcional) `rustc` + `cargo` si se compila `motor_rust` (Streamlit Cloud usa `packages.txt`)

---

## 2. Obtener el código

```bash
git clone https://github.com/dena0906zxfbjjluzz-max/validador.git
cd validador
```

O descargar ZIP del repositorio en GitHub → **Code → Download ZIP**.

El entrypoint sigue siendo **`app.py`**. La UI está en `ui/` y la lógica en `planta/` (`funciones.py` solo reexporta).

---

## 3. Dependencias (local)

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

pip install -r requirements.txt
```

Linux (zbar para QR):

```bash
# Debian/Ubuntu / WSL
sudo apt-get update && sudo apt-get install -y libzbar0
```

En Streamlit Cloud, `packages.txt` instala `libzbar0` y herramientas Rust automáticamente.

---

## 4. Secrets (obligatorio para login y firma real)

1. Copie el ejemplo:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

2. Edite `.streamlit/secrets.toml` (nunca lo suba a Git):

| Clave | Uso |
|--------|-----|
| `usuario` / `clave` | Login de planta |
| `LLAVE_PRIVADA` | Seed Ed25519: **64 caracteres hex** (32 bytes) |
| `nombre_planta` | Nombre en PDF / hero |
| `SUPABASE_URL` / `SUPABASE_KEY` | Nube (opcional; sin esto solo SQLite local) |

### Generar una llave privada de demo (hex 64)

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Guarde el valor en `LLAVE_PRIVADA`.

### Streamlit Cloud

**App settings → Secrets** → pegue el contenido TOML igual que el ejemplo (sección `[credenciales]`).

---

## 5. Supabase (opcional, recomendado)

1. Cree un proyecto en Supabase.
2. **SQL Editor** → pegue y ejecute: [`supabase/schema.sql`](supabase/schema.sql).
3. **Settings → API**: copie URL y `service_role` (o `anon` con policies) a secrets.
4. Tablas esperadas por la app:
   - `public.historial_reportes` → columnas: `fecha`, `lote`, `hash_sha256`, `inspector`
   - `public.control_frio`
   - `public.contenedores_despacho`

Sin Supabase la app **sigue funcionando** con SQLite `planta_calidad_prod.db` local.

---

## 6. Arrancar

```bash
streamlit run app.py
```

Abra el navegador en la URL que muestre la terminal (suele ser `http://localhost:8501`).

### Primera operación de prueba

1. Login con `usuario` / `clave` de secrets (`rol = "supervisor"` o cuenta `[credenciales_operario]`).
2. Cargue [`demo/packing_demo.csv`](demo/packing_demo.csv).
3. Si faltan LOTE/PESO/CALIBRE: **Mapear columnas del packing** en Resumen.
4. Pruebe módulos (peso / LMR / caja / frío). Congelar lote solo con rol supervisor.
5. Sello ECC al generar reporte; **Verificación pública ECC** con un PDF firmado.
6. **Dashboard** → KPIs + PDF firmado; **Historial** para frío/sellos/bitácora.
7. Modo sidebar **Móvil · QR + frío** para piso.
8. Congelar lote (supervisor) → descarga **CSV ERP**.

### Tests locales

```bash
pytest tests/test_smoke.py -q
```

### Roles (opcional)

- `[credenciales]` con `rol = "supervisor"` (por defecto).
- `[credenciales_operario]` para línea: puede operar el lote, no congelar/descongelar ni reenviar avisos.
- Alternativa: lista `[[usuarios]]` (ver `.streamlit/secrets.toml.example`).

### Avisos correo (WhatsApp opcional / otro día)

En Streamlit Secrets agregue bloque `[avisos]` (ver `.streamlit/secrets.toml.example`):

- **Email:** `email_to`, `smtp_host`, `smtp_user`, `smtp_pass` (Gmail: contraseña de aplicación).
- **WhatsApp:** `whatsapp_to` + `callmebot_apikey` (CallMeBot) **o** Twilio — configurar cuando lo necesite.

Al registrar una **ruptura de frío**, el Validador intenta avisar (máx. 1 aviso / cámara / 30 min).

---

## 7. Qué no viene en el Git (normal)

| No incluido | Motivo |
|-------------|--------|
| `.streamlit/secrets.toml` | Secretos de cada cliente |
| `*.db` | Datos locales de operación |
| `.venv/` | Entorno Python del desarrollador |

---

## 8. Alcance del producto v1 (cierre)

**Incluye:** módulos 1–6, packing/export PDF-Excel-CSV, sello Ed25519, cortafuego, SQLite + Supabase opcional.

**No incluye como conector nativo:** SAP OData/BAPI ni Oracle ORDS (se exporta CSV limpio para importar).  
**Balanza:** registro de peso en archivo (integración serial industrial es personalización adicional).

---

## 9. Soporte de entrega rápida

Checklist formal: [`ENTREGA.md`](ENTREGA.md).
