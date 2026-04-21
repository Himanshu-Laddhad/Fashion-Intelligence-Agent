-- Fashion Intelligence DuckDB Schema

-- ─────────────────────────────────────────────
-- Sequences for auto-increment PKs
-- ─────────────────────────────────────────────
CREATE SEQUENCE IF NOT EXISTS seq_trend_snapshots START 1;
CREATE SEQUENCE IF NOT EXISTS seq_trend_scores    START 1;
CREATE SEQUENCE IF NOT EXISTS seq_google_trends   START 1;
CREATE SEQUENCE IF NOT EXISTS seq_fashion_items   START 1;
CREATE SEQUENCE IF NOT EXISTS seq_model_registry  START 1;

-- ─────────────────────────────────────────────
-- 1. trend_snapshots
--    One row per (query, source, timestamp) scrape run.
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trend_snapshots (
    id         INTEGER  PRIMARY KEY DEFAULT nextval('seq_trend_snapshots'),
    query      VARCHAR  NOT NULL,
    source     VARCHAR  NOT NULL,
    timestamp  TIMESTAMP NOT NULL,
    item_count INTEGER,
    raw_json   JSON
);

-- ─────────────────────────────────────────────
-- 2. trend_scores
--    Computed TVI scores per (query, date).
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trend_scores (
    id                  INTEGER   PRIMARY KEY DEFAULT nextval('seq_trend_scores'),
    query               VARCHAR   NOT NULL,
    scored_at           TIMESTAMP NOT NULL,
    tvi_score           FLOAT,
    google_trend_score  FLOAT,
    social_score        FLOAT,
    retail_score        FLOAT,
    confidence          VARCHAR,
    forecast_json       JSON
);

-- ─────────────────────────────────────────────
-- 3. google_trends_raw
--    Raw pytrends time-series responses.
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS google_trends_raw (
    id                  INTEGER   PRIMARY KEY DEFAULT nextval('seq_google_trends'),
    query               VARCHAR   NOT NULL,
    fetched_at          TIMESTAMP NOT NULL,
    interest_over_time  JSON,
    related_queries     JSON
);

-- ─────────────────────────────────────────────
-- 4. fashion_items
--    Scraped product items with optional embeddings.
--    NOTE: FLOAT[] stores sentence-transformer vectors.
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fashion_items (
    id          INTEGER   PRIMARY KEY DEFAULT nextval('seq_fashion_items'),
    source      VARCHAR,
    query       VARCHAR,
    scraped_at  TIMESTAMP,
    name        VARCHAR,
    color       VARCHAR,
    material    VARCHAR,
    price       FLOAT,
    image_url   VARCHAR,
    description VARCHAR,
    embedding   FLOAT[]
);

-- ─────────────────────────────────────────────
-- 5. customer_segments
--    RFM scores + cluster assignment per customer.
--    No sequence — customer_id is a natural key (VARCHAR PK).
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customer_segments (
    customer_id        VARCHAR   PRIMARY KEY,
    recency_days       INTEGER,
    frequency          INTEGER,
    monetary           FLOAT,
    rfm_score          VARCHAR,
    cluster_id         INTEGER,
    cluster_label      VARCHAR,
    churn_probability  FLOAT,
    clv_12m            FLOAT,
    segmented_at       TIMESTAMP
);

-- ─────────────────────────────────────────────
-- 6. model_registry
--    Metadata for every trained / logged model.
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS model_registry (
    id             INTEGER   PRIMARY KEY DEFAULT nextval('seq_model_registry'),
    model_name     VARCHAR   NOT NULL,
    version        VARCHAR,
    trained_at     TIMESTAMP,
    metrics        JSON,
    params         JSON,
    artifact_path  VARCHAR
);
