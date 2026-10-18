CREATE TABLE IF NOT EXISTS financial_records (
    id BIGSERIAL PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL,
    amount NUMERIC(15,2) NOT NULL CHECK (amount >= 0),
    tx_type VARCHAR(16) NOT NULL CHECK (tx_type IN ('credit', 'debit')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    table_name TEXT NOT NULL,
    record_id BIGINT NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    old_data JSONB,
    new_data JSONB,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    anchored BOOLEAN NOT NULL DEFAULT FALSE,
    epoch_id BIGINT
);

CREATE INDEX IF NOT EXISTS idx_audit_unanchored
    ON audit_log (anchored, id);

CREATE TABLE IF NOT EXISTS epoch_anchors (
    epoch_id BIGINT PRIMARY KEY,
    first_audit_id BIGINT NOT NULL,
    last_audit_id BIGINT NOT NULL,
    leaf_count INTEGER NOT NULL,
    merkle_root CHAR(64) NOT NULL,
    tx_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION log_financial_record_change()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log(table_name, record_id, operation, old_data, new_data)
        VALUES (TG_TABLE_NAME, NEW.id, TG_OP, NULL, to_jsonb(NEW));
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_log(table_name, record_id, operation, old_data, new_data)
        VALUES (TG_TABLE_NAME, NEW.id, TG_OP, to_jsonb(OLD), to_jsonb(NEW));
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log(table_name, record_id, operation, old_data, new_data)
        VALUES (TG_TABLE_NAME, OLD.id, TG_OP, to_jsonb(OLD), NULL);
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS financial_records_audit_trigger ON financial_records;
CREATE TRIGGER financial_records_audit_trigger
AFTER INSERT OR UPDATE OR DELETE ON financial_records
FOR EACH ROW EXECUTE FUNCTION log_financial_record_change();
