# Security: DB access and least privilege

Goal: backend uses a non-superuser role; analytics gets read-only; DB is not exposed publicly; secrets stay out of git.

## Roles
- `apm_app`: login, CRUD on app tables/views/sequences.
- `apm_readonly`: login, SELECT only (for CAGGs/analytics).

## Provisioning (first init)
- `docker/initdb/001_roles.sql` runs at first DB init (Timescale image). It creates roles with default passwords `apm_app_pass` and `apm_readonly_pass` and applies grants.
- After init, change passwords if needed and update your `.env` accordingly.

## Application credentials
- Use app creds in env:
  - `POSTGRES_APP_USER=apm_app`
  - `POSTGRES_APP_PASSWORD=apm_app_pass`
- Settings fallback to `POSTGRES_USER`/`POSTGRES_PASSWORD` but prefer the dedicated app user.
- Analytics clients can use `apm_readonly` (`apm_readonly_pass`), but the app should **not** use that account.

## Privileges
- Public create is revoked on schema `public`.
- `apm_app`: CONNECT, USAGE on schema, CRUD on tables, SELECT/USAGE on sequences, default privileges aligned.
- `apm_readonly`: CONNECT, USAGE on schema, SELECT on tables/sequences, default privileges aligned.
- No write for `apm_readonly`.

## Network
- For dev, the DB port is published in compose for local psql. For non-dev, avoid publishing the DB port; rely on the compose network only (remove/comment the `ports` mapping for `db`).
- Keep the backend and DB on the private docker network; do not expose DB publicly.

## Secrets
- `.env` is local-only; **do not commit** secrets.
- `.env.example` and `.env.docker` contain placeholders/defaults.
- CI uses safe defaults and the demo SQL job creates the Timescale extension and runs the script with non-superuser creds.

## Checks / acceptance
- App runs using `apm_app`, not a superuser.
- `apm_readonly` can read but cannot write.
- DB not published publicly in non-dev contexts.
