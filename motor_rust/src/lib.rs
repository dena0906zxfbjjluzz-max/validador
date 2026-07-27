use pyo3::prelude::*;

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

/// Módulo que Python importará nativamente
#[pymodule]
fn motor_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(validar_datos_planta, m)?)?;
    Ok(())
}
