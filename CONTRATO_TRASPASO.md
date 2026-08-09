# Contrato de traspaso de software  
## Validador de planta (código fuente + repositorio Git)

**Documento tipo / plantilla** — completar los campos entre corchetes.  
Adaptar con asesor legal si el monto o las partes lo requieren.  
**No incluye precios fijos** (se acuerdan en la cláusula de precio o en anexo).

---

## 1. Partes

**Vendedor (cedente):**  
Nombre / razón social: _________________________________  
DNI / RUC: _________________________________  
Domicilio: _________________________________  
Correo: _________________________________  
(en adelante, el **Vendedor**)

**Comprador (cesionario):**  
Nombre / razón social: _________________________________  
DNI / RUC: _________________________________  
Domicilio: _________________________________  
Correo: _________________________________  
(en adelante, el **Comprador**)

---

## 2. Objeto

El Vendedor traspasa al Comprador, de forma **definitiva** y a título de compraventa / cesión de derechos sobre el software denominado:

**“Validador de planta”** (aplicación Streamlit de control de calidad, trazabilidad y packing, incluyendo motor de sello Ed25519 y módulos operativos asociados),

en el estado del repositorio Git al momento de la entrega (rama `main` u otra que se indique).

El traspaso incluye:

1. **Código fuente** del proyecto (archivos de aplicación, configuración de ejemplo, documentación de instalación incluida en el repo).  
2. **Historial Git** del repositorio (según se entregue: transferencia de ownership en GitHub, clon con historial, o archivo equivalente).  
3. **Documentación** incluida en el repositorio (`README`, `INSTALACION.md`, `ENTREGA.md`, `demo/`, `supabase/schema.sql`, plantilla de secrets, etc.).  
4. **Derechos de uso, modificación y explotación comercial** del software en el alcance de la cláusula 4, sin limitación territorial salvo pacto en contrario.

---

## 3. Forma de entrega

La entrega se considerará cumplida cuando ocurra **una o más** de las siguientes (marcar lo acordado):

- [ ] Transferencia de ownership del repositorio GitHub a la cuenta/organización del Comprador.  
- [ ] Invitación como administrador al repo y posterior renuncia del Vendedor al control.  
- [ ] Entrega de repositorio exportado (mirror / ZIP con historial Git) y hash o commit de referencia.

**Commit / etiqueta de entrega:** `________________`  
**URL del repositorio (antes del traspaso):** `________________`  
**Fecha de entrega efectiva:** `____ / ____ / ________`

### 3.1. Lo que **no** se entrega (salvo acuerdo escrito aparte)

- Credenciales reales del Vendedor (login de planta, Supabase propio, `LLAVE_PRIVADA` de producción del Vendedor, tokens).  
- Base de datos operativa del Vendedor (`*.db` con datos de terceros).  
- Cuenta Streamlit Community Cloud, dominio o hosting del Vendedor.  
- Datos personales o comerciales de clientes del Vendedor.  
- Soporte, capacitación, personalizaciones o integraciones ERP (SAP/Oracle, etc.), salvo anexo de servicios.

El Comprador es responsable de configurar **sus propios** secrets, proyecto Supabase, hosting y llaves criptográficas.

---

## 4. Derechos y obligaciones

### 4.1. El Vendedor declara

- Ser autor o titular legítimo del software y de los derechos que traspasa.  
- Que el software se entrega **“tal cual” (as is)** en el commit indicado, sin garantía de idoneidad para un fin particular no pactado.  
- Que no retiene derechos de explotación exclusivos sobre lo traspasado, salvo uso de portafolio / mención no confusa si ambas partes lo autorizan por escrito.

### 4.2. El Comprador declara

- Haber tenido (o renunciar a) oportunidad de revisar el código y la documentación de instalación.  
- Asumir la puesta en marcha, seguridad, backups y cumplimiento legal de su operación.  
- No exigir al Vendedor secretos, cuentas o datos ajenos a la lista de entrega.

### 4.3. Portafolio (opcional)

- [ ] El Vendedor **puede** mencionar en CV/LinkedIn haber desarrollado el sistema, sin revelar secretos del Comprador.  
- [ ] El Vendedor **no** publicará el código tras el traspaso si el repo pasa a privado del Comprador.

---

## 5. Precio y forma de pago

Precio total del traspaso: **S/ ______________** ( ________________________ soles),  
más IGV si corresponde legalmente: **[ ] Sí  [ ] No / exonerado / otro:** ________.

Forma de pago:

- [ ] 100 % contra entrega del repo.  
- [ ] 50 % al firmar · 50 % al confirmar recepción (commit / ownership).  
- [ ] Otro: _________________________________

Cuenta / medio de pago: _________________________________

La entrega del control del repositorio se realiza **tras el pago acordado** (o la parte que habilite la entrega).

---

## 6. Garantía limitada (opcional)

Durante **____ días** desde la entrega, el Vendedor solo se compromete a:

- [ ] Aclarar dudas de instalación por correo/chat (máx. ____ horas o ____ mensajes).  
- [ ] Corregir fallas de **bloqueo total** reproducibles en el commit entregado (no bugs de datos del Comprador ni de su hosting).

Fuera de ese plazo: sin obligación de soporte, salvo nuevo contrato de servicios.

---

## 7. Confidencialidad

Las partes no divulgarán datos comerciales sensibles, credenciales ni información del otro, salvo requerimiento legal o acuerdo escrito.

---

## 8. Limitación de responsabilidad

En la máxima medida permitida por la ley aplicable, la responsabilidad total del Vendedor por este contrato no excederá el **monto efectivamente pagado** por el Comprador por el traspaso.  
No se responden daños indirectos, lucro cesante ni pérdidas de datos por mal uso, hosting o configuración del Comprador.

---

## 9. Ley y disputas

Este contrato se rige por las leyes de la **República del Perú**.  
Controversias: trato directo; de no resolverse, se someterán a los jueces y tribunales de **________________** (ciudad).

---

## 10. Aceptación

Al firmar, las partes aceptan el traspaso en los términos de este documento y sus anexos.

| | Vendedor | Comprador |
|--|----------|-----------|
| Nombre | | |
| Documento | | |
| Firma | | |
| Fecha | | |

---

## Anexo A — Acta de recepción (llenar al entregar)

Yo, ________________________ (Comprador), confirmo haber recibido el software **Validador de planta** en la forma:

- [ ] Ownership GitHub transferido a: `________________`  
- [ ] Acceso admin / mirror / ZIP con historial  

Commit de referencia: `________________`  
Fecha: `____ / ____ / ________`  
Firma del Comprador: ________________

---

## Anexo B — Checklist técnico de entrega (resumen)

- [ ] Repo accesible al Comprador  
- [ ] Documentación de instalación presente  
- [ ] Demo y `schema.sql` presentes  
- [ ] Plantilla de secrets (sin secretos del Vendedor)  
- [ ] Comprador informado de que debe crear sus secrets y hosting  

Ver también `ENTREGA.md` del repositorio.

---

*Plantilla orientativa. No sustituye asesoría legal personalizada.*
