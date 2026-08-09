# 🏭 Plataforma Corporativa de Control de Calidad, Trazabilidad y Gestión de Planta (Perú)

¡Bienvenido! Esta es una suite tecnológica e industrial avanzada (AgTech ERP) diseñada a medida para optimizar, auditar y blindar los procesos operativos y logísticos en plantas de empaque (Packing) agroindustrial de exportación.

La plataforma cuenta con una arquitectura híbrida de alto rendimiento que combina la flexibilidad de Python (Streamlit) para la interfaz y gestión de datos, con la velocidad y seguridad matemática de un motor criptográfico nativo en Rust.

## 🚀 Módulos Operativos Integrados

### 🔌 Módulo 1: Conexión de Balanza y Lectura Rápida de Pallets (SSCC)
* **Captura Automatizada:** Conexión en línea con balanzas industriales (vía puerto Serial/USB) para el registro automatizado de peso neto en plataforma, eliminando el error humano por digitación.
* **Estándar Global GS1:** Escaneo e identificación de unidades logísticas de exportación mediante la lectura de códigos GS1-128 / SSCC para un rastreo preciso en almacén.

### 🧪 Módulo 2: Control de Límites Máximos de Residuos (LMR) y Certificación SENASA
* **Seguridad Alimentaria:** Filtro inteligente de consulta de Límites Máximos de Residuos (LMR) de pesticidas y agroquímicos según las exigencias de mercados internacionales.
* **Validación Fitosanitaria:** Sistema integrado de aprobación digital amarrado a las normativas vigentes de SENASA para autorizar el lote de embarque (Destino Aprobado).

### 🗺️ Módulo 3: Trazabilidad Inversa (De Caja o Pallet al Fundo de Origen)
* **Escudo Legal:** Herramienta de auditoría inversa instantánea. Permite ingresar el ID de cualquier caja o pallet observado en el extranjero para rastrear en segundos su turno de empaque, lote de proceso y la parcela o fundo de campo de origen.

### 🌡️ Módulo 4: Control Térmico de Cadena de Frío
* **Preservación de Vida Útil:** Monitoreo, registro automático y alertas visuales de las temperaturas en túneles de pre-frío y cámaras frigoríficas, garantizando rangos óptimos de conservación (5.0°C) para el transporte marítimo de larga distancia.

### 🚢 Módulo 5: Gestión de Contenedores, Bookings y Precintos de Aduanas
* **Resguardo Logístico Antifraude:** Centralización y control estricto de números de Booking, identificadores de contenedores Reefer y sellado digital de los precintos oficiales de la Línea Naviera y SENASA, blindando el despacho en puerto.

### 📷 Módulo 6: Escaneo QR del Pallet (Supabase)
* **Cámara del inspector:** `st.camera_input` activa webcam o cámara del celular.
* **Decodificación:** `pyzbar` + Pillow extraen el texto del QR (JSON, hash SHA-256 o `lote|hash`).
* **Validación en la nube:** consulta automática a `public.historial_reportes` (lote / `hash_sha256`).
* **Resultado:** ✅ pallet verificado si el hash está registrado; 🚨 alerta si no coincide.

### 🛡️ Cortafuego de seguridad (aplicación)
* **Login endurecido:** comparación de secretos en tiempo constante, bloqueo tras intentos fallidos.
* **Sesión protegida:** token aleatorio + timeout por inactividad + cierre de sesión seguro.
* **Validación de entrada:** archivos (extensión / tamaño) y textos operativos (QR / SSCC / lote).
* **Bitácora:** eventos `LOGIN_OK`, `LOGIN_FAIL`, `LOGIN_LOCKOUT`, `UPLOAD_*` en SQLite `bitacora_seguridad`.
* **Streamlit:** XSRF ON, CORS restringido, límite de upload en `.streamlit/config.toml`.

## 🛡️ Diferenciadores Tecnológicos Avanzados

### ⚡ Motor Criptográfico Ed25519 (Real + Demo)
Cada cierre oficial de lote se sella con Ed25519 (`ed25519-dalek` en Rust), generando firma digital (64 bytes) y llave pública (32 bytes) en hexadecimal.
* **Modo Real + Rust:** Lee `st.secrets["LLAVE_PRIVADA"]` (seed de 32 bytes / 64 hex) y firma con `motor_rust`.
* **Respaldo Python (Multi-Capa):** `cryptography` (Ed25519) → `PyNaCl` → paquete `ed25519` si existe.

### 🔎 Verificación Pública de PDF
En la barra lateral: Verificación pública ECC (sin login). Un tercero sube el PDF ejecutivo y la app comprueba la firma Ed25519:
* **AUTÉNTICO:** Firma válida + llave oficial de planta.
* **ALTERADO:** La firma no corresponde al mensaje (documento manipulado).

### 📂 Historial permanente de reportes (SQLite + Supabase)
* Cada sello exitoso se archiva en SQLite local y **se envía en automático a Supabase** vía REST HTTP.
* Campos remotos: **fecha**, **lote**, **hash_sha256**, **inspector**.
* Secrets: `SUPABASE_URL` + `SUPABASE_KEY` → tabla PostgREST `historial_reportes`.

### 💼 Interoperabilidad Universal ERP (SAP / Oracle)
El sistema incluye un algoritmo de limpieza y auditoría que corrige caracteres corruptos, elimina espacios invisibles y parcha celdas vacías de forma masiva en milisegundos. Permite la exportación directa en formato plano universal (CSV Puro) optimizado para la inyección masiva de datos limpios directamente en los módulos logísticos de ERPs corporativos sin bloqueos de formato.
