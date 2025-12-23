# docker/db/Dockerfile
# TimescaleDB with pgBackRest installed for WAL archiving.

ARG PGBACKREST_VERSION=2.57.0
ARG PGVECTOR_VERSION=0.7.4

FROM alpine:3.21 AS pgbackrest-build
ARG PGBACKREST_VERSION

RUN set -eux; \
  apk add --no-cache \
    bash ca-certificates wget \
    build-base meson ninja python3 py3-setuptools pkgconf \
    postgresql-dev openssl-dev libxml2-dev lz4-dev zstd-dev bzip2-dev zlib-dev yaml-dev libssh2-dev

RUN set -eux; \
  mkdir -p /build; \
  wget -q -O - "https://github.com/pgbackrest/pgbackrest/archive/release/${PGBACKREST_VERSION}.tar.gz" \
    | tar zx -C /build

RUN set -eux; \
  meson setup /build/pgbackrest /build/pgbackrest-release-${PGBACKREST_VERSION}; \
  ninja -C /build/pgbackrest

FROM timescale/timescaledb:latest-pg16 AS pgvector-build
ARG PGVECTOR_VERSION

USER root

RUN set -eux; \
  apk add --no-cache --virtual .build-deps \
    build-base \
    git \
    postgresql-dev

RUN set -eux; \
  git clone --branch "v${PGVECTOR_VERSION}" --depth 1 \
    https://github.com/pgvector/pgvector.git /tmp/pgvector; \
  make -C /tmp/pgvector; \
  make -C /tmp/pgvector install DESTDIR=/pgvector-install; \
  rm -rf /tmp/pgvector

FROM timescale/timescaledb:latest-pg16

USER root

RUN set -eux; \
  apk add --no-cache \
    ca-certificates \
    libpq openssl libxml2 lz4 zstd bzip2-dev zlib yaml libssh2; \
  ln -sf /usr/lib/libbz2.so /usr/lib/libbz2.so.1

COPY --from=pgvector-build /pgvector-install /
COPY --from=pgbackrest-build /build/pgbackrest/src/pgbackrest /usr/local/bin/pgbackrest

RUN set -eux; \
  chmod 755 /usr/local/bin/pgbackrest; \
  mkdir -p /etc/pgbackrest /var/lib/pgbackrest /var/log/pgbackrest; \
  chown -R postgres:postgres /etc/pgbackrest /var/lib/pgbackrest /var/log/pgbackrest

USER postgres
