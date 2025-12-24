# Ansible Deployment (LAN / Single Host)

This project uses Ansible to deploy the **DATA / CONTROL / APP** stacks defined in `docker/cluster/*.yml`.
The current recommendation is **Ansible-only** for local LAN or single-host setups.

## What this does

- Installs Docker + Compose plugin (Debian/Ubuntu only).
- Ensures the repo exists on the target host.
- Renders `docker/cluster/.env.cluster` from variables (optional overwrite).
- Brings up the DATA, CONTROL, and APP stacks with the same env-file chain used in dev.
- Optional validation hooks for `check_cluster_dbs` and `pgbackrest info`.

## Prerequisites

- Ansible installed on the control machine.
- SSH access to the target host(s) (or `ansible_connection=local` for single-host).
- The repo present on each target host (set `repo_path` accordingly).

## Inventory (single-host LAN)

Edit `infra/ansible/inventory/hosts.ini`:

- `ansible_host` should be your LAN IP.
- Keep `ansible_connection=local` if you run the playbook on the same machine.
- Set `repo_path` to the repo location on the target host.

Example:

```
[apm_nodes]
apm-node ansible_host=192.168.0.127 ansible_user=apm ansible_connection=local

[data]
apm-node
[control]
apm-node
[app]
apm-node

[all:vars]
repo_path=/opt/apm-observability
cluster_env_overwrite=false
```

## Configure the cluster env

`docker/cluster/.env.cluster` is rendered from `infra/ansible/templates/env.cluster.j2`.
By default, Ansible **will not overwrite** an existing file. To force overwrite:

```
ansible-playbook -i infra/ansible/inventory/hosts.ini infra/ansible/site.yml \
  -e cluster_env_overwrite=true
```

Update values in `infra/ansible/group_vars/*.yml` or use Ansible Vault for secrets:

- `pgbackrest_cipher_pass`
- MinIO credentials
- DB passwords

## Run the deployment

```
ansible-playbook -i infra/ansible/inventory/hosts.ini infra/ansible/site.yml
```

## Optional validation

```
ansible-playbook -i infra/ansible/inventory/hosts.ini infra/ansible/site.yml \
  --tags validate -e run_validation=true
```

### Validation success indicators

- `check_cluster_dbs` reports a primary (writable) plus replicas (read-only).
- `pgbackrest --stanza=apm info` returns repository status without errors.
- Playbook exits with `failed=0`.

### Validation log script

Use the script below to capture a timestamped validation log:

```
scripts/ansible/validate.sh
```

If you use SSH keys, set `ANSIBLE_PRIVATE_KEY_FILE` before running the script.

## Moving to multiple machines later

- Add **real IPs** for DATA / CONTROL / APP in the inventory.
- Update `cluster_db_replica_hosts_list` in `group_vars/app.yml`.
- The playbooks remain the same; only inventory and vars change.
