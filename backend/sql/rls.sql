-- VAYU-READY row-level security, audit trigger and least-privilege grants.
-- Run as the database owner, after schema.sql.

-- 1. Restricted role used by the API. It cannot drop tables or edit audit_log.
--    The seed script resets this password from APP_DB_PASSWORD.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vayu_app') THEN
    CREATE ROLE vayu_app LOGIN PASSWORD 'vayu_app_pw';
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO vayu_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO vayu_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO vayu_app;
REVOKE UPDATE ON audit_log FROM vayu_app;          -- audit trail: read and append only
GRANT DELETE ON system_logs TO vayu_app;           -- 180-day log retention job
GRANT DELETE ON hangar_slots TO vayu_app;

-- 2. Audit trail is append-only for everyone, including the owner.
CREATE OR REPLACE FUNCTION audit_log_block_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only: % is not allowed', TG_OP;
END $$;

DROP TRIGGER IF EXISTS audit_log_no_update_delete ON audit_log;
CREATE TRIGGER audit_log_no_update_delete BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION audit_log_block_change();

DROP TRIGGER IF EXISTS audit_log_no_truncate ON audit_log;
CREATE TRIGGER audit_log_no_truncate BEFORE TRUNCATE ON audit_log
  FOR EACH STATEMENT EXECUTE FUNCTION audit_log_block_change();

-- 3. Row-level security by role and squadron.
--    The API sets app.role and app.squadron at the start of every transaction.
CREATE OR REPLACE FUNCTION app_role() RETURNS text LANGUAGE sql STABLE AS $$
  SELECT coalesce(current_setting('app.role', true), '')
$$;

CREATE OR REPLACE FUNCTION app_can_see_squadron(sq text) RETURNS boolean LANGUAGE sql STABLE AS $$
  SELECT CASE
    -- ENGO, TECH and CO: own squadron only
    WHEN app_role() IN ('CO', 'ENGO', 'TECH') THEN sq = current_setting('app.squadron', true)
    -- These roles see all squadrons. ADMIN sees aircraft records only (see policies below).
    WHEN app_role() IN ('LOGO', 'BRD', 'FSO', 'AUDITOR', 'HQ', 'ADMIN', 'SYSTEM') THEN true
    ELSE false
  END
$$;

ALTER TABLE aircraft ENABLE ROW LEVEL SECURITY;
ALTER TABLE engines  ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts   ENABLE ROW LEVEL SECURITY;
ALTER TABLE defects  ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks    ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS aircraft_by_squadron ON aircraft;
CREATE POLICY aircraft_by_squadron ON aircraft TO vayu_app
  USING (app_can_see_squadron(squadron_code));

-- The aircraft sub-query is itself filtered by the policy above.
DROP POLICY IF EXISTS engines_by_squadron ON engines;
CREATE POLICY engines_by_squadron ON engines TO vayu_app
  USING (EXISTS (SELECT 1 FROM aircraft a WHERE a.tail_no = engines.tail_no));

DROP POLICY IF EXISTS alerts_by_squadron ON alerts;
CREATE POLICY alerts_by_squadron ON alerts TO vayu_app
  USING (app_role() <> 'ADMIN' AND EXISTS (SELECT 1 FROM aircraft a WHERE a.tail_no = alerts.tail_no));

DROP POLICY IF EXISTS defects_by_squadron ON defects;
CREATE POLICY defects_by_squadron ON defects TO vayu_app
  USING (app_role() <> 'ADMIN' AND EXISTS (SELECT 1 FROM aircraft a WHERE a.tail_no = defects.tail_no));

DROP POLICY IF EXISTS tasks_by_squadron ON tasks;
CREATE POLICY tasks_by_squadron ON tasks TO vayu_app
  USING (app_role() <> 'ADMIN' AND EXISTS (SELECT 1 FROM aircraft a WHERE a.tail_no = tasks.tail_no));

-- 4. Hosted Supabase only: its auto-generated REST API serves the public schema to the "anon" and
--    "authenticated" roles. VAYU-READY never uses that API, so those roles get no access at all.
DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', r);
      EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I', r);
    END IF;
  END LOOP;
END $$;
