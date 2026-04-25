#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

ENV_LINE_RE = re.compile(r"^([A-Z0-9_]+)=(.*)$")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_env_lines(path: Path) -> list[str]:
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


def _resolve_path(root: Path, path_str: str) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        return (root / path).resolve()
    return path


def _load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    suffix = path.suffix.lower()
    if suffix in {".json"}:
        return json.loads(path.read_text()) or {}
    if suffix in {".yml", ".yaml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "PyYAML is required for YAML configs. " "Install with: pip install pyyaml"
            ) from exc
        return yaml.safe_load(path.read_text()) or {}
    raise ValueError(f"Unsupported config format: {path}")


def _cfg_get(cfg: dict, *keys: str, default=None):
    cur = cfg
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _upsert_env(lines: list[str], key: str, value: str) -> None:
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


def _detect_local_ip() -> str | None:
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


def _parse_host_port(value: str, default_port: int) -> tuple[str, int]:
    if ":" in value:
        host, port_str = value.rsplit(":", 1)
        return host, int(port_str)
    return value, default_port


def _format_hosts(hosts: list[tuple[str, int]]) -> str:
    return ",".join(f"{host}:{port}" for host, port in hosts)


def _update_prometheus_targets(
    path: Path,
    app_ip: str,
    data_ip: str,
    control_ip: str,
    app_port: int = 18443,
    data_port: int = 9187,
    control_port: int = 9100,
    app_scheme: str = "https",
    app_insecure_skip_verify: bool = True,
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

    def ensure_django_tls() -> None:
        in_job = False
        job_indent = ""
        has_scheme = False
        has_tls = False
        has_tls_setting = False
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("- job_name:"):
                in_job = "django" in stripped
                job_indent = line.split("- job_name:")[0]
                has_scheme = False
                has_tls = False
                has_tls_setting = False
                continue
            if not in_job:
                continue
            if stripped.startswith("- job_name:"):
                in_job = False
                continue
            if stripped.startswith("scheme:"):
                lines[idx] = f"{job_indent}  scheme: {app_scheme}"
                has_scheme = True
            if stripped.startswith("tls_config:"):
                lines[idx] = f"{job_indent}  tls_config:"
                has_tls = True
            if stripped.startswith("insecure_skip_verify:"):
                value = "true" if app_insecure_skip_verify else "false"
                lines[idx] = f"{job_indent}    insecure_skip_verify: {value}"
                has_tls_setting = True
            if stripped.startswith("static_configs:"):
                insert_lines: list[str] = []
                if not has_scheme:
                    insert_lines.append(f"{job_indent}  scheme: {app_scheme}")
                if app_scheme == "https":
                    if not has_tls:
                        insert_lines.append(f"{job_indent}  tls_config:")
                        if app_insecure_skip_verify:
                            insert_lines.append(f"{job_indent}    insecure_skip_verify: true")
                    elif has_tls and not has_tls_setting and app_insecure_skip_verify:
                        insert_lines.append(f"{job_indent}    insecure_skip_verify: true")
                if insert_lines:
                    lines[idx:idx] = insert_lines
                break

    replace_target("django", f"{app_ip}:{app_port}")
    replace_target("postgres_exporter", f"{data_ip}:{data_port}")
    replace_target("node_exporter", f"{control_ip}:{control_port}")
    ensure_django_tls()

    path.write_text("\n".join(lines) + "\n")


def _backup(path: Path) -> Path:
    stamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_suffix(path.suffix + f".bak.{stamp}")
    backup.write_text(path.read_text())
    return backup


def _build_replicas(
    replica_args: list[str],
    base_port: int,
    count: int,
) -> list[tuple[str, int]]:
    if replica_args:
        replicas: list[tuple[str, int]] = []
        for value in replica_args:
            replicas.append(_parse_host_port(value, base_port))
        return replicas
    replicas = []
    for idx in range(count):
        replicas.append(("", base_port + idx))
    return replicas


def _resolve_ips(args: argparse.Namespace, env: dict[str, str]) -> tuple[str, str, str]:
    data_ip = args.data_ip or env.get("DATA_NODE_IP")
    control_ip = args.control_ip or env.get("CONTROL_NODE_IP")
    app_ip = args.app_ip or env.get("APP_NODE_IP")
    return data_ip or "", control_ip or "", app_ip or ""


def main() -> int:
    root = _repo_root()
    default_env = root / "docker" / "cluster" / ".env.cluster"
    default_template = root / "docker" / "cluster" / ".env.cluster.example"
    default_prom = root / "docker" / "monitoring" / "prometheus.yml"

    argv = sys.argv[1:]
    if argv and argv[0] in {"single", "multi"}:
        argv = ["--mode", argv[0]] + argv[1:]

    parser = argparse.ArgumentParser(
        description="Switch cluster env between single-machine and multi-node modes.",
    )
    parser.add_argument("--mode", choices=["single", "multi"])
    parser.add_argument("--config", default=None, help="Path to YAML/JSON config file.")
    parser.add_argument("--env-file", default=str(default_env))
    parser.add_argument("--template", default=str(default_template))
    parser.add_argument("--prometheus", default=str(default_prom))
    parser.add_argument("--no-prometheus", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--primary-port", type=int, default=None)
    parser.add_argument("--primary-host", default=None)
    parser.add_argument("--ip", default=None, help="Single host IP (DATA/CONTROL/APP).")
    parser.add_argument(
        "--container-ip",
        default=None,
        help="Single host IP/hostname used from containers (defaults to --ip).",
    )
    parser.add_argument("--app-https-port", type=int, default=None)
    parser.add_argument("--replica-count", type=int, default=2)
    parser.add_argument("--replica-base-port", type=int, default=25433)
    parser.add_argument("--replica", action="append", default=[])
    parser.add_argument("--data-ip", default=None)
    parser.add_argument("--control-ip", default=None)
    parser.add_argument("--app-ip", default=None)
    parser.add_argument("--allow-single-ip-in-multi", action="store_true")

    args = parser.parse_args(argv)

    config: dict = {}
    if args.config:
        config_path = _resolve_path(root, args.config)
        config = _load_config(config_path)
    else:
        config_path = None

    mode = args.mode or _cfg_get(config, "mode")
    if mode not in {"single", "multi"}:
        print("Missing or invalid mode. Use --mode or set mode in config.", file=sys.stderr)
        return 1

    env_path = _resolve_path(
        root,
        args.env_file or _cfg_get(config, "env_file", default=str(default_env)),
    )
    template_path = _resolve_path(
        root,
        args.template or _cfg_get(config, "template", default=str(default_template)),
    )
    prom_path = _resolve_path(
        root,
        args.prometheus or _cfg_get(config, "prometheus", default=str(default_prom)),
    )

    update_prom = not args.no_prometheus
    if _cfg_get(config, "update_prometheus", default=True) is False:
        update_prom = False
    backup_env = not args.no_backup
    if _cfg_get(config, "backup_env", default=True) is False:
        backup_env = False

    if env_path.exists():
        lines = _read_env_lines(env_path)
    elif template_path.exists():
        lines = _read_env_lines(template_path)
    else:
        print(f"Missing env file/template: {env_path} or {template_path}", file=sys.stderr)
        return 1

    env = _parse_env(lines)

    if mode == "single":
        public_ip = (
            args.ip
            or _cfg_get(config, "single", "ip")
            or env.get("DATA_NODE_IP")
            or _detect_local_ip()
        )
        if not public_ip:
            print("Unable to determine IP; pass --ip.", file=sys.stderr)
            return 1
        container_ip = (
            args.container_ip
            or _cfg_get(config, "single", "container_ip")
            or _cfg_get(config, "single", "container_host")
            or public_ip
        )
        data_ip = control_ip = app_ip = container_ip
        app_https_port = (
            args.app_https_port
            or _cfg_get(config, "single", "app_https_port")
            or _cfg_get(config, "monitoring", "app_https_port")
            or 18443
        )
        base_port = args.replica_base_port or _cfg_get(
            config,
            "single",
            "replica_base_port",
            default=25433,
        )
        replica_list = args.replica or _cfg_get(config, "single", "replicas", default=[])
        replica_count = args.replica_count or _cfg_get(config, "single", "replica_count", default=2)
        replicas = _build_replicas(replica_list, base_port, replica_count)
        replicas = [(container_ip if host == "" else host, port) for host, port in replicas]
        primary_port = args.primary_port or _cfg_get(config, "single", "primary_port")
        if primary_port is None:
            if "CLUSTER_DB_PRIMARY_HOST" in env:
                _, primary_port = _parse_host_port(env["CLUSTER_DB_PRIMARY_HOST"], 25432)
            else:
                primary_port = 25432
        primary_host = (
            args.primary_host
            or _cfg_get(config, "single", "primary_host")
            or f"{container_ip}:{primary_port}"
        )
        data_host_gateway = _cfg_get(config, "single", "host_gateway") or "host-gateway"
        control_host_gateway = data_host_gateway
    else:
        data_ip = (
            args.data_ip or _cfg_get(config, "multi", "data_ip") or env.get("DATA_NODE_IP") or ""
        )
        control_ip = (
            args.control_ip
            or _cfg_get(config, "multi", "control_ip")
            or env.get("CONTROL_NODE_IP")
            or ""
        )
        app_ip = args.app_ip or _cfg_get(config, "multi", "app_ip") or env.get("APP_NODE_IP") or ""
        app_https_port = (
            args.app_https_port
            or _cfg_get(config, "multi", "app_https_port")
            or _cfg_get(config, "monitoring", "app_https_port")
            or 443
        )
        missing = [
            name
            for name, value in [
                ("data-ip", data_ip),
                ("control-ip", control_ip),
                ("app-ip", app_ip),
            ]
            if not value
        ]
        if missing:
            print(f"Missing required IPs for multi mode: {', '.join(missing)}", file=sys.stderr)
            return 1
        allow_single = args.allow_single_ip_in_multi or _cfg_get(
            config,
            "multi",
            "allow_single_ip",
            default=False,
        )
        if len({data_ip, control_ip, app_ip}) < 2 and not allow_single:
            print(
                "Multi mode requires at least two distinct node IPs. "
                "Use --allow-single-ip-in-multi or set multi.allow_single_ip: true "
                "for single-host dev.",
                file=sys.stderr,
            )
            return 1
        primary_port = args.primary_port or _cfg_get(config, "multi", "primary_port")
        if primary_port is None:
            if "CLUSTER_DB_PRIMARY_HOST" in env:
                _, primary_port = _parse_host_port(env["CLUSTER_DB_PRIMARY_HOST"], 5432)
            else:
                primary_port = 5432
        primary_host = (
            args.primary_host
            or _cfg_get(config, "multi", "primary_host")
            or f"{data_ip}:{primary_port}"
        )
        replica_args = (
            args.replica
            or _cfg_get(config, "multi", "replicas", default=[])
            or (
                []
                if "CLUSTER_DB_REPLICA_HOSTS" not in env
                else env["CLUSTER_DB_REPLICA_HOSTS"].split(",")
            )
        )
        replicas = []
        for value in replica_args:
            value = value.strip()
            if not value:
                continue
            replicas.append(_parse_host_port(value, 5432))
        data_host_gateway = data_ip
        control_host_gateway = control_ip

    replica_hosts = _format_hosts(replicas)
    cluster_hosts = ",".join(filter(None, [primary_host, replica_hosts])).strip(",")

    updates = {
        "DATA_NODE_IP": data_ip,
        "CONTROL_NODE_IP": control_ip,
        "APP_NODE_IP": app_ip,
        "DATA_NODE_HOST_GATEWAY": data_host_gateway,
        "CONTROL_NODE_HOST_GATEWAY": control_host_gateway,
        "CLUSTER_DB_PRIMARY_HOST": primary_host,
        "CLUSTER_DB_REPLICA_HOSTS": replica_hosts,
        "CLUSTER_DB_HOSTS": cluster_hosts,
    }

    if mode == "single":
        updates["CLUSTER_DATA_DB_REPLICA1_HOST_PORT"] = str(base_port)
        updates["CLUSTER_DATA_DB_REPLICA2_HOST_PORT"] = str(base_port + 1)

    for key, value in updates.items():
        _upsert_env(lines, key, value)

    if args.dry_run:
        for key, value in updates.items():
            print(f"{key}={value}")
        return 0

    if env_path.exists() and backup_env:
        backup = _backup(env_path)
        print(f"Backup: {backup}")

    env_path.write_text("\n".join(lines) + "\n")
    print(f"Updated {env_path}")

    if update_prom:
        _update_prometheus_targets(
            prom_path,
            app_ip=app_ip,
            data_ip=data_ip,
            control_ip=control_ip,
            app_port=int(app_https_port),
            app_scheme="https",
            app_insecure_skip_verify=True,
        )
        print(f"Updated {prom_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
