# Présentation de la base — TimescaleDB pour l’APM (Section 1)

## Pourquoi TimescaleDB pour les séries temporelles / APM

- TimescaleDB est une extension PostgreSQL conçue pour les séries temporelles : même moteur SQL, mêmes outils, mais avec hypertables, chunking et continuous aggregates.
- APM produit des flux append-only à haut débit (latences, codes HTTP, traces). Les hypertables gèrent efficacement l’écriture et la rétention par plage de temps.
- Les continuous aggregates (CAGG) offrent des vues matérialisées incrémentales (hourly/daily) adaptées aux tableaux de bord et aux KPI (hits, erreurs, p95, max, latence moyenne).

## Cas d’usage et adoption

- Observabilité / APM : métriques de requêtes HTTP, traces, événements d’infrastructure.
- IoT / télémétrie industrielle : mesures capteurs, maintenance prédictive.
- FinOps / billing : consommation par client/service, agrégats horaires/journaliers.
- Systèmes financiers : séries de prix, carnets d’ordres agrégés.
- TimescaleDB est utilisé dans les secteurs SaaS, IoT, énergie, retail; la compatibilité PostgreSQL facilite l’adoption (ORMs, BI, SQL standard).

## Architecture interne (PostgreSQL)

- Processus backend : un processus par connexion gère les requêtes SQL.
- WAL (Write-Ahead Log) : journal des transactions, garantit durabilité; écrit avant les datafiles.
- Checkpointer : force périodiquement les pages modifiées sur disque.
- Background writer : évacue les dirty buffers pour réduire la charge du checkpointer.
- Autovacuum/Analyze : nettoie tuples morts, maintient les statistiques.
- Buffers : cache partagé (shared_buffers) amortit lectures/écritures.

## Hypertables, chunks et compression (Timescale)

- Hypertable : abstraction logique; en dessous, données réparties en chunks par temps (et optionnellement par espace, ex: service).
- Chunking : chaque chunk couvre une fenêtre temporelle; réduit les scans complets et facilite la rétention (suppression/compression par chunk).
- Compression (optionnelle) : colonnes encodées par segment; réduit stockage et I/O; utile pour données froides (anciens chunks).

## Continuous aggregates (CAGG) et rafraîchissement

- Les CAGG matérialisent des agrégats sur l’hypertable via time_bucket(); ils sont incrémentaux (rafraîchissent uniquement les fenêtres impactées).
- Politiques de refresh : planifiées par background jobs Timescale; la fenêtre peut être décalée (ex : 1 h de retard) pour éviter les données en cours d’arrivée.
- Pour notre APM : vues hourly et daily (hits, erreurs, avg, p95, max). Le p95 peut être recalculé sur la table raw pour précision si nécessaire.

## Particularités utiles pour l’APM

- time_bucket() : groupement temporel efficace (heure/jour).
- Retention policy : suppression ou compression des chunks anciens pour maîtriser les coûts.
- Compression policy : compresse les chunks anciens, réduit I/O.
- CAGG policy : rafraîchit automatiquement les agrégats.

## Comparaison avec Oracle

- Licensing / coût : TimescaleDB Community/Cloud vs Oracle SE/EE (licences CPU + options); TCO nettement inférieur côté Timescale/Postgres.
- Fonctionnalités : SQL riche des deux côtés; Timescale apporte hypertables/CAGG natives pour time-series; Oracle requiert partitionnement + matérialized views, souvent avec options payantes.
- Scalabilité : Timescale scale-up/postgres + partitionnement et multi-node en option; Oracle scale-up/Real Application Clusters (RAC) avec coûts élevés.
- Tooling : Timescale garde l’écosystème PostgreSQL (psql, extensions, drivers). Oracle a ses outils propriétaires (SQL\*Plus, OEM) et drivers spécifiques.
- Transactionnel vs analytique : Oracle solide en OLTP/OLAP mais coûteux; Timescale vise time-series/analytique temps réel tout en restant OLTP-compatible.

## On-prem vs cloud (Aurora/RDS/Postgres/Timescale Cloud)

- Coût : RDS/Aurora gèrent les opérations mais facturent par instance + stockage + I/O; Timescale Cloud facture par ressources time-series; on-premise = CAPEX + ops internes.
- Ops/complexité : les services gérés (RDS/Aurora) simplifient patch/backup/monitoring; on-prem donne contrôle fin (extensions, configs) mais demande SRE/DBA.
- Performance : Aurora offre stockage distribué; RDS standard reste mono-instance; on-prem peut optimiser pour matériel dédié; Timescale Cloud optimise pour hypertables/CAGG.
- Autoscaling vs contrôle : cloud managé = autoscaling simplifié (dans limites); on-prem = contrôle maximal mais scaling manuel; choisir selon SLA, budget, gouvernance.

## Références croisées

- Diagrammes Mermaid :
  - Postgres processus/WAL/bgwriter : [docs/diagrams/postgres_processes.md](diagrams/postgres_processes.md)
  - Hypertable et chunks : [docs/diagrams/hypertable_chunks.md](diagrams/hypertable_chunks.md)
  - Flux de refresh CAGG : [docs/diagrams/cagg_refresh.md](diagrams/cagg_refresh.md)

## Résumé

TimescaleDB marie PostgreSQL et fonctionnalités time-series (hypertables, CAGG, policies de rétention/compression) adaptées à l’APM. Les coûts et l’opérationnel sont plus légers qu’un stack Oracle pour le même besoin; le déploiement peut être on-prem ou managé (RDS/Aurora/Timescale Cloud) selon l’équilibre recherché entre contrôle et coût.
