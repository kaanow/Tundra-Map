-- Soft delete.
--
-- Deleting an item hides it everywhere in the app but leaves the row in place,
-- so a mistaken delete is recoverable in psql. There is deliberately no API or
-- UI path back — if we ever want one, the data is already here.
--
-- Keeping the row also means gen_short_id() will never hand a deleted item's
-- ID to a new one, so an old printed label can't start resolving to something
-- else.

ALTER TABLE items ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
ALTER TABLE items ADD COLUMN IF NOT EXISTS deleted_by uuid REFERENCES users(id);

-- Every read path filters on deleted_at IS NULL; index for it.
CREATE INDEX IF NOT EXISTS items_live_idx
    ON items (added_at DESC)
    WHERE deleted_at IS NULL;
