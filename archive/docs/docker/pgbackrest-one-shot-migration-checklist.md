# **pgBackRest One-Shot Container Migration Checklist**

## **Overview**

Convert pgBackRest from a persistent service to a one-shot container for on-demand backup/restore operations. This improves resource efficiency and follows best practices for backup tools.

## **Code Changes Required**

### **1. Update `docker-compose.backup.yml`**

- [x] **Remove persistent command**: Delete `command: tail -f /dev/null` from pgbackrest service
- [x] **Remove from depends_on**: Remove pgbackrest from other services' `depends_on` (if any)
- [x] **Keep volumes and networks**: Retain all volume mounts and network configurations

**Before:**

```yaml
pgbackrest:
  image: debian:bookworm-slim
  # ... volumes ...
  command: tail -f /dev/null # ← Remove this
  depends_on:
    - db
    - minio # ← Keep if needed for startup order
```

**After:**

```yaml
pgbackrest:
  image: debian:bookworm-slim
  # ... volumes ...
  # No command - runs one-shot
  depends_on:
    - db
    - minio
```

### **2. Update Backup Scripts**

- [x] **Modify `pgbackrest_mode.sh`**: Change `run_pgbackrest()` to use `docker-compose run --rm pgbackrest`
- [x] **Update all pgBackRest commands**: Ensure they use one-shot execution

**Example change in `pgbackrest_mode.sh`:**

```bash
# Before
run_pgbackrest() {
  docker compose -f "$SCRIPT_DIR/../docker-compose.backup.yml" exec pgbackrest "$@"
}

# After
run_pgbackrest() {
  docker compose -f "$SCRIPT_DIR/../docker-compose.backup.yml" run --rm pgbackrest "$@"
}
```

### **3. Update Documentation**

- [x] **Update `docs/BACKUP_RESTORE.md`**: Change startup commands to exclude pgbackrest from `up -d`
- [x] **Update usage examples**: Show `docker-compose run --rm pgbackrest <command>` instead of `exec`

**Example:**

```bash
# Before
docker compose -f docker/docker-compose.backup.yml up -d minio db pgbackrest

# After
docker compose -f docker/docker-compose.backup.yml up -d minio db
# Run pgbackrest commands on-demand
```

## **Testing Steps**

### **4. Test Backup Operations**

- [ ] **Start backup services**: `docker-compose -f docker/docker-compose.backup.yml up -d minio db`
- [ ] **Run stanza check**: `./docker/backup/pgbackrest_mode.sh check`
- [ ] **Create stanza if needed**: `./docker/backup/pgbackrest_mode.sh stanza-create`
- [ ] **Run backup**: `./docker/backup/pgbackrest_mode.sh backup`
- [ ] **Verify backup**: `./docker/backup/pgbackrest_mode.sh info`

### **5. Test Restore Operations**

- [ ] **Stop database**: `docker-compose -f docker/docker-compose.backup.yml stop db`
- [ ] **Remove database volume**: `docker volume rm apm-observability_pgdata` (if testing full restore)
- [ ] **Run restore**: `./docker/backup/pgbackrest_mode.sh restore`
- [ ] **Restart services**: `docker-compose -f docker/docker-compose.backup.yml up -d`
- [ ] **Verify data integrity**: Check if database data is restored correctly

### **6. SSL Verification**

- [ ] **Confirm SSL connectivity**: Ensure backups use HTTPS to MinIO (`repo1-s3-endpoint = https://minio:9000`)
- [ ] **Check certificate loading**: Verify `/tmp/ca/public.crt` is mounted and used
- [ ] **Test MinIO SSL**: Confirm backup files are stored securely over HTTPS

## **Benefits Achieved**

- [ ] **Resource efficiency**: No idle pgbackrest container consuming resources
- [ ] **On-demand execution**: Backup operations only run when needed
- [ ] **Cleaner architecture**: Separation of persistent services from task containers
- [ ] **Easier maintenance**: No need to manage pgbackrest service lifecycle

## **Rollback Plan**

- [ ] **If issues occur**: Revert changes and add back `command: tail -f /dev/null` to make pgbackrest persistent
- [ ] **Test thoroughly**: Run full backup/restore cycle before considering migration complete

**Completion Criteria**: All checkboxes marked, backup/restore operations working with SSL encryption, no persistent pgbackrest container running. ✅
