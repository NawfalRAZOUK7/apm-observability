-- Roles and grants for least-privilege access
-- Adjust passwords in .env / .env.docker to match these defaults
-- Defaults: apm_app / apm_app_pass, apm_readonly / apm_readonly_pass

-- Create/alter app role (login)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'apm_app') THEN
    CREATE ROLE apm_app LOGIN PASSWORD 'apm_app_pass';
  ELSE
    ALTER ROLE apm_app WITH LOGIN PASSWORD 'apm_app_pass';
  END IF;
END $$;

-- Create/alter readonly role (login)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'apm_readonly') THEN
    CREATE ROLE apm_readonly LOGIN PASSWORD 'apm_readonly_pass';
  ELSE
    ALTER ROLE apm_readonly WITH LOGIN PASSWORD 'apm_readonly_pass';
  END IF;
END $$;

-- Revoke unsafe defaults
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON DATABASE apm FROM PUBLIC;

-- Grants for application role
GRANT CONNECT ON DATABASE apm TO apm_app;
GRANT USAGE ON SCHEMA public TO apm_app;
GRANT CREATE ON SCHEMA public TO apm_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO apm_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO apm_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO apm_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO apm_app;

-- Grants for readonly role (analytics/CAGGs)
GRANT CONNECT ON DATABASE apm TO apm_readonly;
GRANT USAGE ON SCHEMA public TO apm_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO apm_readonly;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO apm_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO apm_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO apm_readonly;

-- Optional: allow readonly role to refresh materialized views? (kept off by default)
-- GRANT REFRESH MATERIALIZED VIEW ON ALL MATERIALIZED VIEWS IN SCHEMA public TO apm_readonly;

-- Note: run-time ownership of application tables/views should remain with a maintainer role (e.g., apm)
-- Application should connect as apm_app; analytics consumers can use apm_readonly.
