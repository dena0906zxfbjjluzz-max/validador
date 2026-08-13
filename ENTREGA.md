# ACTA DE CONFORMIDAD Y ENTREGA FINAL — VALIDADOR DE PLANTA (V1)

Por el presente documento, **EL COMITENTE** deja constancia de la recepción conforme de la suite tecnológica provista por **EL LOCADOR**, dando por finalizada la fase de desarrollo e implementación según los términos acordados.

## Checklist de Validación en Planta

El personal de control de calidad e infraestructura de TI ha verificado satisfactoriamente la operación de los siguientes módulos en el entorno de producción (`Streamlit Cloud + Supabase`):

- [ ] **Módulo 1: Balanza y SSCC:** Registro correcto del campo `PESO` en la base de datos y búsqueda instantánea de pallets/lotes.
- [ ] **Módulo 2: LMR / SENASA:** Consulta en tiempo real de los veredictos de laboratorio y alertas de límites de residuos según mercado destino.
- [ ] **Módulo 3: Trazabilidad Inversa:** Desglose limpio del origen del pallet (Fundo, Productor, Turno y Lote) desde el archivo CSV/Excel cargado.
- [ ] **Módulo 4: Cadena de Frío:** Registro y almacenamiento correcto de lecturas de túnel y Reefer en la tabla `public.control_frio`.
- [ ] **Módulo 5: Contenedores y Precintos:** Validación del formulario de despacho y guardado de precintos ISO 6346.
- [ ] **Módulo 6: Escaneo QR del Pallet:** Activación correcta de la cámara del celular, escaneo del código físico y consulta exitosa a la tabla `public.historial_reportes`.
- [ ] **Módulo 7: Alertas y tendencias:** Veredicto de riesgo con frío (SQLite) y packing (pesos / LMR / merma); KPIs y detalle de alertas visibles en planta.

## Criptografía y Seguridad Operativa

- [ ] **Firma Criptográfica Ed25519:** Verificación de que cada reporte PDF se sella con la `LLAVE_PRIVADA` institucional única del cliente.
- [ ] **Verificación Pública ECC:** Comprobación externa desde el flujo público ECC, permitiendo auditar la integridad del PDF sin credenciales de planta.
- [ ] **Cortafuego y Bitácora:** Validación del sistema de login con bloqueo de intentos y registro local de operaciones.

## Conformidad de Cierre

Al marcar este checklist, **EL COMITENTE** declara su total satisfacción con el rendimiento técnico de la plataforma y da por ejecutada la entrega, dando inicio al periodo de **3 meses de soporte técnico y garantía** estipulados en el contrato.

**Fecha de Entrega:** ____ de ______________ de 2026

| | Por el Comitente | Por el Locador |
|--|------------------|----------------|
| Nombre | Jefe de TI / Operaciones Planta | Denilson Aure |
| Firma | ______________________________ | ______________________________ |
| Fecha | | |

---

*Acta de conformidad del paquete de entrega Validador de planta v1. Completar fechas y firmas al momento del cierre en planta.*  
*Plantilla complementaria de traspaso de código: [CONTRATO_TRASPASO.md](CONTRATO_TRASPASO.md).*
