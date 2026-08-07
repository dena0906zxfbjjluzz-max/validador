use pyo3::prelude::*;
use p256::ecdsa::{SigningKey, Signature, signature::Signer};
use p256::FieldBytes;
use rand_core::OsRng;

/// Función de alta velocidad para validar mermas y auditorías
#[pyfunction]
fn validar_datos_planta(total_filas: usize, mermas: f64) -> PyResult<(f64, String)> {
    let porcentaje_eficiencia = (1.0 - (mermas / total_filas as f64)) * 100.0;
    let estado = if porcentaje_eficiencia > 95.0 {
        "Aprobado - Planta Eficiente".to_string()
    } else {
        "Alerta - Revisar Línea de Producción".to_string()
    };

    Ok((porcentaje_eficiencia, estado))
}

fn signing_key_desde_hex(llave_hex: &str) -> PyResult<SigningKey> {
    let limpia = llave_hex.trim().trim_start_matches("0x").trim_start_matches("0X");
    let bytes = hex::decode(limpia).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("LLAVE_PRIVADA hex inválida: {e}"))
    })?;
    if bytes.len() != 32 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "LLAVE_PRIVADA debe tener 32 bytes (64 caracteres hex)",
        ));
    }
    let mut field_bytes = FieldBytes::default();
    field_bytes.copy_from_slice(&bytes);
    SigningKey::from_bytes(&field_bytes).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("No se pudo cargar SigningKey: {e}"))
    })
}

/// Firma ECDSA P-256. Si `llave_privada_hex` viene informada (secrets), usa esa llave (modo real).
/// Si es None, genera una llave efímera (modo demo).
#[pyfunction]
#[pyo3(signature = (datos_reporte, llave_privada_hex=None))]
fn firmar_reporte_ecc(
    datos_reporte: String,
    llave_privada_hex: Option<String>,
) -> PyResult<(String, String)> {
    let llave_privada = match llave_privada_hex {
        Some(hex_key) if !hex_key.trim().is_empty() => signing_key_desde_hex(&hex_key)?,
        _ => SigningKey::random(&mut OsRng),
    };

    let llave_publica = llave_privada.verifying_key();
    let firma: Signature = llave_privada.sign(datos_reporte.as_bytes());

    Ok((
        hex::encode(llave_publica.to_sec1_bytes()),
        hex::encode(firma.to_bytes()),
    ))
}

#[pymodule]
fn motor_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(validar_datos_planta, m)?)?;
    m.add_function(wrap_pyfunction!(firmar_reporte_ecc, m)?)?;
    Ok(())
}
