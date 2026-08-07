# 🏭 Plataforma Corporativa de Control de Calidad, Trazabilidad y Gestión de Planta (Perú)

¡Bienvenido! Esta es una suite tecnológica e industrial avanzada (AgTech ERP) diseñada a medida para optimizar, auditar y blindar los procesos operativos y logísticos en plantas de empaque (Packing) agroindustrial de exportación.

La plataforma cuenta con una arquitectura híbrida de alto rendimiento que combina la flexibilidad de **Python (Streamlit)** para la interfaz y gestión de datos, con la velocidad y seguridad matemática de un motor criptográfico nativo en **Rust**.

---

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

---

## 🛡️ Diferenciadores Tecnológicos Avanzados

### ⚡ Motor Criptográfico ECC P-256 (real + demo)
Cada cierre oficial de lote se sella con **ECDSA sobre curva P-256**, generando **firma digital** y **llave pública** en hexadecimal.

* **Modo real + Rust:** lee exactamente `st.secrets["LLAVE_PRIVADA"]` y firma con `motor_rust` (compilación vía Maturin en Cloud).
* **Respaldo:** si Rust no carga, firma igual con esa llave usando `cryptography`.
* **Modo demo:** sin secret → llave efímera.
* En Cloud, Secrets debe quedar así (con comillas):

```toml
LLAVE_PRIVADA = "3d3c988092632e2e4ecfbf60989822344ef0168166f6ea84282441a780b1f3c0"
```

Tras cambiar Secrets o el código: **Reboot** de la app. La UI muestra un diagnóstico si el secret no se encuentra.

### 💼 Interoperabilidad Universal ERP (SAP / Oracle)
El sistema incluye un algoritmo de limpieza y auditoría que corrige caracteres corruptos, elimina espacios invisibles y parcha celdas vacías de forma masiva en milisegundos. Permite la exportación directa en formato plano universal **(CSV Puro)** optimizado para la inyección masiva de datos limpios directamente en los módulos logísticos de ERPs corporativos sin bloqueos de formato.

---

## 🛠️ Arquitectura del Proyecto

El repositorio sigue un patrón de diseño limpio y modular:
* `app.py`: Control central y orquestación de la interfaz gráfica interactiva del usuario (UI).
* `funciones.py`: Biblioteca de lógica de negocio, manipulación de datos con Pandas, formateo visual múltiple con Openpyxl y renderizado de reportes ejecutivos en PDF mediante ReportLab.
* `motor_rust/`: Código fuente nativo en Rust encargado del procesamiento de criptografía asimétrica y firmado asíncrono.
* `requirements.txt` & `packages.txt`: Declaración estricta de dependencias y compiladores a nivel de sistema operativo para su despliegue en la nube.
