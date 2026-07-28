use pyo3::prelude::*;
use p256::ecdsa::{SigningKey, Signature, signature::Signer};
use rand_core::OsRng; // <- CAMBIO AQUÍ: Importación directa y limpia

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

/// Genera una firma criptográfica única usando la curva elíptica P-256
#[pyfunction]
fn firmar_reporte_ecc(datos_reporte: String) -> PyResult<(String, String)> {
    // 1. Genera una llave privada secreta de curva elíptica sobre la marcha
    let llave_privada = SigningKey::random(&mut OsRng);
    
    // 2. Extrae la llave pública correspondiente
    let llave_publica = llave_privada.verifying_key();
    
    // 3. Firma matemáticamente el texto del reporte de mermas
    let firma: Signature = llave_privada.sign(datos_reporte.as_bytes());
    
    // Convertimos los resultados a texto legible para Python
    Ok((
        hex::encode(llave_publica.to_sec1_bytes()),
        hex::encode(firma.to_bytes())
    ))
}

/// Módulo que Python importará nativamente
#[pymodule]
fn motor_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(validar_datos_planta, m)?)?;
    m.add_function(wrap_pyfunction!(firmar_reporte_ecc, m)?)?;
    Ok(())
}
