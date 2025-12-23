from __future__ import annotations

import os
import time
from dataclasses import dataclass

import psycopg
from django.core.management.base import BaseCommand, CommandError


@dataclass(frozen=True)
class HostTarget:
    host: str
    port: int


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _parse_host_entry(entry: str, default_port: int) -> HostTarget:
    raw = entry.strip()
    if not raw:
        raise CommandError("Empty host entry in host list")

    if raw.startswith("["):
        host_part, _, rest = raw[1:].partition("]")
        if not host_part:
            raise CommandError(f"Invalid host entry: {entry}")
        if not rest:
            return HostTarget(host_part, default_port)
        if not rest.startswith(":"):
            raise CommandError(f"Invalid host entry: {entry}")
        port_part = rest[1:]
    else:
        if ":" in raw:
            host_part, port_part = raw.rsplit(":", 1)
        else:
            host_part = raw
            port_part = str(default_port)

    try:
        port = int(port_part)
    except ValueError as exc:
        raise CommandError(f"Invalid port in host entry: {entry}") from exc

    return HostTarget(host_part, port)


def _resolve_hosts(raw_hosts: str | None, default_port: int) -> list[HostTarget]:
    raw = (raw_hosts or "").strip()
    if not raw:
        primary = _env("CLUSTER_DB_PRIMARY_HOST")
        replicas = _env("CLUSTER_DB_REPLICA_HOSTS")
        combined: list[str] = []
        if primary:
            combined.append(primary)
        if replicas:
            combined.extend([entry.strip() for entry in replicas.split(",") if entry.strip()])
        if combined:
            return [_parse_host_entry(entry, default_port) for entry in combined]

        host = _env("POSTGRES_HOST") or _env("DB_HOST") or "localhost"
        return [HostTarget(host, default_port)]

    entries = [entry.strip() for entry in raw.split(",") if entry.strip()]
    return [_parse_host_entry(entry, default_port) for entry in entries]


class Command(BaseCommand):
    help = "Check read/write connectivity to each cluster DB host."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hosts",
            default=None,
            help=(
                "Comma-separated host[:port] or [ipv6]:port list. "
                "Defaults to CLUSTER_DB_HOSTS, then "
                "CLUSTER_DB_PRIMARY_HOST/CLUSTER_DB_REPLICA_HOSTS."
            ),
        )
        parser.add_argument(
            "--timeout",
            type=float,
            default=None,
            help="Connect timeout in seconds (default: DB_CONNECT_TIMEOUT or 5).",
        )
        parser.add_argument(
            "--sslmode",
            default=None,
            help="Override SSL mode (default: DB_SSLMODE env var).",
        )

    def handle(self, *args, **options):
        default_port = int(_env("POSTGRES_PORT", "5432") or "5432")
        targets = _resolve_hosts(options.get("hosts") or _env("CLUSTER_DB_HOSTS"), default_port)

        db_name = _env("POSTGRES_DB") or _env("DB_NAME")
        db_user = _env("POSTGRES_APP_USER") or _env("POSTGRES_USER") or _env("DB_USER")
        db_password = (
            _env("POSTGRES_APP_PASSWORD") or _env("POSTGRES_PASSWORD") or _env("DB_PASSWORD")
        )

        if not db_name:
            raise CommandError("Missing POSTGRES_DB/DB_NAME.")
        if not db_user or not db_password:
            raise CommandError(
                "Missing DB user/password (POSTGRES_APP_USER/PASSWORD or POSTGRES_USER/PASSWORD)."
            )

        timeout = options.get("timeout") or float(_env("DB_CONNECT_TIMEOUT", "5") or "5")
        sslmode = options.get("sslmode") or _env("DB_SSLMODE")

        failures: list[str] = []

        for target in targets:
            params = {
                "host": target.host,
                "port": target.port,
                "dbname": db_name,
                "user": db_user,
                "password": db_password,
                "connect_timeout": timeout,
            }
            if sslmode:
                params["sslmode"] = sslmode

            start = time.monotonic()
            try:
                with psycopg.connect(**params) as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT 1;")
                        cursor.execute("SELECT pg_is_in_recovery();")
                        in_recovery = cursor.fetchone()[0]
                        row_count = None
                        if not in_recovery:
                            cursor.execute(
                                "CREATE TEMP TABLE IF NOT EXISTS apm_cluster_probe ("
                                "id serial PRIMARY KEY, payload text, "
                                "created_at timestamptz default now()"
                                ");"
                            )
                            cursor.execute(
                                "INSERT INTO apm_cluster_probe (payload) VALUES (%s);",
                                [f"probe@{target.host}:{target.port}"],
                            )
                            cursor.execute("SELECT COUNT(*) FROM apm_cluster_probe;")
                            row_count = cursor.fetchone()[0]
                elapsed_ms = int((time.monotonic() - start) * 1000)
                role_label = "replica" if in_recovery else "primary"
                details = (
                    f"role={role_label}, read-only"
                    if in_recovery
                    else f"role={role_label}, temp rows={row_count}"
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{target.host}:{target.port} ok ({details}, {elapsed_ms}ms)"
                    )
                )
            except Exception as exc:  # noqa: BLE001 - surface DB errors
                failures.append(f"{target.host}:{target.port}")
                self.stderr.write(self.style.ERROR(f"{target.host}:{target.port} failed: {exc}"))

        if failures:
            raise CommandError(f"{len(failures)} host(s) failed: {', '.join(failures)}")
