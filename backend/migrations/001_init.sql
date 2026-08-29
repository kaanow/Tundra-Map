-- Tundra-Map schema v1.
--
-- Two-user freezer inventory. There is no auth at the HTTP layer; users are
-- just labels for attribution.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL UNIQUE,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Short, URL-safe item IDs so QR modules stay low.
CREATE OR REPLACE FUNCTION gen_short_id() RETURNS text AS $$
DECLARE
    alphabet text := 'abcdefghijkmnpqrstuvwxyz23456789';
    result   text := '';
    i        int;
BEGIN
    FOR i IN 1..8 LOOP
        result := result || substr(alphabet, 1 + floor(random() * length(alphabet))::int, 1);
    END LOOP;
    RETURN result;
END;
$$ LANGUAGE plpgsql VOLATILE;

CREATE TABLE IF NOT EXISTS items (
    id           text PRIMARY KEY DEFAULT gen_short_id(),
    name         text NOT NULL,
    added_at     timestamptz NOT NULL DEFAULT now(),
    added_by     uuid REFERENCES users(id),
    quantity     numeric,
    unit         text,
    source       text,
    notes        text,
    category     text,
    location     text,
    photo_url    text,
    consumed_at  timestamptz,
    consumed_by  uuid REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS items_consumed_idx  ON items (consumed_at) WHERE consumed_at IS NULL;
CREATE INDEX IF NOT EXISTS items_added_at_idx  ON items (added_at DESC);
CREATE INDEX IF NOT EXISTS items_category_idx  ON items (category);

CREATE TABLE IF NOT EXISTS print_jobs (
    id            bigserial PRIMARY KEY,
    item_id       text NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    requested_at  timestamptz NOT NULL DEFAULT now(),
    requested_by  uuid REFERENCES users(id),
    printed_at    timestamptz,
    error         text,
    attempts      int NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS print_jobs_pending_idx
    ON print_jobs (requested_at)
    WHERE printed_at IS NULL AND error IS NULL;

-- Wake the print worker the moment a job is inserted.
CREATE OR REPLACE FUNCTION notify_print_job() RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify('print_jobs', NEW.id::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS print_jobs_notify ON print_jobs;
CREATE TRIGGER print_jobs_notify
    AFTER INSERT ON print_jobs
    FOR EACH ROW EXECUTE FUNCTION notify_print_job();
