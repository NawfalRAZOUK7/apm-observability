# **pgBackRest TCP Mode Configuration Checklist**

## **Overview**

Convert pgBackRest from SSH mode to TCP mode for direct database connection. This simplifies the setup while maintaining SSL encryption for backup storage to MinIO.

## **Current Configuration Analysis**

### **pgBackRest Config File: [`docker/backup/pgbackrest.conf`](docker/backup/pgbackrest.conf)**

- **Current Mode**: SSH (`pg1-host-type=ssh`)
- **SSH Settings**: `pg1-host-user=postgres`, `pg1-port=22`
- **Database**: `pg1-path=/var/lib/postgresql/data`
- **SSL Repository**: `repo1-s3-endpoint=https://minio:9000`, `repo1-s3-ca-file=/tmp/ca/public.crt`

### **Docker Compose: [`docker/docker-compose.backup.yml`](docker/docker-compose.backup.yml)**

- **pgbackrest service**: Already one-shot ready (no persistent command)
- **Volumes**: Includes SSL certificate mount (`./certs/public.crt:/tmp/ca/public.crt:ro`)
- **Networks**: Connected to backup-net for MinIO access

## **Code Changes Required**

### **1. Update pgBackRest Configuration**

- [x] **Change host type**: Set `pg1-host-type=tcp` in [`docker/backup/pgbackrest.conf`](docker/backup/pgbackrest.conf)
- [x] **Remove SSH settings**: Comment out or remove `pg1-host-user=postgres` and `pg1-port=22`
- [x] **Add TCP settings**: Ensure `pg1-host=db` (Docker service name) and `pg1-port=5432`
- [x] **Keep SSL settings**: Retain all `repo1-s3-*` settings for MinIO HTTPS

**Updated [`docker/backup/pgbackrest.conf`](docker/backup/pgbackrest.conf):**

```ini
[global]
repo1-type=s3
repo1-s3-endpoint=https://minio:9000
repo1-s3-bucket=apm-backups
repo1-s3-key=minioadmin
repo1-s3-key-secret=minioadmin
repo1-s3-ca-file=/tmp/ca/public.crt
repo1-s3-verify-ssl=n
repo1-retention-full=2

[apm]
pg1-path=/var/lib/postgresql/data
pg1-host=db
pg1-port=5432
pg1-host-type=tcp  # ← Changed from ssh
pg1-user=apm
pg1-database=apm
```

### **2. Update Docker Compose (if needed)**

- [x] **Verify service names**: Ensure `pg1-host=db` matches the db service name in [`docker/docker-compose.backup.yml`](docker/docker-compose.backup.yml)
- [x] **Check port mapping**: Confirm PostgreSQL port 5432 is accessible within backup-net
- [x] **SSL certificate mount**: Verify `./certs/public.crt:/tmp/ca/public.crt:ro` is mounted

### **3. Update Backup Scripts**

- [x] **Verify TCP compatibility**: Ensure [`docker/backup/pgbackrest_mode.sh`](docker/backup/pgbackrest_mode.sh) works with TCP mode
- [x] **Test connection**: Scripts should connect directly to PostgreSQL without SSH

## **Testing Steps**

### **4. Test Database Connectivity**

- [ ] **Start services**: `docker-compose -f docker/docker-compose.backup.yml up -d minio db`
- [ ] **Test TCP connection**: Run `./docker/backup/pgbackrest_mode.sh check` (should connect via TCP)
- [ ] **Verify no SSH errors**: Check logs for TCP connection success

### **5. Test Backup with SSL**

- [ ] **Create stanza**: `./docker/backup/pgbackrest_mode.sh stanza-create`
- [ ] **Run backup**: `./docker/backup/pgbackrest_mode.sh backup --repo=1 --type=full`
- [ ] **Verify SSL**: Confirm backup uploads to MinIO over HTTPS (`https://minio:9000`)
- [ ] **Check MinIO**: Access MinIO console at `https://localhost:9001` to verify encrypted backup storage

### **6. Test Restore with SSL**

- [ ] **Stop database**: `docker-compose -f docker/docker-compose.backup.yml stop db`
- [ ] **Run restore**: `./docker/backup/pgbackrest_mode.sh restore --repo=1`
- [ ] **Restart services**: `docker-compose -f docker/docker-compose.backup.yml up -d`
- [ ] **Verify data**: Check if database data is restored and accessible via API

## **Security Verification**

### **7. SSL Encryption Confirmation**

- [ ] **Certificate validation**: Ensure `/tmp/ca/public.crt` is used for MinIO connections
- [ ] **HTTPS traffic**: All backup operations use `https://minio:9000`
- [ ] **No HTTP fallback**: Verify no insecure connections to MinIO
- [ ] **Database security**: TCP connection is secure within Docker network

## **Benefits of TCP Mode**

- [ ] **Simplified setup**: No SSH keys or tunneling required
- [ ] **Direct connection**: Faster backup operations
- [ ] **SSL maintained**: Backup data still encrypted to MinIO
- [ ] **Easier debugging**: Clear TCP connection logs

## **Rollback Plan**

- [ ] **If TCP fails**: Revert `pg1-host-type` back to `ssh` and restore SSH settings
- [ ] **SSH alternative**: Keep SSH config as backup option
- [ ] **Test both modes**: Verify both TCP and SSH work before finalizing

**Completion Criteria**: pgBackRest connects via TCP, backups succeed with SSL to MinIO, restore operations work, no SSH dependencies. ✅

_(This checklist ensures safe TCP mode migration while preserving SSL encryption)_
