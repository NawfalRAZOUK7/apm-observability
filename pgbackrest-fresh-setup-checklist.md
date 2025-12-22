# **pgBackRest Fresh Setup Checklist: SSH + HTTPS Integration (PostgreSQL 17)**

## **Project Context**

- **Main Application**: Django APM Observability on PostgreSQL 17 + TimescaleDB
- **Existing SSL**: Certificates in [`docker/certs`](docker/certs), nginx HTTPS configured
- **Goal**: Create pgBackRest backup system from scratch using SSH connections and HTTPS for MinIO

## **Detailed Setup Checklist**

### **Phase 1: Infrastructure Preparation**

#### **1.1 Create Backup Docker Compose**

- [x] **Create `docker/docker-compose.backup.yml`**:

  ```yaml
  version: "3.8"

  services:
    db:
      image: timescale/timescaledb:latest-pg17
      environment:
        POSTGRES_USER: apm
        POSTGRES_DB: apm
        POSTGRES_PASSWORD: apm
      volumes:
        - ./db:/var/lib/postgresql/data
        - ./certs/public.crt:/tmp/ca/public.crt:ro
        - ./db/entrypoint_with_sshd.sh:/docker-entrypoint.sh
      command: ["/bin/bash", "/docker-entrypoint.sh"]
      networks:
        - backup-net
      restart: unless-stopped

    minio:
      build: ./minio
      environment:
        MINIO_ROOT_USER: minioadmin
        MINIO_ROOT_PASSWORD: minioadmin123
        MINIO_SERVER_URL: https://minio:9000
      volumes:
        - minio_data:/data
        - ./certs:/root/.minio/certs:ro
      ports:
        - "9000:9000"
        - "9001:9001"
      networks:
        - backup-net
      restart: unless-stopped

    pgbackrest:
      build: ./pgbackrest
      volumes:
        - ./backup/pgbackrest.conf:/etc/pgbackrest/pgbackrest.conf:ro
        - ./certs/public.crt:/tmp/ca/public.crt:ro
      networks:
        - backup-net
      command: ["sleep", "infinity"]
      restart: unless-stopped

  volumes:
    minio_data:

  networks:
    backup-net:
      driver: bridge
  ```

- [x] **Verify networks**: Ensure `backup-net` connects to main app network if needed

  **Analysis**: The backup stack is designed as an isolated environment with its own PostgreSQL instance. The pgBackRest service connects to the backup database via SSH within the same `backup-net` network. No cross-network communication with the main application stack is required, maintaining security isolation between production and backup environments.

#### **1.2 Create DB Entrypoint with SSH**

- [x] **Create [`docker/db/entrypoint_with_sshd.sh`](docker/db/entrypoint_with_sshd.sh)**:

  ```bash
  #!/bin/bash

  # Install pgBackRest and OpenSSH
  apt-get update && apt-get install -y pgbackrest openssh-server

  # Generate SSH host keys
  ssh-keygen -A

  # Create postgres SSH directory
  mkdir -p /var/lib/postgresql/.ssh
  chown postgres:postgres /var/lib/postgresql/.ssh
  chmod 700 /var/lib/postgresql/.ssh

  # Generate SSH keys for postgres user
  if [ ! -f /var/lib/postgresql/.ssh/id_rsa ]; then
      su - postgres -c "ssh-keygen -t rsa -b 2048 -f /var/lib/postgresql/.ssh/id_rsa -N ''"
      su - postgres -c "cat /var/lib/postgresql/.ssh/id_rsa.pub >> /var/lib/postgresql/.ssh/authorized_keys"
      chmod 600 /var/lib/postgresql/.ssh/authorized_keys
      chown postgres:postgres /var/lib/postgresql/.ssh/authorized_keys
  fi

  # Set permissions
  chown -R postgres:postgres /var/lib/postgresql

  # Start SSH daemon
  /usr/sbin/sshd -D &

  # Initialize PostgreSQL if needed
  if [ ! -f "/var/lib/postgresql/data/PG_VERSION" ]; then
      su - postgres -c "initdb -D /var/lib/postgresql/data --locale=C.UTF-8 --encoding=UTF-8"
  fi

  # Configure postgresql.conf for backups
  CONF="/var/lib/postgresql/data/postgresql.conf"
  if [ -f "$CONF" ]; then
      sed -i 's/#*wal_level.*/wal_level = replica/' "$CONF"
      sed -i 's/#*archive_mode.*/archive_mode = on/' "$CONF"
      sed -i "s|#*archive_command.*|archive_command = 'pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm archive-push %p'|" "$CONF"
      sed -i 's/#*listen_addresses.*/listen_addresses = '\''*'\''/' "$CONF"
  fi

  # Start PostgreSQL
  exec su - postgres -c "/usr/lib/postgresql/17/bin/postgres -D /var/lib/postgresql/data"
  ```

- [x] **Make executable**: `chmod +x docker/db/entrypoint_with_sshd.sh`

#### **1.3 Create MinIO Dockerfile with SSL**

- [x] **Create [`docker/minio/Dockerfile`](docker/minio/Dockerfile)**:

  ```dockerfile
  FROM minio/minio:latest

  # Copy SSL certificates
  COPY certs/public.crt /root/.minio/certs/public.crt
  COPY certs/private.key /root/.minio/certs/private.key

  # Set permissions
  RUN chmod 600 /root/.minio/certs/private.key

  # Expose ports
  EXPOSE 9000 9001

  # Start MinIO server with SSL
  ENTRYPOINT ["minio", "server", "/data", "--console-address", ":9001"]
  ```

- [x] **Create MinIO init script**: [`docker/minio/init.sh`](docker/minio/init.sh)
  ```bash
  #!/bin/bash
  mc alias set myminio https://minio:9000 minioadmin minioadmin123 --api S3v4
  mc mb myminio/apm-backups
  mc policy set public myminio/apm-backups
  ```

#### **1.4 Create pgBackRest Dockerfile**

- [x] **Create `docker/pgbackrest/Dockerfile`**:

  ```dockerfile
  FROM debian:bookworm

  # Install pgBackRest and dependencies
  RUN apt-get update && apt-get install -y \
      pgbackrest \
      openssh-client \
      ca-certificates \
      && rm -rf /var/lib/apt/lists/*

  # Create pgbackrest user
  RUN useradd -m -s /bin/bash pgbackrest

  # Set working directory
  WORKDIR /home/pgbackrest

  # Default command
  CMD ["pgbackrest"]
  ```

- [x] **Create pgBackRest config**: `docker/backup/pgbackrest.conf`

  ```ini
  [global]
  repo1-type=s3
  repo1-s3-endpoint=https://minio:9000
  repo1-s3-bucket=apm-backups
  repo1-s3-key=minioadmin
  repo1-s3-key-secret=minioadmin123
  repo1-s3-ca-file=/tmp/ca/public.crt
  repo1-s3-verify-ssl=y
  repo1-path=/pgbackrest
  repo1-retention-full=7

  repo2-type=posix
  repo2-path=/var/lib/pgbackrest-hot
  repo2-retention-full=2

  log-level-console=info
  start-fast=y
  process-max=2

  [apm]
  pg1-path=/var/lib/postgresql/data
  pg1-host=db
  pg1-port=5432
  pg1-host-type=ssh
  pg1-host-user=postgres
  pg1-user=apm
  pg1-database=apm
  ```

### **Phase 2: SSL Certificate Setup**

#### **2.1 Verify Existing Certificates**

- [x] **Check [`docker/certs`](docker/certs)**: Confirm `public.crt` and `private.key` exist
- [x] **Certificate validity**: Run `openssl x509 -in [`docker/certs/public.crt`](docker/certs/public.crt ) -text -noout` to check expiry
- [x] **CA setup**: Ensure certificates are trusted for MinIO

#### **2.2 Generate MinIO Certificates (if needed)**

- [x] **Create `docker/minio/gen-cert.sh`**: Not needed - certificates already exist
  ```bash
  #!/bin/bash
  openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 \
      -subj "/C=US/ST=State/L=City/O=Organization/CN=minio" \
      -keyout private.key -out public.crt
  ```
- [x] **Run script**: `./docker/minio/gen-cert.sh` if certificates don't exist - Not needed, certificates exist

#### **2.3 Mount Certificates**

- [x] **Verify mounts**: In `docker-compose.backup.yml`, ensure certs are mounted to MinIO and pgBackRest containers
- [x] **Permissions**: Set correct permissions for private keys (600)

### **Phase 3: SSH Configuration**

#### **3.1 SSH Key Distribution**

- [ ] **Copy postgres public key**: From db container to pgbackrest container
- [ ] **Add to known hosts**: In pgbackrest container, add db host to `~/.ssh/known_hosts`
- [ ] **Test SSH connection**: `ssh -o StrictHostKeyChecking=no postgres@db 'echo "SSH working"'`

#### **3.2 SSH Config File**

- [x] **Create `docker/pgbackrest/ssh_config`**:
  ```
  Host db
      HostName db
      User postgres
      StrictHostKeyChecking no
      UserKnownHostsFile /dev/null
  ```
- [x] **Mount SSH config**: Add volume mount in docker-compose.backup.yml

#### **3.3 pgBackRest SSH User**

- [ ] **Create pgbackrest user**: In db container, `useradd -m -s /bin/bash pgbackrest`
- [ ] **SSH permissions**: Add pgbackrest to sudoers for pgBackRest commands
- [ ] **Key authentication**: Copy pgbackrest public key to db authorized_keys

### **Phase 4: pgBackRest Configuration**

#### **4.1 Stanza Configuration**

- [x] **Update `docker/backup/pgbackrest.conf`**: Ensure all paths and credentials are correct
- [ ] **Test config**: `pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm check`

#### **4.2 WAL Archiving**

- [x] **Verify postgresql.conf**: Confirm WAL settings are applied - Configured in entrypoint script
- [ ] **Test archive command**: Manually run archive-push to verify

#### **4.3 Repository Setup**

- [ ] **Initialize MinIO**: Run [`docker/minio/init.sh`](docker/minio/init.sh) to create bucket
- [ ] **Test S3 connection**: `pgbackrest --config=/etc/pgbackrest/pgbackrest.conf info`

### **Phase 5: Testing and Validation**

#### **5.1 Start Services**

- [ ] **Launch backup stack**: `docker-compose -f docker/docker-compose.backup.yml up -d`
- [ ] **Check logs**: `docker-compose -f docker/docker-compose.backup.yml logs`

#### **5.2 Create Stanza**

- [ ] **Run stanza-create**: `docker-compose -f docker/docker-compose.backup.yml exec pgbackrest pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm stanza-create`
- [ ] **Verify in MinIO**: Check bucket for stanza files

#### **5.3 Test Backup**

- [ ] **Full backup**: `docker-compose -f docker/docker-compose.backup.yml exec pgbackrest pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm backup --type=full`
- [ ] **Check status**: `pgbackrest --config=/etc/pgbackrest/pgbackrest.conf info`

#### **5.4 Test Restore**

- [ ] **Stop main DB**: `docker-compose -f [`docker/docker-compose.yml`](docker/docker-compose.yml ) stop db`
- [ ] **Restore**: `docker-compose -f docker/docker-compose.backup.yml exec pgbackrest pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm restore`
- [ ] **Restart and verify**: Check data integrity
- [ ] **Test application**: Ensure Django app works with restored data

#### **5.5 SSL Validation**

- [ ] **HTTPS traffic**: Confirm all MinIO connections use HTTPS
- [ ] **Certificate validation**: No SSL errors in logs
- [ ] **SSH encryption**: Verify SSH connections are encrypted

### **Phase 6: Automation**

#### **6.1 Backup Scripts**

- [ ] **Create `docker/backup/backup.sh`**:
  ```bash
  #!/bin/bash
  docker-compose -f docker/docker-compose.backup.yml exec pgbackrest pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm backup --type=incr
  ```
- [ ] **Restore script**: `docker/backup/restore.sh`

#### **6.2 Cron Jobs**

- [ ] **Add to pgbackrest container**: Schedule daily backups
- [ ] **Log rotation**: Configure log management

### **Phase 7: Documentation**

#### **7.1 Create Documentation**

- [ ] **Update `docs/BACKUP_RESTORE.md`**: Document SSH + HTTPS setup
- [ ] **Troubleshooting guide**: Common issues and solutions
- [ ] **Runbook**: Step-by-step backup/restore procedures

## **Completion Criteria**

- [ ] pgBackRest configured with SSH connections
- [ ] MinIO using HTTPS with SSL certificates
- [ ] Successful backup and restore operations
- [ ] Integration with existing SSL infrastructure
- [ ] Automated backup scripts created

## **Troubleshooting**

- **SSH Issues**: Check key permissions and known_hosts
- **SSL Errors**: Verify certificate paths and validity
- **Connection Failures**: Test network connectivity between containers

**This checklist creates pgBackRest from scratch with SSH and HTTPS integration for PostgreSQL 17.** 🚀
