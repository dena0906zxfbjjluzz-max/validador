"""
Fachada de compatibilidad: la lógica vive en el paquete `planta/`.

Mantener `import funciones` en UI y scripts existentes.
"""
from __future__ import annotations

from planta.avisos import (  # noqa: F401
    _config_avisos,
    enviar_aviso_email,
    enviar_aviso_whatsapp,
    notificar_ruptura_frio,
)
from planta.contenedores import (  # noqa: F401
    buscar_contenedor_local,
    cargar_contenedores_db,
    consultar_contenedores_supabase,
    enviar_contenedor_supabase,
    guardar_contenedor_db,
    parsear_payload_contenedor,
    procesar_escaneo_contenedor_camara,
    registrar_contenedor_despacho,
    validar_y_consultar_contenedor,
)
from planta.db import (  # noqa: F401
    DB_NAME,
    DB_PATH,
    calcular_hash_reporte,
    cargar_bitacora_db,
    cargar_historial_db,
    guardar_cambio_db,
    guardar_historial_db,
    inicializar_base_datos,
)
from planta.frio import (  # noqa: F401
    cargar_frio_db,
    enviar_control_frio_supabase,
    guardar_frio_db,
    obtener_rango_frio_fruta,
    purgar_control_frio_local,
    registrar_control_frio,
    validar_temperatura_fruta,
)
from planta.inteligencia import (  # noqa: F401
    alertas_frio_activas,
    analizar_patrones_packing,
    analizar_tendencias_frio,
    cargar_frio_dataframe,
    consolidar_inteligencia_planta,
    resumen_dashboard_turno,
)
from planta.packing import (  # noqa: F401
    ALIAS_COLUMNAS,
    CAMPOS_CRITICOS_PACKING,
    CAMPOS_MAPEO_UI,
    aplicar_estilo_corporativo_hoja,
    armar_arbol_trazabilidad,
    buscar_registros_por_codigo,
    campos_criticos_sin_mapear,
    cargar_datos_archivo,
    encontrar_columna,
    escribir_dataframe_corporativo,
    exportar_packing_csv_bytes,
    generar_excel_corporativo,
    interpretar_estado_lmr,
    mapear_columnas_trazabilidad,
    registrar_peso_ultima_fila,
    resaltar_errores_celdas,
    resolver_mapa_columnas,
)
from planta.balanza import (  # noqa: F401
    leer_peso_serial,
    listar_puertos_serial,
    parsear_peso_desde_texto,
)
from planta.cola_sync import (  # noqa: F401
    encolar_sync,
    listar_cola_sync,
    procesar_cola_sync,
)
from planta.demo import sembrar_datos_demo  # noqa: F401
from planta.informe import (  # noqa: F401
    consolidar_informe_semanal,
    enviar_informe_semanal_email,
)
from planta.pdfs import (  # noqa: F401
    extraer_sello_ecc_pdf,
    generar_pdf_dashboard_turno,
    generar_pdf_errores,
    generar_pdf_informe_semanal,
    generar_pdf_resumen,
)
from planta.usuarios import (  # noqa: F401
    crear_usuario_local,
    desactivar_usuario_local,
    listar_usuarios_local,
)
from planta.qr_pallet import (  # noqa: F401
    construir_payload_qr,
    consultar_historial_reportes_supabase,
    decodificar_qr_desde_imagen,
    parsear_payload_qr,
    procesar_escaneo_qr_camara,
    validar_pallet_por_qr,
)
from planta.supabase_io import (  # noqa: F401
    buscar_reporte_por_hash,
    cargar_historial_reportes_db,
    enviar_sello_a_supabase,
    guardar_reporte_historico,
)
