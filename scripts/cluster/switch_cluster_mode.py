#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


ENV_LINE_RE = re.compile(r"^([A-Z0-9_]+)=(.*)$")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_env_lines(path: Path) -> List[str]:
    return path.read_text().splitlines()


def _parse_env(lines: Iterable[str]) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in lines:
        match = ENV_LINE_RE.match(line.strip())
        if not match:
            continue
        key, value = match.groups()
        env[key] = value
    return env


def _upsert_env(lines: List[str], key: str, value: str) -> None:
    updated = False
    for idx, line in enumerate(lines):
        match = ENV_LINE_RE.match(line.strip())
        if not match:
            continue
        if match.group(1) == key:
            lines[idx] = f"{key}={value}"
            updated = True
    if not updated:
        lines.append(f"{key}={value}")


def _detect_local_ip() -> Optional[str]:
    commands = [
        ["ipconfig", "getifaddr", "en0"],
        ["ipconfig", "getifaddr", "en1"],
        ["hostname", "-I"],
    ]
    for cmd in commands:
        try:
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        except FileNotFoundError:
            continue
        if result.returncode != 0:
            continue
        out = result.stdout.strip()
        if not out:
            continue
        return out.split()[0]
    return None


def _parse_host_port(value: str, default_port: int) -> Tuple[str, int]:
    if ":" in value:
        host, port_str = value.rsplit(":", 1)
        return host, int(port_str)
    return value, default_port


def _format_hosts(hosts: List[Tuple[str, int]]) -> str:
    return ",".join(f"{host}:{port}" for host, port in hosts)


def _update_prometheus_targets(
    path: Path,
    app_ip: str,
    data_ip: str,
    control_ip: str,
    app_port: int = 28000,
    data_port: int = 9187,
    control_port: int = 9100,
) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Prometheus config not found: {path}")

    lines = path.read_text().splitlines()

    def replace_target(job: str, target: str) -> None:
        in_job = False
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("- job_name:"):
                in_job = job in stripped
                continue
            if not in_job:
                continue
            if "job_name:" in stripped:
                in_job = False
                continue
            if "targets:" in stripped:
                indent = line.split("targets:")[0]
                lines[idx] = f'{indent}targets: ["{target}"]'
                return

    replace_target("django", f"{app_ip}:{app_port}")
    replace_target("postgres_exporter", f"{data_ip}:{data_port}")
    replace_target("node_exporter", f"{control_ip}:{control_port}")

    path.write_text("\n".join(lines) + "\n")


def _backup(path: Path) -> Path:
    stamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_suffix(path.suffix + f".bak.{stamp}")
    backup.write_text(path.read_text())
    return backup


def _build_replicas(
    replica_args: List[str],
    base_port: int,
    count: int,
) -> List[Tuple[str, int]]:
    if replica_args:
        replicas: List[Tuple[str, int]] = []
        for value in replica_args:
            replicas.append(_parse_host_port(value, base_port))
        return replicas
    replicas = []
    for idx in range(count):
        replicas.append(("", base_port + idx))
    return replicas


def _resolve_ips(args: argparse.Namespace, env: dict[str, str]) -> Tuple[str, str, str]:
    data_ip = args.data_ip or env.get("DATA_NODE_IP")
    control_ip = args.control_ip or env.get("CONTROL_NODE_IP")
    app_ip = args.app_ip or env.get("APP_NODE_IP")
    return data_ip or "", control_ip or "", app_ip or ""


def main() -> int:
    root = _repo_root()
    default_env = root / "docker" / "cluster" / ".env.cluster"
    default_template = root / "docker" / "cluster" / ".env.cluster.example"
    default_prom = root / "docker" / "monitoring" / "prometheus.yml"

    parser = argparse.ArgumentParser(
        description="Switch cluster env between single-machine and multi-node modes.",
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--env-file", default=str(default_env))
    common.add_argument("--template", default=str(default_template))
    common.add_argument("--prometheus", default=str(default_prom))
    common.add_argument("--no-prometheus", action="store_true")
    common.add_argument("--no-backup", action="store_true")
    common.add_argument("--dry-run", action="store_true")
    common.add_argument("--primary-port", type=int, default=None)
    common.add_argument("--primary-host", default=None)

    single = sub.add_parser("single", parents=[common], help="Single-machine LAN mode.")
    single.add_argument("--ip", default=None, help="Single host IP (DATA/CONTROL/APP).")
    single.add_argument("--replica-count", type=int, default=2)
    single.add_argument("--replica-base-port", type=int, default=25433)
    single.add_argument("--replica", action="append", default=[])

    multi = sub.add_parser("multi", parents=[common], help="Multi-node LAN mode.")
    multi.add_argument("--data-ip", default=None)
    multi.add_argument("--control-ip", default=None)
    multi.add_argument("--app-ip", default=None)
    multi.add_argument("--replica", action="append", default=[])

    args = parser.parse_args()

    env_path = Path(args.env_file)
    template_path = Path(args.template)
    prom_path = Path(args.prometheus)

    if env_path.exists():
        lines = _read_env_lines(env_path)
    elif template_path.exists():
        lines = _read_env_lines(template_path)
    else:
        print(f"Missing env file/template: {env_path} or {template_path}", file=sys.stderr)
        return 1

    env = _parse_env(lines)

    if args.mode == "single":
        ip = args.ip or env.get("DATA_NODE_IP") or _detect_local_ip()
        if not ip:
            print("Unable to determine IP; pass --ip.", file=sys.stderr)
            return 1
        data_ip = control_ip = app_ip = ip
        base_port = args.replica_base_port
        replicas = _build_replicas(args.replica, base_port, args.replica_count)
        replicas = [(ip if host == "" else host, port) for host, port in replicas]
        primary_port = args.primary_port
        if primary_port is None:
            if "CLUSTER_DB_PRIMARY_HOST" in env:
                _, primary_port = _parse_host_port(env["CLUSTER_DB_PRIMARY_HOST"], 25432)
            else:
                primary_port = 25432
        primary_host = args.primary_host or f"{ip}:{primary_port}"
    else:
        data_ip, control_ip, app_ip = _resolve_ips(args, env)
        missing = [name for name, value in [("data-ip", data_ip), ("control-ip", control_ip), ("app-ip", app_ip)] if not value]
        if missing:
            print(f"Missing required IPs for multi mode: {', '.join(missing)}", file=sys.stderr)
            return 1
        primary_port = args.primary_port
        if primary_port is None:
            if "CLUSTER_DB_PRIMARY_HOST" in env:
                _, primary_port = _parse_host_port(env["CLUSTER_DB_PRIMARY_HOST"], 5432)
            else:
                primary_port = 5432
        primary_host = args.primary_host or f"{data_ip}:{primary_port}"
        replica_args = args.replica or ([] if "CLUSTER_DB_REPLICA_HOSTS" not in env else env["CLUSTER_DB_REPLICA_HOSTS"].split(","))
        replicas = []
        for value in replica_args:
            value = value.strip()
            if not value:
                continue
            replicas.append(_parse_host_port(value, 5432))

    replica_hosts = _format_hosts(replicas)
    cluster_hosts = ",".join(filter(None, [primary_host, replica_hosts])).strip(",")

    updates = {
        "DATA_NODE_IP": data_ip,
        "CONTROL_NODE_IP": control_ip,
        "APP_NODE_IP": app_ip,
        "CLUSTER_DB_PRIMARY_HOST": primary_host,
        "CLUSTER_DB_REPLICA_HOSTS": replica_hosts,
        "CLUSTER_DB_HOSTS": cluster_hosts,
    }

    if args.mode == "single":
        updates["CLUSTER_DATA_DB_REPLICA1_HOST_PORT"] = str(args.replica_base_port)
        updates["CLUSTER_DATA_DB_REPLICA2_HOST_PORT"] = str(args.replica_base_port + 1)

    for key, value in updates.items():
        _upsert_env(lines, key, value)

    if args.dry_run:
        for key, value in updates.items():
            print(f"{key}={value}")
        return 0

    if env_path.exists() and not args.no_backup:
        backup = _backup(env_path)
        print(f"Backup: {backup}")

    env_path.write_text("\n".join(lines) + "\n")
    print(f"Updated {env_path}")

    if not args.no_prometheus:
        _update_prometheus_targets(prom_path, app_ip=app_ip, data_ip=data_ip, control_ip=control_ip)
        print(f"Updated {prom_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
