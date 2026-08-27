-- Switch new item IDs to 5 numeric digits.
--
-- Rationale: freezer holds ~100-200 items at a time; 5 digits gives a
-- 100k namespace which is enough for the lifetime of the app. Numeric-only
-- IDs QR-encode ~40% denser than alphanumeric (numeric mode packs 3 digits
-- per 10 bits vs. alphanumeric 2 chars per 11 bits) AND are easier to
-- type/dictate — no case, no confusable letters.
--
-- Existing 8-char IDs stay valid; nothing renames them.

CREATE OR REPLACE FUNCTION gen_short_id() RETURNS text AS $$
DECLARE
    candidate text;
    tries     int := 0;
BEGIN
    LOOP
        candidate := lpad((floor(random() * 100000))::int::text, 5, '0');
        EXIT WHEN NOT EXISTS (SELECT 1 FROM items WHERE id = candidate);
        tries := tries + 1;
        IF tries > 50 THEN
            RAISE EXCEPTION 'gen_short_id: failed to find free 5-digit id after 50 tries (namespace saturated?)';
        END IF;
    END LOOP;
    RETURN candidate;
END;
$$ LANGUAGE plpgsql VOLATILE;
