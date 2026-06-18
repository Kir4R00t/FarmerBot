CREATE SCHEMA IF NOT EXISTS farmerbot;

CREATE TABLE IF NOT EXISTS farmerbot.etl_run (
    run_id UUID PRIMARY KEY,
    pipeline_name TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    records_loaded INTEGER NOT NULL DEFAULT 0,
    records_failed INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS farmerbot.dim_league (
    league_id BIGSERIAL PRIMARY KEY,
    league_name TEXT NOT NULL UNIQUE,
    divine_price NUMERIC(18, 6),
    chaos_divine_price NUMERIC(18, 6),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS farmerbot.dim_category (
    category_id BIGSERIAL PRIMARY KEY,
    category_name TEXT NOT NULL UNIQUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS farmerbot.dim_item (
    item_id BIGSERIAL PRIMARY KEY,
    api_id TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS farmerbot.raw_poe2scout_response (
    raw_response_id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES farmerbot.etl_run(run_id),
    source_endpoint TEXT NOT NULL,
    league_name TEXT,
    category_name TEXT,
    reference_currency TEXT,
    payload JSONB NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS farmerbot.fact_price_snapshot (
    snapshot_id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES farmerbot.etl_run(run_id),
    item_id BIGINT NOT NULL REFERENCES farmerbot.dim_item(item_id),
    league_id BIGINT NOT NULL REFERENCES farmerbot.dim_league(league_id),
    category_id BIGINT NOT NULL REFERENCES farmerbot.dim_category(category_id),
    reference_currency TEXT NOT NULL,
    current_price NUMERIC(18, 6) NOT NULL CHECK (current_price >= 0),
    snapshot_at TIMESTAMPTZ NOT NULL,
    price_logs JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_item JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (
        item_id,
        league_id,
        category_id,
        reference_currency,
        snapshot_at
    )
);

CREATE TABLE IF NOT EXISTS farmerbot.fact_price_log (
    price_log_id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES farmerbot.etl_run(run_id),
    item_id BIGINT NOT NULL REFERENCES farmerbot.dim_item(item_id),
    league_id BIGINT NOT NULL REFERENCES farmerbot.dim_league(league_id),
    category_id BIGINT NOT NULL REFERENCES farmerbot.dim_category(category_id),
    reference_currency TEXT NOT NULL,
    source_time TIMESTAMPTZ NOT NULL,
    price NUMERIC(18, 6) NOT NULL CHECK (price >= 0),
    quantity INTEGER,
    frequency_hours INTEGER NOT NULL CHECK (frequency_hours > 0),
    raw_log JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (
        item_id,
        league_id,
        category_id,
        reference_currency,
        source_time,
        frequency_hours
    )
);

CREATE TABLE IF NOT EXISTS farmerbot.data_quality_issue (
    issue_id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES farmerbot.etl_run(run_id),
    source_name TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'error')),
    issue_type TEXT NOT NULL,
    message TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fact_price_snapshot_lookup
    ON farmerbot.fact_price_snapshot (
        league_id,
        category_id,
        reference_currency,
        snapshot_at DESC
    );

CREATE INDEX IF NOT EXISTS idx_fact_price_log_lookup
    ON farmerbot.fact_price_log (
        league_id,
        category_id,
        reference_currency,
        source_time DESC
    );

CREATE INDEX IF NOT EXISTS idx_raw_poe2scout_response_payload
    ON farmerbot.raw_poe2scout_response USING GIN (payload);

CREATE OR REPLACE VIEW farmerbot.mart_item_snapshot_prices AS
SELECT
    l.league_name,
    c.category_name,
    i.api_id,
    i.display_name,
    f.reference_currency,
    f.snapshot_at,
    f.current_price,
    f.loaded_at
FROM farmerbot.fact_price_snapshot f
JOIN farmerbot.dim_item i ON i.item_id = f.item_id
JOIN farmerbot.dim_league l ON l.league_id = f.league_id
JOIN farmerbot.dim_category c ON c.category_id = f.category_id;

CREATE OR REPLACE VIEW farmerbot.mart_item_price_history AS
SELECT
    l.league_name,
    c.category_name,
    i.api_id,
    i.display_name,
    f.reference_currency,
    f.source_time,
    f.price,
    f.quantity,
    f.frequency_hours,
    f.loaded_at
FROM farmerbot.fact_price_log f
JOIN farmerbot.dim_item i ON i.item_id = f.item_id
JOIN farmerbot.dim_league l ON l.league_id = f.league_id
JOIN farmerbot.dim_category c ON c.category_id = f.category_id;
