-- Beacon-Safe seed data
BEGIN;

INSERT INTO users (username, email, display_name)
VALUES ('demo', 'demo@beacon-safe.local', 'Demo User')
ON CONFLICT (username) DO NOTHING;

COMMIT;
