# Manual de uso — Validador de planta

Guía sencilla para el personal de **control de calidad, packing y trazabilidad**.  
(No es la guía técnica de instalación: eso está en `INSTALACION.md`.)

---

## ¿Para qué sirve?

Es la **suite de planta** para:

- Validar y limpiar archivos de packing / exportación  
- Registrar peso, frío, contenedores y precintos  
- Hacer **trazabilidad inversa** (de caja/pallet al fundo y lote)  
- Emitir **reportes Excel y PDF firmados** (sello Ed25519)  
- Consultar historial en la nube (Supabase), si está conectada  
- Verificar desde afuera que un PDF **no fue alterado** (sin login de planta)

---

## Dos modos de la aplicación

En el menú de la izquierda elija:

| Modo | ¿Quién lo usa? | ¿Pide usuario? |
|------|----------------|----------------|
| **Planta / Packing (login)** | Personal de planta (calidad, packing) | **Sí** |
| **Verificación pública ECC** | Cliente, auditor o inspector externo | **No** |

### Navegación dentro de Planta

Tras el login, use los **botones de Navegación** en la barra lateral (activo = primario):

| Pantalla | Qué hace |
|----------|----------|
| **Inicio** | Atajos 2×2 hacia dashboard, QR, contenedores, alertas y lote |
| **Dashboard** | KPIs del turno + alertas de frío recientes |
| **Operación del lote** | Aparece al cargar Excel/CSV; elija un módulo (Resumen, Balanza, LMR, …) |
| **QR pallet / Contenedores / Alertas** | Pantallas propias |

El archivo se carga desde **Cargar lote**. Al subirlo, la app entra sola a **Operación del lote → Resumen**.

---

## Cómo entrar (modo Planta)

1. Abra el enlace de la app (Streamlit Cloud o local).  
2. Elija **Planta / Packing (login)**.  
3. Escriba su **Usuario** y **Contraseña** (las da el administrador de planta).  
4. Toque **Ingresar**.

### Si no puede entrar

| Qué ve | Qué hacer |
|--------|-----------|
| Credenciales incorrectas | Revise mayúsculas y vuelva a intentar |
| Bloqueo por muchos intentos | Espere o pida al administrador que le habilite de nuevo |
| Error de secrets | La planta debe configurar `usuario` / `clave` en Streamlit Secrets |

### Cerrar sesión

Con sesión abierta, en la barra lateral:

- **Cerrar sesión segura**

Cierre sesión al terminar su turno, sobre todo en PC compartidas.

---

## Flujo típico del día en packing

### 1) Cargar el archivo de packing

1. Entre con su usuario.  
2. Suba el **Excel (.xlsx)** o **CSV** del packing del lote.  
3. Espere a que la app lea filas y muestre el panel de control.

> Archivos de prueba del sistema: carpeta `demo/` (`packing_demo.csv` / `.xlsx`).

### 2) Revisar y limpiar datos

Use las herramientas de limpieza cuando las vea en pantalla, por ejemplo:

- **Limpiar espacios ocultos** — quita caracteres que rompen búsquedas  
- **Rellenar vacíos con (-)** — completa celdas vacías de forma controlada  
- **Ver registros con vacíos** — lista lo que falta revisar  

Revise también:

- Peso / SSCC  
- LMR / SENASA (si aplica al mercado destino)  
- Duplicados o filas raras  

### 3) Módulos operativos (según el turno)

| Módulo | Qué hace en la práctica |
|--------|-------------------------|
| **Balanza y SSCC** | Registra peso en la última fila PESO y busca SSCC / caja / pallet / lote en el archivo |
| **LMR / SENASA** | Consulta veredicto de laboratorio / límites del lote según el archivo |
| **Trazabilidad inversa** | Partiendo de una **caja o pallet**, muestra fundo, productor, lote, turno (según columnas del archivo) |
| **Cadena de frío** | Anota lecturas de cámara / túnel / reefer; guarda local y en nube si está Supabase |
| **Contenedores y precintos** | Formulario de contenedor, booking, precinto (ISO 6346), QR si lo usa la planta |
| **QR pallet** | Cámara o foto del QR → consulta respaldo en historial (Supabase) si está configurado |
| **Alertas y tendencias** | Resume riesgos del frío y del packing (pesos raros, LMR por productor, merma) para anticipar problemas antes de cerrar el lote |

No todos los turnos usan todos los módulos: use el que pida la operación de su planta.

### 4) Congelar (aprobar) el lote

Cuando el lote está **revisado y listo**:

1. Use **Congelar y Aprobar Lote (Cierre Oficial)** si está disponible en pantalla.  
2. Eso marca el cierre oficial (edición restringida).  
3. Solo descongele si un supervisor lo autoriza (**Descongelar Lote**).

### 5) Descargar reportes

Según botones visibles en la pantalla de cierre / descarga:

| Entrega | Para qué |
|---------|----------|
| **Excel corporativo** | Reporte multi-hoja listo para archivo o cliente |
| **PDF ejecutivo firmado** | Resumen con **sello criptográfico Ed25519** (no se debe alterar) |
| **Packing list CSV** | Listado para ERP u otros sistemas (carga manual si aplica) |

Guarde los archivos con el número de lote / fecha en el nombre si su planta lo pide.

---

## Cadena de frío (resumen)

1. Entre al módulo de frío.  
2. Indique tipo (cámara, túnel, reefer, etc.) y lecturas según formulario.  
3. **Registrar lectura de frío**.  
4. Si Supabase está conectado, la lectura también puede ir a la nube (`control_frio`).

Si no hay nube, al menos queda el registro local de la app (SQLite) según cómo esté desplegada.

---

## Alertas y tendencias (Módulo 7)

1. Sin packing: el módulo muestra tendencias de **cadena de frío** desde el historial local.  
2. Con archivo cargado: añade patrones de **peso**, **LMR por productor** y **merma**.  
3. Revise el veredicto (`ESTABLE` / `VIGILANCIA` / `ACCION_REQUERIDA`) antes de congelar el lote.  
4. Use el detalle de alertas y las tablas por cámara / productor para anticipar revisiones.

No reemplaza el criterio del inspector: es un apoyo operativo sobre los datos ya registrados.

---

## Contenedores y precintos (resumen)

1. Complete booking / contenedor / precinto según el formulario.  
2. Use **Buscar contenedor** si ya existe un registro.  
3. Guarde el sello o el despacho.  
4. Si hay cámara, puede usarla para QR y apagarla con el botón **Apagar cámara** cuando termine.

---

## QR / historial de reportes

1. Active la cámara o suba foto del código del pallet.  
2. Valide si el sistema encuentra respaldo en Supabase (`historial_reportes`).  
3. Si no hay conexión a nube, el administrador debe revisar secrets `SUPABASE_URL` y `SUPABASE_KEY`.

---

## Verificación pública ECC (sin login de planta)

Para un cliente, aduana o auditor que solo quiere saber si el **PDF es auténtico**:

1. En el menú elija **Verificación pública ECC**.  
2. **Suba el PDF ejecutivo firmado**.  
3. Toque **Verificar autenticidad ECC**.  

| Resultado | Significado |
|-----------|-------------|
| OK / auténtico | El PDF coincide con la firma matemática de la planta |
| Fallo | El archivo pudo modificarse o no es el original firmado |

Si el PDF no se lee bien, use el expander de **verificación manual** (mensaje, firma y llave pública en hex).

Opcional: **Buscar en historial** con el hash, si la planta conectó el historial en la nube.

---

## Seguridad (lo que debe saber el usuario)

- No comparta usuario ni contraseña.  
- No intente muchas veces una clave incorrecta (puede bloquearse).  
- Cierre sesión al terminar.  
- No reenvíe PDFs editados “a mano”: **rompen** el sello. Si hay error en el contenido, se **emite de nuevo** desde la planta.  
- La `LLAVE_PRIVADA` solo la maneja el administrador en Secrets; **usted no la copia ni la pega** en chats.

---

## En el celular

- Funciona en el navegador (Chrome / Safari).  
- Para QR use preferible **cámara frontal/trasera** con buena luz.  
- Abra el menú lateral con el icono superior izquierdo.  
- Puede fijar el enlace en la pantalla de inicio como acceso rápido.

---

## Problemas frecuentes

| Problema | Qué hacer |
|----------|-----------|
| No carga el Excel | Formato `.xlsx` o `.csv`; archivo no dañado; tamaño razonable |
| No encuentra pallet / SSCC | Revise espacios o tire de “limpiar espacios”; confírme columna en el archivo |
| Supabase no guarda | Avisar a TI: secrets y tablas (`schema.sql` de la carpeta `supabase/`) |
| PDF no verifica | Usar el PDF **original** descargado de la app, no un escaneo o edición |
| Cámara no abre | Permisos del navegador; HTTPS en la nube; cerrar y reabrir la pestaña |
| “Acceso denegado” | Pedir clave al jefe de calidad / admin |

---

## Resumen ultra corto (WhatsApp / pizarra)

```
PLANTA
1. Login con usuario y clave
2. Subir Excel/CSV del packing
3. Limpiar y revisar (peso, LMR, trazabilidad, frío, contenedor…)
4. Congelar lote si todo OK
5. Bajar Excel + PDF firmado
6. Cerrar sesión

AFUERA (cliente / auditor)
1. Modo “Verificación pública ECC”
2. Subir PDF firmado
3. Verificar autenticidad
```

---

## Documentos relacionados (personal técnico)

| Documento | Contenido |
|-----------|-----------|
| [INSTALACION.md](INSTALACION.md) | Instalar, secrets, Supabase, arranque |
| [ENTREGA.md](ENTREGA.md) | Checklist de entrega / conformidad |
| [README.md](README.md) | Resumen de módulos y alcance v1 |
| [demo/](demo/) | Archivos de prueba packing |

---

## Contacto en planta

Si la app falla o necesita una cuenta nueva, avise a:

- **Administrador / TI de planta** (secrets, usuarios)  
- o a quien entregó el sistema  

---

*Manual de uso operativo — Validador de planta v1 · para personal de packing y calidad.*
