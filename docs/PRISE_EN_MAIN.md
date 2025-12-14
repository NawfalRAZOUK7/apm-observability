# Section 2 — Prise en main (TimescaleDB)

Objectif : montrer comment se connecter, vérifier TimescaleDB, et exécuter une démo SQL reproductible.

## Prérequis

- Docker Compose démarré :
  - `docker compose -f docker/docker-compose.yml up -d`
  - Service DB : `db` (container `apm_timescaledb`, port host par défaut `5432`).
- Outils : `psql` côté host ou via le container; DBeaver facultatif.

## Connexion PostgreSQL / TimescaleDB

### Depuis le host (psql)

- Variables par défaut : `POSTGRES_DB=apm`, `POSTGRES_USER=apm`, `POSTGRES_PASSWORD=apm`, `POSTGRES_PORT=5432`.
- Commande directe :
  - `psql postgres://apm:apm@localhost:5432/apm`
- Alternative (sans URL) :
  - `PGPASSWORD=apm psql -h localhost -p 5432 -U apm -d apm`

### Depuis le container (psql inside db)

- Ouvrir un shell :
  - `docker compose -f docker/docker-compose.yml exec db bash`
- Puis :
  - `psql -U apm -d apm`

### DBeaver (optionnel, sans capture)

- Créer une connexion PostgreSQL avec :
  - Host : `localhost` (ou `db` si vous ciblez le réseau docker interne depuis un autre container)
  - Port : `5432`
  - Database : `apm`
  - User / Password : `apm` / `apm`
- Test de connexion, puis enregistrer. (Vous pouvez ajouter des captures plus tard si besoin.)

## Démo SQL minimale

Deux options : exécuter le script prêt à l’emploi ou saisir les commandes à la main.

### 1) Exécuter le script prêt à l’emploi

- Depuis le host (psql installé) :
  - `psql postgres://apm:apm@localhost:5432/apm -f scripts/db_quick_demo.sql`
- Ou depuis le container :
  - `docker compose -f docker/docker-compose.yml exec db psql -U apm -d apm -f /app/scripts/db_quick_demo.sql`

### 2) Commandes manuelles (résumé du script)

- Vérifier l’extension Timescale :
  - `SELECT extname FROM pg_extension WHERE extname = 'timescaledb';`
- Lister les hypertables existantes :
  - `SELECT hypertable_name, table_schema, table_name FROM timescaledb_information.hypertables;`
- Créer une table de démo et l’hypertable :
  - `DROP TABLE IF EXISTS demo_requests;`
  - `CREATE TABLE demo_requests (time timestamptz NOT NULL, service text NOT NULL, latency_ms integer NOT NULL);`
  - `SELECT create_hypertable('demo_requests', 'time', if_not_exists => true);`
- Insérer quelques lignes :
  - `INSERT INTO demo_requests VALUES (now() - interval '5 min', 'api', 120), (now() - interval '4 min', 'api', 90), (now() - interval '3 min', 'billing', 210), (now() - interval '2 min', 'api', 150), (now() - interval '1 min', 'billing', 110);`
- Agréger avec `time_bucket` :
  - `SELECT time_bucket('1 minute', time) AS bucket, service, count(*) AS hits, avg(latency_ms) AS avg_latency_ms FROM demo_requests GROUP BY bucket, service ORDER BY bucket DESC, service;`
- Voir l’info hypertable / chunks :
  - `SELECT * FROM timescaledb_information.hypertables WHERE hypertable_name = 'demo_requests';`
  - `SELECT chunk_schema, chunk_name, range_start, range_end FROM timescaledb_information.chunks WHERE hypertable_name = 'demo_requests' ORDER BY range_start;`

## Résultat attendu (validation rapide)

- `SELECT extname ...` retourne `timescaledb`.
- La requête `time_bucket` retourne des lignes par minute et par service (hits, latence moyenne).
- Les vues `timescaledb_information` montrent l’hypertable `demo_requests` et ses chunks.

## Acceptation

- Toute personne peut suivre les commandes ci-dessus ou exécuter `scripts/db_quick_demo.sql` pour reproduire la démo et vérifier TimescaleDB.
