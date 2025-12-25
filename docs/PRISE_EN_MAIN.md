# Prise en main

Guide pas a pas pour repartir de zero et valider le projet.
Objectif: permettre un lancement propre depuis un environnement vide et verifier les checks.

## Choisir le mode (rapide)
| Mode | Quand l'utiliser | Commande de base |
| --- | --- | --- |
| Cluster | Demo complete (replicas, pgBackRest, monitoring) | `make up-all` |
| Local / main stack | Test rapide sans cluster | `docker compose -f docker/docker-compose.yml up -d --build` |

## 0) Prerequis
- Docker Desktop + Docker Compose
- Python 3.12 (pour le switcher de configuration)
- Node.js + newman (optionnel, pour la suite de tests API)

Optionnel (recommande):
```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pyyaml
```

## 1) Nettoyer l'etat Docker (repartir de zero)
```
make down-all
docker compose -f docker/docker-compose.yml down -v --remove-orphans

# Supprimer les volumes restants du projet (si besoin).
# Cela supprime aussi la base "main stack" (volume db_data).
docker volume ls -q | grep '^apm' | xargs -r docker volume rm
```

Optionnel (ne pas faire si tu veux garder les fichiers locaux):
```
# Supprimer les fichiers locaux generes
rm -f docker/cluster/.env.cluster
rm -f configs/cluster/cluster.yml
# Optionnel: rm -f .env.gemini

# Nettoyer les artefacts locaux Python / logs
rm -rf .venv staticfiles media
find . -name '__pycache__' -type d -prune -exec rm -rf {} +
find . -name '*.log' -type f -delete
```

## 2) Configurer le cluster (single machine par defaut)
```
cp -n configs/cluster/cluster.example.yml configs/cluster/cluster.yml
```
Ouvrir `configs/cluster/cluster.yml` et ajuster les IP/ports si besoin.

Notes:
- En mode single, le switcher met `DATA_NODE_IP/CONTROL_NODE_IP/APP_NODE_IP` a `host.docker.internal` pour que les containers se parlent.
- Pour acceder a l'UI depuis le navigateur, utiliser l'IP LAN de la machine (ex: 192.168.x.x).

## 3) Generer les fichiers d'environnement
```
python scripts/cluster/switch_cluster_mode.py --config configs/cluster/cluster.yml
```
Cela met a jour `docker/cluster/.env.cluster` et `docker/monitoring/prometheus.yml`.

## 4) Lancer le cluster (data, control, app)
```
make up-data
make up-control
make up-app
```
Le conteneur web lance deja les migrations au demarrage.
Si `make up-data` echoue au tout premier lancement, attendre 30-60s et relancer la meme commande.

## 5) Seed (donnees de demo)
```
make seed
```

## 6) Initialiser pgBackRest (une fois)
```
docker compose -p apm-control \
  --env-file docker/.env.ports \
  --env-file docker/.env.ports.localdev \
  --env-file docker/cluster/.env.cluster \
  -f docker/cluster/docker-compose.control.yml \
  exec pgbackrest pgbackrest --stanza=apm stanza-create
```

## 7) Seed backups (hot + cold)
```
make pgbackrest-full
make pgbackrest-full-repo2
```
Astuce: eviter de lancer un backup exactement a :00 (cron horaire) pour eviter un conflit de lock.

## 8) Verifier que tout est OK
```
make validate
```
Attendu:
- DB primary et replicas OK.
- pgBackRest "status: ok" avec repo1 et repo2.
- Health endpoint HTTPS 200.

## 9) Tests API (optionnel)
```
npm install -g newman newman-reporter-htmlextra
make steps-all STACK=cluster
```

## 10) Acces monitoring (optionnel)
```
make grafana
make prometheus
make targets
```
Astuce: ces commandes affichent `host.docker.internal` pour les containers.
Dans le navigateur, utiliser l'IP LAN de la machine (ex: 192.168.x.x) en HTTPS.
Note: certificat local auto-signe => accepter l'avertissement du navigateur.

## 11) Arret des services (optionnel)
```
make down-all
```

## 12) Variante "local / main stack" (optionnel)
Si tu veux tester la stack principale (non-cluster) sur une seule machine:

### 12.1) Lancer la stack principale
```
docker compose -f docker/docker-compose.yml up -d --build
```

### 12.2) Seed (donnees de demo)
```
docker compose -f docker/docker-compose.yml exec web \
  python manage.py seed_apirequests --count 1000 --days 1
```

### 12.3) Verifier que tout est OK
```
docker compose -f docker/docker-compose.yml exec web python manage.py test -v 2
curl -kI https://localhost:8443/api/health/ | head -n 5
```

### 12.4) Stop + wipe (local)
```
docker compose -f docker/docker-compose.yml down -v --remove-orphans
```
