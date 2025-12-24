
# Project Cleanup Checklist

This document provides actionable, detailed checklists (in todo format) to guide a thorough cleanup of the project. Each section is focused on a specific area, with granular tasks to ensure nothing is missed. Mark each item as you complete it.

---

## 1. Scripts & Configs Cleanup

- [x] Review all scripts in `docker/` and subfolders:
  - [x] Remove unused or legacy scripts (e.g., manual fix or debug scripts)
  - [x] Archive scripts that are rarely used but may be needed for reference
  - [x] Ensure all active scripts are referenced in Dockerfiles, Compose, or documentation
  - [x] Add comments to scripts explaining their purpose
- [x] Review all config files (`.conf`, `.sh`, `.sql`):
  - [x] Remove configs not referenced by any service
  - [x] Move deprecated configs to an `archive/` folder
  - [x] Document the purpose of each config in a README or inline comment

---

## 2. Docker Compose Files

- [x] Review `docker-compose.yml`:
  - [x] Confirm it is only for the main application stack
  - [x] Add a comment at the top explaining its purpose
- [x] Review `docker-compose.backup.yml`:
  - [x] Confirm it is only for backup/restore stack
  - [x] Add a comment at the top explaining its purpose
- [x] Ensure shared configuration (env vars, volumes) is consistent between files
- [x] Remove or archive any deprecated Compose files

---

## 3. Legacy & Manual Files

- [x] Identify old/legacy files (e.g., `known_hosts.old`, manual test scripts)
  - Identified: `docker/backup/known_hosts.old`, `docker/backup/test_ssh_pgbackrest_db.sh`, `docker/archive/test_ssh_pgbackrest_db.sh`
- [x] Remove files not referenced in current automation or documentation
  - Removed: `docker/backup/known_hosts.old`, `docker/backup/test_ssh_pgbackrest_db.sh`
- [x] Archive files needed for historical reference in an `archive/` folder
  - Archived: `docker/archive/test_ssh_pgbackrest_db.sh`
- [x] Add a README in the archive folder explaining the purpose of each file
  - Created: `docker/archive/README.md` with file explanations

---

## 4. Documentation Cleanup

- [x] Review all `.md` files in `docs/` and `docs/diagrams/`: ✅ All reviewed, current docs kept, legacy/docs archived or moved to legacy.

  - [x] Remove or archive outdated/step-specific documentation (e.g., step11 backup/restore docs)
    - Archived: docs/step11*MinIO_Bucket_with_mc.md, docs/step11_Docker_Installation_Availability*(pgBackRest).md, docs/step11_Fix pgBackRest Image + MinIO Env Warnings.md, docs/STEP11_BACKUP_PLAN.md, docs/STEP11_MINIO_SETUP.md, docs/STEP11_PGBACKREST_SETUP.md
  - [x] Keep only current, relevant project docs

    - Current docs: SECURITY.md, PLAN.md, PRISE_EN_MAIN.md, DEPLOY.md, REPORT.md, BACKUP_RESTORE.md, diagrams/\*
    - All outdated/step-specific docs are archived in docs/archive/

  - [x] Move legacy docs to `docs/legacy/` or similar

    - Moved all files from docs/archive/ to docs/legacy/

  - [x] Add a README in legacy folder listing contents and purpose
    - Created: docs/legacy/README.md with file list and explanations

- [x] Ensure all diagrams are referenced in current documentation
  - All diagrams in docs/diagrams/ are referenced in REPORT.md

---

## 5. Postman Collections

- [ ] Review all collections in `postman/`:
  - [ ] Remove or archive step-specific collections if a unified collection exists
  - [ ] Keep only the latest, relevant collections
  - [ ] Move archived collections to `postman/legacy/`
  - [ ] Ensure environment files are up to date and in use

---

## 6. Test/Report Artifacts

- [ ] Add all generated reports and logs in `reports/` to `.gitignore`
- [ ] Add `__pycache__/` and other Python cache folders to `.gitignore`
- [ ] Periodically clean out `reports/` and subfolders
- [ ] Remove old test outputs not needed for CI or documentation

---

## 7. Empty/Unused Directories

- [ ] Scan for empty directories (excluding `.venv/`, `.git/`, `__pycache__/`, `node_modules/`, `logs/`, `reports/`)
- [ ] Remove empty directories unless required by scripts/configs
- [ ] Document any intentionally empty directories with a README

---

## 8. General Recommendations

- [ ] Use `.gitignore` to avoid tracking generated, sensitive, or temporary files
- [ ] Add comments or README files to explain the purpose of non-obvious files/folders
- [ ] Periodically repeat these checklists to keep the project clean and organized

---

> **Tip:** Check off each item as you complete it. Adjust or expand the checklists as your project evolves.
