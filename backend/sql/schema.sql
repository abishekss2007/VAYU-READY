-- VAYU-READY database schema (PostgreSQL 16 + TimescaleDB).
-- Run as the database owner. The seed script runs this file, then rls.sql.
-- Timestamps are stored as UTC.

DROP TABLE IF EXISTS system_logs, incidents, breaches, grievances, settings, plans, audit_log, hangar_slots,
  indents, parts, tasks, defects, alerts, predictions, sensor_readings, engines, aircraft, users, squadrons, bases CASCADE;

CREATE TABLE bases (
  code text PRIMARY KEY,
  name text NOT NULL
);

CREATE TABLE squadrons (
  code text PRIMARY KEY,
  name text NOT NULL,
  base_code text NOT NULL REFERENCES bases(code),
  availability_target double precision NOT NULL DEFAULT 0.75
);

CREATE TABLE users (
  id serial PRIMARY KEY,
  email text NOT NULL UNIQUE,
  name text NOT NULL,
  role text NOT NULL CHECK (role IN ('CO','ENGO','TECH','LOGO','BRD','FSO','ADMIN','AUDITOR','HQ')),
  squadron_code text REFERENCES squadrons(code),
  password_hash text NOT NULL,
  otp_required boolean NOT NULL DEFAULT false,
  active boolean NOT NULL DEFAULT true,
  failed_logins integer NOT NULL DEFAULT 0,
  locked_until timestamp,
  notice_ack_at timestamp
);

CREATE TABLE aircraft (
  tail_no text PRIMARY KEY,
  type text NOT NULL,
  squadron_code text NOT NULL REFERENCES squadrons(code),
  flying_hours double precision NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'MC' CHECK (status IN ('MC','PMC','AOG','MAINT')),
  combat_ready boolean NOT NULL DEFAULT true,
  transport_ready boolean NOT NULL DEFAULT true,
  health_score integer NOT NULL DEFAULT 100,
  archived boolean NOT NULL DEFAULT false,
  archived_reason text
);

CREATE TABLE engines (
  id text PRIMARY KEY,
  tail_no text NOT NULL REFERENCES aircraft(tail_no),
  position integer NOT NULL CHECK (position IN (1, 2)),
  serial text NOT NULL,
  hours_since_overhaul double precision NOT NULL,
  overhaul_limit_hours double precision NOT NULL,
  cmapss_unit integer NOT NULL
);

CREATE TABLE sensor_readings (
  time timestamp NOT NULL,
  engine_id text NOT NULL,
  cycle integer NOT NULL,
  op_setting_1 double precision NOT NULL, op_setting_2 double precision NOT NULL, op_setting_3 double precision NOT NULL,
  s1 double precision NOT NULL, s2 double precision NOT NULL, s3 double precision NOT NULL,
  s4 double precision NOT NULL, s5 double precision NOT NULL, s6 double precision NOT NULL,
  s7 double precision NOT NULL, s8 double precision NOT NULL, s9 double precision NOT NULL,
  s10 double precision NOT NULL, s11 double precision NOT NULL, s12 double precision NOT NULL,
  s13 double precision NOT NULL, s14 double precision NOT NULL, s15 double precision NOT NULL,
  s16 double precision NOT NULL, s17 double precision NOT NULL, s18 double precision NOT NULL,
  s19 double precision NOT NULL, s20 double precision NOT NULL, s21 double precision NOT NULL,
  PRIMARY KEY (time, engine_id)
);

-- Sensor time-series lives in a TimescaleDB hypertable. If the extension is not
-- available (for example on a managed cloud copy), it stays a normal table.
DO $$
BEGIN
  CREATE EXTENSION IF NOT EXISTS timescaledb;
  PERFORM create_hypertable('sensor_readings', 'time', if_not_exists => true);
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'TimescaleDB not available (%); sensor_readings is a plain table.', SQLERRM;
END $$;

CREATE INDEX sensor_readings_engine_idx ON sensor_readings (engine_id, cycle DESC);

CREATE TABLE predictions (
  id serial PRIMARY KEY,
  engine_id text NOT NULL REFERENCES engines(id),
  time timestamp NOT NULL,
  rul_cycles double precision NOT NULL,
  anomaly_score double precision NOT NULL DEFAULT 0,
  model_version text NOT NULL,
  shap_top3 json NOT NULL DEFAULT '[]',
  trained_on text,
  dataset text,
  test_rmse double precision
);
CREATE INDEX predictions_engine_idx ON predictions (engine_id, time DESC);

CREATE TABLE alerts (
  id text PRIMARY KEY,
  tail_no text NOT NULL REFERENCES aircraft(tail_no),
  engine_id text,
  kind text NOT NULL CHECK (kind IN ('RUL','ANOMALY','OVERHAUL','SPARES','RECURRING')),
  severity text NOT NULL CHECK (severity IN ('Info','Warning','Critical')),
  message text NOT NULL,
  created_at timestamp NOT NULL,
  reviewed_by text,
  reviewed_at timestamp,
  decision text CHECK (decision IN ('Inspect','Schedule','FalseAlarm')),
  note text,
  escalated boolean NOT NULL DEFAULT false,
  model_version text
);

CREATE TABLE defects (
  id serial PRIMARY KEY,
  tail_no text NOT NULL REFERENCES aircraft(tail_no),
  text text NOT NULL,
  suggested_category text,
  confirmed_category text,
  system text,
  logged_by text NOT NULL,
  logged_at timestamp NOT NULL,
  status text NOT NULL DEFAULT 'Open'
);

CREATE TABLE tasks (
  id serial PRIMARY KEY,
  tail_no text NOT NULL REFERENCES aircraft(tail_no),
  title text NOT NULL,
  kind text NOT NULL DEFAULT 'scheduled',
  slot_start date NOT NULL,
  slot_end date NOT NULL,
  hangar text NOT NULL,
  assigned_to text,
  status text NOT NULL DEFAULT 'Scheduled',
  hours_spent double precision,
  completed_by text,
  signed_off_by text,
  engine_ids json NOT NULL DEFAULT '[]',
  part_no text
);

CREATE TABLE parts (
  part_no text PRIMARY KEY,
  name text NOT NULL,
  system text NOT NULL,
  stock integer NOT NULL,
  reorder_point integer NOT NULL,
  lead_time_days integer NOT NULL
);

CREATE TABLE indents (
  id text PRIMARY KEY,
  part_no text NOT NULL REFERENCES parts(part_no),
  tail_no text,
  qty integer NOT NULL DEFAULT 1,
  reason text NOT NULL,
  needed_by date NOT NULL,
  raised_by text NOT NULL,
  status text NOT NULL DEFAULT 'Raised' CHECK (status IN ('Raised','Approved','Received')),
  created_at timestamp NOT NULL,
  fitted boolean NOT NULL DEFAULT false
);

CREATE TABLE hangar_slots (
  id serial PRIMARY KEY,
  base_code text NOT NULL REFERENCES bases(code),
  day date NOT NULL,
  capacity integer NOT NULL
);

-- Append-only, hash-chained. hash = SHA-256 of ts|actor|role|action|detail|prev_hash
CREATE TABLE audit_log (
  id serial PRIMARY KEY,
  ts text NOT NULL,
  actor text NOT NULL,
  role text NOT NULL,
  action text NOT NULL,
  detail text NOT NULL,
  prev_hash text NOT NULL,
  hash text NOT NULL
);

CREATE TABLE plans (
  id serial PRIMARY KEY,
  squadron_code text NOT NULL,
  created_at timestamp NOT NULL,
  created_by text NOT NULL,
  status text NOT NULL DEFAULT 'Proposed',
  approved_by text,
  payload json NOT NULL
);

CREATE TABLE settings (
  key text PRIMARY KEY,
  value text NOT NULL
);

CREATE TABLE grievances (
  id serial PRIMARY KEY,
  kind text NOT NULL,
  raised_by text NOT NULL,
  text text NOT NULL,
  created_at timestamp NOT NULL,
  status text NOT NULL DEFAULT 'Open',
  response text,
  responded_by text,
  responded_at timestamp
);

CREATE TABLE breaches (
  id serial PRIMARY KEY,
  what_happened text NOT NULL,
  impact text NOT NULL,
  steps_taken text NOT NULL,
  affected_users json NOT NULL DEFAULT '[]',
  detected_at timestamp NOT NULL,
  report_due_at timestamp NOT NULL,
  users_informed_at timestamp,
  reported_at timestamp,
  recorded_by text NOT NULL
);

CREATE TABLE incidents (
  id serial PRIMARY KEY,
  incident_type text NOT NULL,
  description text NOT NULL,
  noticed_at timestamp NOT NULL,
  report_due_at timestamp NOT NULL,
  reported_at timestamp,
  recorded_by text NOT NULL
);

CREATE TABLE system_logs (
  id serial PRIMARY KEY,
  ts timestamp NOT NULL,
  level text NOT NULL,
  message text NOT NULL
);
