from __future__ import annotations

import os


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_bool(name: str, default: bool = False) -> bool:
    value = env(name, "")
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "y", "on"}


def env_csv(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


def split_host_port(raw: str, default_port: int) -> tuple[str, int]:
    value = raw.strip() if raw else ""
    if not value:
        return "localhost", default_port

    if value.startswith("["):
        host_part, _, rest = value[1:].partition("]")
        if not host_part:
            raise ValueError(f"Invalid host entry: {raw}")
        if not rest:
            return host_part, default_port
        if not rest.startswith(":"):
            raise ValueError(f"Invalid host entry: {raw}")
        port_part = rest[1:]
    else:
        if ":" in value:
            host_part, port_part = value.rsplit(":", 1)
        else:
            host_part = value
            port_part = str(default_port)

    try:
        port = int(port_part)
    except ValueError as exc:
        raise ValueError(f"Invalid port in host entry: {raw}") from exc

    return host_part, port


def parse_host_list(raw: str, default_port: int) -> list[tuple[str, int]]:
    entries = [entry.strip() for entry in raw.split(",") if entry.strip()]
    return [split_host_port(entry, default_port) for entry in entries]
