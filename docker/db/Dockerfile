
# Use Debian-based Timescale for robust OpenSSH and logging support

FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive



# Install PostgreSQL 14, TimescaleDB, pgBackRest, OpenSSH, and rsyslog
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    gnupg2 wget lsb-release ca-certificates curl \
    locales openssh-server pgbackrest postgresql-common \
  && echo "deb http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
  && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql-archive-keyring.gpg \
  && echo "deb [signed-by=/usr/share/keyrings/postgresql-archive-keyring.gpg] http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
  && echo "deb [signed-by=/usr/share/keyrings/timescaledb-archive-keyring.gpg] https://packagecloud.io/timescale/timescaledb/debian/ bookworm main" > /etc/apt/sources.list.d/timescaledb.list \
  && curl -fsSL https://packagecloud.io/timescale/timescaledb/gpgkey | gpg --dearmor -o /usr/share/keyrings/timescaledb-archive-keyring.gpg \
  && apt-get update \
  && apt-get install -y postgresql-14 timescaledb-2-postgresql-14 \
  && rm -rf /var/lib/apt/lists/* \
  && sed -i '/en_US.utf8/d' /etc/locale.gen \
  && echo 'C.UTF-8 UTF-8' >> /etc/locale.gen \
  && locale-gen \
  && pg_dropcluster --stop 14 main \
  && su - postgres -c "pg_createcluster --locale C.UTF-8 14 main"

# Set default locale for PostgreSQL initdb
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Create standard pgBackRest dirs and ensure postgres can write logs/locks if needed
RUN mkdir -p /etc/pgbackrest /var/log/pgbackrest /var/lib/pgbackrest /var/run/sshd /var/lib/postgresql/data \
  && chown -R postgres:postgres /etc/pgbackrest /var/log/pgbackrest /var/lib/pgbackrest /var/lib/postgresql

# Set correct permissions for postgres home
RUN chmod 700 /var/lib/postgresql

# Generate SSH host keys at build time
RUN ssh-keygen -A

# Patch any default postgresql.conf to use C.utf8 locale if present (for first init)
RUN if [ -f /var/lib/postgresql/data/postgresql.conf ]; then \
    sed -i 's/en_US.utf8/C.utf8/g' /var/lib/postgresql/data/postgresql.conf; \
  fi

# Enable SSH server and syslog on container start
COPY db/entrypoint_with_sshd.sh /usr/local/bin/entrypoint_with_sshd.sh
RUN chmod +x /usr/local/bin/entrypoint_with_sshd.sh

ENTRYPOINT ["/usr/local/bin/entrypoint_with_sshd.sh"]

# Create standard pgBackRest dirs and ensure postgres can write logs/locks if needed
RUN mkdir -p /etc/pgbackrest /var/log/pgbackrest /var/lib/pgbackrest /var/run/sshd \
  && chown -R postgres:postgres /etc/pgbackrest /var/log/pgbackrest /var/lib/pgbackrest

# Set correct permissions for postgres home
RUN chown -R postgres:postgres /var/lib/postgresql && chmod 700 /var/lib/postgresql

# Generate SSH host keys at build time
RUN ssh-keygen -A

# Enable SSH server and syslog on container start
COPY db/entrypoint_with_sshd.sh /usr/local/bin/entrypoint_with_sshd.sh
RUN chmod +x /usr/local/bin/entrypoint_with_sshd.sh

ENTRYPOINT ["/usr/local/bin/entrypoint_with_sshd.sh"]

USER root

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    openssh-server \
    rsyslog \
    pgbackrest \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Create standard pgBackRest dirs and ensure postgres can write logs/locks if needed
RUN mkdir -p /etc/pgbackrest /var/log/pgbackrest /var/lib/pgbackrest /var/run/sshd \
  && chown -R postgres:postgres /etc/pgbackrest /var/log/pgbackrest /var/lib/pgbackrest

# Set correct permissions for postgres home
RUN chown -R postgres:postgres /var/lib/postgresql && chmod 700 /var/lib/postgresql

# Generate SSH host keys at build time
RUN ssh-keygen -A

# Enable SSH server and syslog on container start
COPY db/entrypoint_with_sshd.sh /usr/local/bin/entrypoint_with_sshd.sh
RUN chmod +x /usr/local/bin/entrypoint_with_sshd.sh

ENTRYPOINT ["/usr/local/bin/entrypoint_with_sshd.sh"]
