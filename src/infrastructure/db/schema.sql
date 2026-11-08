CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE rol_usuario AS ENUM ('admin', 'usuario');
CREATE TYPE estado_cierre AS ENUM ('oficial', 'no_oficial');
CREATE TYPE origen_cierre AS ENUM ('manual', 'cascada');
CREATE TYPE categoria_servicio AS ENUM (
    'basico', 'completo', 'vip', 'rama_87', 'rama_89', 'rama_90'
);


CREATE TABLE IF NOT EXISTS periodo (
    id             SERIAL PRIMARY KEY,
    nombre         CITEXT NOT NULL CHECK (char_length(nombre) <= 20),
    anio           INTEGER NOT NULL CHECK (anio BETWEEN 2014 AND 2100),
    mes            INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
    hojas_entrada  JSONB,
    UNIQUE (anio, mes)
);
CREATE INDEX IF NOT EXISTS idx_periodo_anio ON periodo (anio);
CREATE INDEX IF NOT EXISTS idx_periodo_mes ON periodo (mes);

CREATE TABLE IF NOT EXISTS tipo_servicio (
    id     SERIAL PRIMARY KEY,
    rama   VARCHAR(25) NOT NULL,
    nombre CITEXT NOT NULL CHECK (char_length(nombre) <= 50),
    codigo VARCHAR(10) NOT NULL UNIQUE,
    categoria categoria_servicio NOT NULL,
    es_alias BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_tipo_servicio_rama ON tipo_servicio (rama);
CREATE INDEX IF NOT EXISTS idx_periodo_nombre ON tipo_servicio (nombre);

CREATE TABLE IF NOT EXISTS cierre (
    id          SERIAL PRIMARY KEY,
    periodo_id  INTEGER NOT NULL REFERENCES periodo(id),
    version     INTEGER NOT NULL CHECK (version > 0),
    estado      estado_cierre NOT NULL,
    origen      origen_cierre NOT NULL,
    motivo      TEXT,
    aumento     NUMERIC(6, 2) NOT NULL CHECK (aumento > -100),
    snapshot    JSONB,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (periodo_id, version)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_cierre_oficial
    ON cierre (periodo_id) WHERE estado = 'oficial';

CREATE TABLE IF NOT EXISTS alicuota (
    periodo_id        INTEGER NOT NULL REFERENCES periodo(id),
    tipo_servicio_id  INTEGER NOT NULL REFERENCES tipo_servicio(id),
    coeficiente       NUMERIC(10, 6) NOT NULL,
    valor             NUMERIC(12, 2) NOT NULL CHECK (valor > 0),
    UNIQUE (periodo_id, tipo_servicio_id, coeficiente)
);
CREATE INDEX IF NOT EXISTS idx_alicuota ON alicuota (periodo_id, tipo_servicio_id, coeficiente);

CREATE TABLE IF NOT EXISTS servicio (
    nro_servicio      CITEXT NOT NULL CHECK (char_length(nro_servicio) <= 20),
    codigo_radio      CITEXT NOT NULL CHECK (char_length(codigo_radio) <= 6),
    fecha             DATE NOT NULL,
    dominio           CITEXT NOT NULL CHECK (char_length(dominio) <= 12),
    cod_productor     INTEGER NOT NULL,
    periodo_id        INTEGER NOT null REFERENCES periodo(id),
    tipo_servicio_id  INTEGER NOT null REFERENCES tipo_servicio(id),
    UNIQUE (nro_servicio)
);
CREATE INDEX IF NOT EXISTS idx_servicio_periodo ON servicio (periodo_id);
CREATE INDEX IF NOT EXISTS idx_servicio_periodo_tipo_servicio ON servicio (periodo_id, tipo_servicio_id);

CREATE TABLE IF NOT EXISTS capita_periodo (
    periodo_id        INTEGER NOT NULL REFERENCES periodo(id) ,
    tipo_servicio_id  INTEGER NOT NULL REFERENCES tipo_servicio(id) ,
    capitas           INTEGER NOT NULL CHECK (capitas >= 0),
    PRIMARY KEY (periodo_id, tipo_servicio_id)
);



CREATE TABLE IF NOT EXISTS usuario (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	nombre CITEXT NOT NULL UNIQUE CHECK (
		char_length(nombre) >= 3
	),
	password_hash TEXT NOT NULL,
	rol rol_usuario NOT NULL DEFAULT 'usuario',
	email CITEXT UNIQUE NULL CHECK (
		char_length(email) <= 255
	),
	activo BOOLEAN NOT NULL DEFAULT TRUE,
	creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
	actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
