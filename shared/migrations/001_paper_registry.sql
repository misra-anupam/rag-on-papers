-- Paper registry: tracks every paper through the full pipeline
-- DOI is the primary deduplication key.
-- Papers without DOIs use SHA256(title || first_author) as a synthetic key.

CREATE TABLE IF NOT EXISTS paper_registry (
    doi              TEXT PRIMARY KEY,
    paper_id         TEXT,                          -- source-native ID
    source           TEXT        NOT NULL,          -- pubmed|europepmc|semanticscholar|biorxiv
    fetch_status     TEXT        NOT NULL DEFAULT 'fetched',
    parse_status     TEXT        NOT NULL DEFAULT 'pending',
    embed_status     TEXT        NOT NULL DEFAULT 'pending',
    index_status     TEXT        NOT NULL DEFAULT 'pending',
    title            TEXT,
    authors          JSONB,
    journal          TEXT,
    publication_date DATE,
    mesh_terms       TEXT[],
    s3_raw_key       TEXT,
    s3_parsed_key    TEXT,
    fetched_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_paper_registry_fetch_status  ON paper_registry (fetch_status);
CREATE INDEX IF NOT EXISTS idx_paper_registry_parse_status  ON paper_registry (parse_status);
CREATE INDEX IF NOT EXISTS idx_paper_registry_embed_status  ON paper_registry (embed_status);
CREATE INDEX IF NOT EXISTS idx_paper_registry_index_status  ON paper_registry (index_status);
CREATE INDEX IF NOT EXISTS idx_paper_registry_pub_date      ON paper_registry (publication_date);
CREATE INDEX IF NOT EXISTS idx_paper_registry_source        ON paper_registry (source);

-- Automatically update updated_at on any row change
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_paper_registry_updated_at ON paper_registry;
CREATE TRIGGER trg_paper_registry_updated_at
    BEFORE UPDATE ON paper_registry
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
