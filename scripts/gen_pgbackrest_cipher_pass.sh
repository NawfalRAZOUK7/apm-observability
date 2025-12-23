#!/usr/bin/env bash
set -euo pipefail

tmp_dir="$(mktemp -d)"
key_path="${tmp_dir}/pgbackrest_cipher"

ssh-keygen -q -t ed25519 -N "" -f "$key_path" >/dev/null
sha256sum "$key_path" | awk '{print $1}'

rm -rf "$tmp_dir"
