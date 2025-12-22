-- docker/initdb/001_roles.sql
-- Create application roles (idempotent) + grants.
--
-- Notes:
-- - This runs only on FIRST database initialization when mounted into
--   /docker-entrypoint-initdb.d (main stack).
-- - Passwords below are DEV defaults. For production, avoid hardcoding.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'apm_app') THEN
    CREATE ROLE apm_app LOGIN PASSWORD 'apm_app_pass';
  ELSE
    ALTER ROLE apm_app LOGIN PASSWORD 'apm_app_pass';
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'apm_readonly') THEN
    CREATE ROLE apm_readonly LOGIN PASSWORD 'apm_readonly_pass';
  ELSE
    ALTER ROLE apm_readonly LOGIN PASSWORD 'apm_readonly_pass';
  END IF;
END
$$;

-- Allow connections to the current DB
GRANT CONNECT ON DATABASE apm TO apm_app;
GRANT CONNECT ON DATABASE apm TO apm_readonly;

-- Schema privileges (public schema)
GRANT USAGE ON SCHEMA public TO apm_app;
GRANT USAGE ON SCHEMA public TO apm_readonly;

-- Read/write role: CRUD on tables + sequences + execute functions
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO apm_app;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO apm_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO apm_app;

-- Read-only role
GRANT SELECT ON ALL TABLES IN SCHEMA public TO apm_readonly;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO apm_readonly;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO apm_readonly;

-- Default privileges for future objects created by the DB owner (POSTGRES_USER).
-- In your docker-compose.yml, that owner is 'apm'.
ALTER DEFAULT PRIVILEGES FOR ROLE apm IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO apm_app;
ALTER DEFAULT PRIVILEGES FOR ROLE apm IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO apm_app;
ALTER DEFAULT PRIVILEGES FOR ROLE apm IN SCHEMA public
  GRANT EXECUTE ON FUNCTIONS TO apm_app;

ALTER DEFAULT PRIVILEGES FOR ROLE apm IN SCHEMA public
  GRANT SELECT ON TABLES TO apm_readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE apm IN SCHEMA public
  GRANT SELECT ON SEQUENCES TO apm_readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE apm IN SCHEMA public
  GRANT EXECUTE ON FUNCTIONS TO apm_readonly;
