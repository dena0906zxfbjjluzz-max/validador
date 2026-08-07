use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};
use pyo3::prelude::*;
use rand::rngs::OsRng;

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

fn bytes32_desde_hex(llave_hex: &str, etiqueta: &str) -> PyResult<[u8; 32]> {
    let limpia = llave_hex
        .trim()
        .trim_start_matches("0x")
        .trim_start_matches("0X");
    let bytes = hex::decode(limpia).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("{etiqueta} hex inválida: {e}"))
    })?;
    if bytes.len() != 32 {
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "{etiqueta} debe tener 32 bytes (64 caracteres hex), se recibieron {}",
            bytes.len()
        )));
    }
    let mut arr = [0u8; 32];
    arr.copy_from_slice(&bytes);
    Ok(arr)
}

fn signing_key_desde_hex(llave_hex: &str) -> PyResult<SigningKey> {
    let seed = bytes32_desde_hex(llave_hex, "LLAVE_PRIVADA")?;
    Ok(SigningKey::from_bytes(&seed))
}

/// Firma Ed25519. Si `llave_privada_hex` viene informada (secrets), usa esa llave (modo real).
/// Si es None, genera una llave efímera (modo demo).
/// Devuelve (llave_publica_hex 64 chars, firma_hex 128 chars).
#[pyfunction]
#[pyo3(signature = (datos_reporte, llave_privada_hex=None))]
fn firmar_reporte_ecc(
    datos_reporte: String,
    llave_privada_hex: Option<String>,
) -> PyResult<(String, String)> {
    let llave_privada = match llave_privada_hex {
        Some(hex_key) if !hex_key.trim().is_empty() => signing_key_desde_hex(&hex_key)?,
        _ => SigningKey::generate(&mut OsRng),
    };

    let llave_publica = llave_privada.verifying_key();
    let firma: Signature = llave_privada.sign(datos_reporte.as_bytes());

    Ok((
        hex::encode(llave_publica.to_bytes()),
        hex::encode(firma.to_bytes()),
    ))
}

/// Verifica una firma Ed25519. Devuelve (ok, detalle).
#[pyfunction]
fn verificar_firma_ed25519(
    datos_reporte: String,
    firma_hex: String,
    llave_publica_hex: String,
) -> PyResult<(bool, String)> {
    let pub_bytes = bytes32_desde_hex(&llave_publica_hex, "Llave pública")?;
    let firma_limpia = firma_hex
        .trim()
        .trim_start_matches("0x")
        .trim_start_matches("0X");
    let firma_vec = hex::decode(firma_limpia).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("Firma hex inválida: {e}"))
    })?;
    if firma_vec.len() != 64 {
        return Ok((
            false,
            format!(
                "Firma inválida: se esperan 64 bytes (128 hex), hay {}",
                firma_vec.len()
            ),
        ));
    }
    let mut firma_arr = [0u8; 64];
    firma_arr.copy_from_slice(&firma_vec);

    let verifying_key = VerifyingKey::from_bytes(&pub_bytes).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("Llave pública Ed25519 inválida: {e}"))
    })?;
    let signature = Signature::from_bytes(&firma_arr);

    match verifying_key.verify(datos_reporte.as_bytes(), &signature) {
        Ok(()) => Ok((
            true,
            "AUTÉNTICO: firma Ed25519 válida".to_string(),
        )),
        Err(_) => Ok((
            false,
            "Firma NO válida: el contenido fue alterado o no corresponde al mensaje firmado"
                .to_string(),
        )),
    }
}

#[pymodule]
fn motor_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(validar_datos_planta, m)?)?;
    m.add_function(wrap_pyfunction!(firmar_reporte_ecc, m)?)?;
    m.add_function(wrap_pyfunction!(verificar_firma_ed25519, m)?)?;
    Ok(())
}
