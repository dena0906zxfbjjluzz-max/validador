# Checklist de cierre / entrega del Validador

Usar al **vender código + GitHub** o al poner la app en producción por primera vez.

## A. Entrega de código

- [ ] Repo GitHub accesible (o ZIP con historial Git)
- [ ] Branch `main` estable (sin cambios locales sin commit)
- [ ] Existe `README.md`, `INSTALACION.md`, `ENTREGA.md`
- [ ] Existe `supabase/schema.sql`
- [ ] Existe `demo/packing_demo.csv`
- [ ] Existe `.streamlit/secrets.toml.example` (sin contraseñas reales)
- [ ] Confirmado: **NO** se copian secrets reales del vendedor al comprador

## B. Puesta en marcha (cliente)

- [ ] Python 3.10+ o app en Streamlit Cloud
- [ ] `pip install -r requirements.txt` (o deploy Cloud)
- [ ] `secrets.toml` / Secrets Cloud con usuario, clave, `LLAVE_PRIVADA`
- [ ] Login OK
- [ ] Carga `demo/packing_demo.csv` OK
- [ ] Panel **Criptografía**: modo **real** (si hay llave válida)
- [ ] Supabase (si contratado): SQL ejecutado + URL/KEY
- [ ] Una lectura de frío guardada
- [ ] Un contenedor sellado (formulario o demo)
- [ ] Un sello ECC + descarga PDF (opcional en la misma sesión)
- [ ] Verificación pública ECC abre sin login de planta

## C. Contrato / alcance comercial (recomendado)

| Incluido en v1 | No incluido por defecto |
|----------------|-------------------------|
| Código fuente + este paquete | Hosting / dominio de producción del vendedor |
| Guía de instalación | SAP / Oracle nativo |
| CSV de demo | Balanza puerto serial industrial |
| Esquema Supabase | Soporte 24×7 sin contrato aparte |
| | Capacitación presencial sin horas extras |

**Precios, plazos y soporte** se define en cotización o contrato (no se publican en el repositorio).

## D. Firma de cierre

| Campo | Dato |
|-------|------|
| Fecha entrega | |
| Versión / commit Git | |
| Entregado por | |
| Recibido por | |
| Notas | |

Con A+B completos, la app se considera **cerrada para entrega v1**.
