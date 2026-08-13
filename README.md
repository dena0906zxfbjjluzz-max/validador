# 🏭 Validador de planta — Control de calidad, trazabilidad y packing (v1)

Suite AgTech de piso de empaque: Python (Streamlit) + sello Ed25519 (Rust/Python) + SQLite y Supabase opcional.

## Estructura del código

| Ruta | Rol |
|------|-----|
| `app.py` | Entrypoint Streamlit (`streamlit run app.py`) |
| `ui/` | Pantallas, tema, login y navegación |
| `planta/` | Lógica de negocio (DB, frío, QR, PDF, avisos, M7) |
| `funciones.py` | Fachada: reexporta `planta/` (compat `import funciones`) |
| `motor_planta.py` / `seguridad_cortafuego.py` | Firma Ed25519 y cortafuego |

**Estado:** producto **v1 cerrado** para entrega / uso / venta de código.  
**Instalación:** [INSTALACION.md](INSTALACION.md) · **Manual de uso (operarios):** [MANUAL.md](MANUAL.md) · acta de entrega [ENTREGA.md](ENTREGA.md) · plantilla de venta [CONTRATO_TRASPASO.md](CONTRATO_TRASPASO.md).

## Módulos

### 1 · Balanza y SSCC
Registro de peso en la última fila PESO y búsqueda de SSCC/caja/pallet/lote en el archivo cargado.

### 2 · LMR / SENASA
Consulta de lote y veredicto de laboratorio / columna LMR del archivo.

### 3 · Trazabilidad inversa
De caja o pallet al fundo, productor, lote y turno (columnas detectadas del Excel/CSV).

### 4 · Cadena de frío
Lecturas de cámara/túnel/reefer con rangos por fruta; SQLite + Supabase `control_frio`.

### 5 · Contenedores y precintos
QR/booking/ISO 6346, formulario de sello, SQLite + Supabase `contenedores_despacho`.

### 6 · QR pallet
Cámara / foto / texto → consulta `historial_reportes` en Supabase.

### 7 · Alertas y tendencias
Inteligencia operativa de planta: reglas + z-score sobre cadena de frío (SQLite) y el packing cargado (pesos atípicos, LMR por productor, merma). Anticipa rupturas y patrones de riesgo sin modelos externos.

### Dashboard de turno
KPIs del día (sellos ECC, lecturas/rupturas de frío, contenedores, cargas), **alertas de frío activas** y **PDF del turno**.

### Mapeo de columnas y roles
Si el Excel no trae LOTE/PESO/CALIBRE con esos nombres, se mapean en Resumen. Roles `supervisor` / `operario` en secrets (congelar lote solo supervisor).

### Avisos email (WhatsApp opcional)
Opcional vía secrets `[avisos]`: al registrar ruptura de frío se notifica por correo SMTP; WhatsApp (CallMeBot/Twilio) cuando lo configure.

### Seguridad (cortafuego)
Login con bloqueo, token de sesión, timeout, validación de uploads y bitácora local.

### Sello Ed25519
Firma de reportes con `LLAVE_PRIVADA` (secrets). Verificación pública de PDF sin login de planta.

## Demo

Archivo de prueba: [demo/packing_demo.csv](demo/packing_demo.csv) · [demo/packing_demo.xlsx](demo/packing_demo.xlsx)

## Supabase

Ejecutar [supabase/schema.sql](supabase/schema.sql) en el SQL Editor del proyecto.

## Secrets

Plantilla: [.streamlit/secrets.toml.example](.streamlit/secrets.toml.example)

## Alcance v1

| Incluido | No incluido en v1 |
|----------|-------------------|
| App completa de planta + PDF/CSV/Excel | Conector nativo SAP/Oracle |
| Nube Supabase opcional | Balanza industrial por puerto serial plug-and-play |
| Código en Git + guía de instalación | Secretos y base de datos del vendedor |

Export CSV limpio usable para cargar en ERPs de forma manual o con integrador.

## Arranque rápido

```bash
git clone https://github.com/dena0906zxfbjjluzz-max/validador.git
cd validador
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# editar secrets.toml
streamlit run app.py
```

Detalle de instalación, secrets y Supabase: **[INSTALACION.md](INSTALACION.md)**.  
Checklist de entrega: **[ENTREGA.md](ENTREGA.md)**.
