-- =============================================================================
-- Validador de planta — esquema mínimo Supabase (PostgreSQL)
-- Ejecutar en: Supabase → SQL Editor → Run
-- =============================================================================

-- 1) Sellos ECC / verificación QR (Módulo 6 + historial)
CREATE TABLE IF NOT EXISTS public.historial_reportes (
  id            bigserial PRIMARY KEY,
  fecha         text NOT NULL,
  lote          text NOT NULL,
  hash_sha256   text NOT NULL UNIQUE,
  inspector     text NOT NULL,
  created_at    timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_historial_reportes_lote
  ON public.historial_reportes (lote);
CREATE INDEX IF NOT EXISTS idx_historial_reportes_hash
  ON public.historial_reportes (hash_sha256);

-- 2) Cadena de frío (Módulo 4)
CREATE TABLE IF NOT EXISTS public.control_frio (
  id              bigserial PRIMARY KEY,
  fecha           text,
  hora_registro   text,
  camara          text,
  temperatura     double precision,
  estado          text,
  inspector       text,
  producto        text,
  temp_min        double precision,
  temp_max        double precision,
  created_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_control_frio_fecha
  ON public.control_frio (created_at DESC);

-- 3) Contenedores / bookings / precintos (Módulo 5)
CREATE TABLE IF NOT EXISTS public.contenedores_despacho (
  id               bigserial PRIMARY KEY,
  booking          text,
  contenedor       text NOT NULL,
  precinto_linea   text,
  precinto_senasa  text,
  destino          text,
  estado           text,
  inspector        text,
  fecha            text,
  created_at       timestamptz DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_contenedores_despacho_contenedor
  ON public.contenedores_despacho (contenedor);

-- 4) RLS opcional: con service_role key la app suele bypassear RLS.
-- Si usa solo anon key, cree policies de INSERT/SELECT según su política.
-- Ejemplo permisivo solo para DEMO (NO producción open):
-- ALTER TABLE public.historial_reportes ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "demo_all_hist" ON public.historial_reportes FOR ALL USING (true) WITH CHECK (true);

COMMENT ON TABLE public.historial_reportes IS 'Sellos lote: fecha, lote, hash_sha256, inspector';
COMMENT ON TABLE public.control_frio IS 'Lecturas de cámara / reefer';
COMMENT ON TABLE public.contenedores_despacho IS 'Booking, contenedor ISO y precintos';
