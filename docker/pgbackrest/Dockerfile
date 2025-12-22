# docker/pgbackrest/Dockerfile
# Build pgBackRest from source (pinned) so it supports newer PostgreSQL catalogs.
#
# NOTE:
# - Your previous pgBackRest binary was too old and failed with:
#   VersionNotSupportedError unexpected control/catalog version.
# - This Dockerfile builds pgBackRest with meson/ninja.

ARG PGBACKREST_VERSION=2.57.0

FROM debian:bookworm-slim AS build
ARG PGBACKREST_VERSION

RUN set -eux; \
  apt-get update; \
  apt-get install -y --no-install-recommends \
    ca-certificates wget \
    python3-distutils meson ninja-build gcc pkg-config \
    libpq-dev libssl-dev libxml2-dev liblz4-dev libzstd-dev libbz2-dev zlib1g-dev libyaml-dev libssh2-1-dev \
  ; \
  rm -rf /var/lib/apt/lists/*

RUN set -eux; \
  mkdir -p /build; \
  wget -q -O - "https://github.com/pgbackrest/pgbackrest/archive/release/${PGBACKREST_VERSION}.tar.gz" \
    | tar zx -C /build

# Meson: meson setup <builddir> <sourcedir>
RUN set -eux; \
  meson setup /build/pgbackrest /build/pgbackrest-release-${PGBACKREST_VERSION}; \
  ninja -C /build/pgbackrest

FROM debian:bookworm-slim

RUN set -eux; \
  apt-get update; \
  apt-get install -y --no-install-recommends \
    ca-certificates curl openssh-client postgresql-client \
    libpq5 libssl3 libxml2 liblz4-1 libzstd1 libbz2-1.0 zlib1g libyaml-0-2 libssh2-1 \
  ; \
  rm -rf /var/lib/apt/lists/*

# pgBackRest binary
COPY --from=build /build/pgbackrest/src/pgbackrest /usr/local/bin/pgbackrest

# Optional: MinIO client for troubleshooting
RUN set -eux; \
  curl -fsSL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc; \
  chmod 755 /usr/local/bin/mc /usr/local/bin/pgbackrest

RUN set -eux; \
  mkdir -p /etc/pgbackrest /var/lib/pgbackrest /var/log/pgbackrest /root/.ssh; \
  chmod 700 /root/.ssh

COPY docker/pgbackrest/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 755 /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sleep", "infinity"]
