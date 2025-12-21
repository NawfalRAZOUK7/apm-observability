
FROM debian:bookworm-slim

# Copy entrypoint script for CA cert workaround
COPY entrypoint.copy-ca.sh /pgbackrest/entrypoint.copy-ca.sh
RUN chmod +x /pgbackrest/entrypoint.copy-ca.sh

RUN apt-get update \
  && apt-get install -y --no-install-recommends gnupg2 wget lsb-release ca-certificates curl cron postgresql-client openssh-client sshpass \
  && echo "deb http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
  && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql-archive-keyring.gpg \
  && echo "deb [signed-by=/usr/share/keyrings/postgresql-archive-keyring.gpg] http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
  && apt-get update \
  && apt-get install -y --no-install-recommends pgbackrest \
  && rm -rf /var/lib/apt/lists/*


# pgBackRest standard dirs
RUN mkdir -p /etc/pgbackrest /var/log/pgbackrest /var/lib/pgbackrest /var/lib/pgbackrest-hot \
  && rm -rf /tmp/minio-ca-cert-file.crt \
  && rm -rf /minio-ca.pem /tmp/minio-ca.pem

# Cron schedule
COPY pgbackrest-cron /etc/cron.d/pgbackrest
RUN chmod 0644 /etc/cron.d/pgbackrest && crontab /etc/cron.d/pgbackrest

CMD ["cron", "-f"]