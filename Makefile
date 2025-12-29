# APM Observability helper targets
# Keep targets short and composable.

SHELL := /bin/bash
ROOT := $(CURDIR)

# Main stack (docker/docker-compose.yml)
COMPOSE := docker compose --env-file docker/.env.ports --env-file docker/.env.ports.localdev -f docker/docker-compose.yml

# Cluster stack envs + compose files
ENV_PORTS := docker/.env.ports
ENV_PORTS_LOCAL := docker/.env.ports.localdev
ENV_CLUSTER := docker/cluster/.env.cluster
CONFIG ?= configs/cluster/cluster.yml

APP_COMPOSE := docker/cluster/docker-compose.app.yml
DATA_COMPOSE := docker/cluster/docker-compose.data.yml
CONTROL_COMPOSE := docker/cluster/docker-compose.control.yml

# Derived ports for test wrappers (auto-detect open ports).
TEST_MAIN_HTTPS_PORT_DEFAULT := $(shell bash -c 'set -a; f="$(ENV_PORTS)"; [ -f "$$f" ] && source "$$f"; echo "$${MAIN_NGINX_HTTPS_HOST_PORT:-8443}"')
TEST_MAIN_HTTPS_PORT_LOCAL := $(shell bash -c 'set -a; for f in $(ENV_PORTS) $(ENV_PORTS_LOCAL); do [ -f "$$f" ] && source "$$f"; done; echo "$${MAIN_NGINX_HTTPS_HOST_PORT:-8443}"')
TEST_MAIN_HTTPS_PORT := $(shell bash -c 'for p in $(TEST_MAIN_HTTPS_PORT_LOCAL) $(TEST_MAIN_HTTPS_PORT_DEFAULT); do if nc -z -w 1 127.0.0.1 $$p >/dev/null 2>&1; then echo $$p; exit 0; fi; done; echo $(TEST_MAIN_HTTPS_PORT_LOCAL)')

TEST_MAIN_DB_PORT_DEFAULT := $(shell bash -c 'set -a; f="$(ENV_PORTS)"; [ -f "$$f" ] && source "$$f"; echo "$${MAIN_DB_HOST_PORT:-5432}"')
TEST_MAIN_DB_PORT_LOCAL := $(shell bash -c 'set -a; for f in $(ENV_PORTS) $(ENV_PORTS_LOCAL); do [ -f "$$f" ] && source "$$f"; done; echo "$${MAIN_DB_HOST_PORT:-5432}"')
TEST_MAIN_DB_PORT := $(shell bash -c 'for p in $(TEST_MAIN_DB_PORT_LOCAL) $(TEST_MAIN_DB_PORT_DEFAULT); do if nc -z -w 1 127.0.0.1 $$p >/dev/null 2>&1; then echo $$p; exit 0; fi; done; echo $(TEST_MAIN_DB_PORT_LOCAL)')

TEST_CLUSTER_HTTPS_PORT_DEFAULT := $(shell bash -c 'set -a; f="$(ENV_PORTS)"; [ -f "$$f" ] && source "$$f"; echo "$${CLUSTER_APP_NGINX_HTTPS_HOST_PORT:-443}"')
TEST_CLUSTER_HTTPS_PORT_LOCAL := $(shell bash -c 'set -a; for f in $(ENV_PORTS) $(ENV_PORTS_LOCAL); do [ -f "$$f" ] && source "$$f"; done; echo "$${CLUSTER_APP_NGINX_HTTPS_HOST_PORT:-18443}"')
TEST_CLUSTER_HTTPS_PORT := $(shell bash -c 'for p in $(TEST_CLUSTER_HTTPS_PORT_LOCAL) $(TEST_CLUSTER_HTTPS_PORT_DEFAULT); do if nc -z -w 1 127.0.0.1 $$p >/dev/null 2>&1; then echo $$p; exit 0; fi; done; echo $(TEST_CLUSTER_HTTPS_PORT_LOCAL)')

TEST_CLUSTER_DB_PORT_DEFAULT := $(shell bash -c 'set -a; f="$(ENV_PORTS)"; [ -f "$$f" ] && source "$$f"; echo "$${CLUSTER_DATA_DB_HOST_PORT:-5432}"')
TEST_CLUSTER_DB_PORT_LOCAL := $(shell bash -c 'set -a; for f in $(ENV_PORTS) $(ENV_PORTS_LOCAL); do [ -f "$$f" ] && source "$$f"; done; echo "$${CLUSTER_DATA_DB_HOST_PORT:-5432}"')
TEST_CLUSTER_DB_PORT := $(shell bash -c 'for p in $(TEST_CLUSTER_DB_PORT_LOCAL) $(TEST_CLUSTER_DB_PORT_DEFAULT); do if nc -z -w 1 127.0.0.1 $$p >/dev/null 2>&1; then echo $$p; exit 0; fi; done; echo $(TEST_CLUSTER_DB_PORT_LOCAL)')

APP_CMD := docker compose -p apm-app --env-file $(ENV_PORTS) --env-file $(ENV_PORTS_LOCAL) --env-file $(ENV_CLUSTER) -f $(APP_COMPOSE)
DATA_CMD := docker compose -p apm-data --env-file $(ENV_PORTS) --env-file $(ENV_PORTS_LOCAL) --env-file $(ENV_CLUSTER) -f $(DATA_COMPOSE)
CONTROL_CMD := docker compose -p apm-control --env-file $(ENV_PORTS) --env-file $(ENV_PORTS_LOCAL) --env-file $(ENV_CLUSTER) -f $(CONTROL_COMPOSE)

.PHONY: help
help:
	@echo "APM Observability Makefile"
	@echo ""
	@echo "Main stack (docker/docker-compose.yml):"
	@echo "  make up | build | down | logs | restart | ps"
	@echo ""
	@echo "Local venv:"
	@echo "  make install | makemigrations | migrate | run | shell | createsuperuser | test"
	@echo "  make step6"
	@echo ""
	@echo "Docker (main stack):"
	@echo "  make docker-migrate | docker-test"
	@echo ""
	@echo "Backup:"
	@echo "  make setup-backup-ssh"
	@echo ""
	@echo "Cluster mode:"
	@echo "  make cluster-single CONFIG=..."
	@echo "  make cluster-multi  CONFIG=..."
	@echo ""
	@echo "Cluster stacks:"
	@echo "  make up-data | up-control | up-app | up-all"
	@echo "  make down-data | down-control | down-app | down-all"
	@echo ""
	@echo "Cluster checks / data:"
	@echo "  make health | seed | check-dbs"
	@echo ""
	@echo "Observability:"
	@echo "  make grafana | prometheus | targets"
	@echo ""
	@echo "Backup (cluster):"
	@echo "  make pgbackrest-info | pgbackrest-check | pgbackrest-full | pgbackrest-full-repo2"
	@echo ""
	@echo "Scripts:"
	@echo "  make bootstrap | validate"
	@echo "  make steps-all [STACK=main|cluster]"
	@echo "  make test-main | test-cluster | test-cluster-primary"

# --- Backup/Restore SSH key setup ---
.PHONY: setup-backup-ssh
setup-backup-ssh:
	docker compose -f docker/docker-compose.backup.yml exec db bash /backup/setup_postgres_ssh.sh /backup/id_rsa.pub
	@echo "SSH key for postgres user set up in db container."

# --- Docker shortcuts (main stack) ---
.PHONY: up build down logs restart ps
up:
	$(COMPOSE) up -d

build:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

restart: down up

ps:
	$(COMPOSE) ps

# --- Local (venv) shortcuts ---
.PHONY: install makemigrations migrate run shell createsuperuser test step6
install:
	. .venv/bin/activate && pip install -r requirements.txt

makemigrations:
	. .venv/bin/activate && python manage.py makemigrations

migrate:
	. .venv/bin/activate && python manage.py migrate --noinput

run:
	. .venv/bin/activate && python manage.py runserver

shell:
	. .venv/bin/activate && python manage.py shell

createsuperuser:
	. .venv/bin/activate && python manage.py createsuperuser

test:
	. .venv/bin/activate && python manage.py test -v 2

step6:
	./scripts/step6_test.sh

# --- Run commands inside Docker web container ---
.PHONY: docker-migrate docker-test
docker-migrate:
	$(COMPOSE) exec web python manage.py migrate --noinput

docker-test:
	$(COMPOSE) exec web python manage.py test -v 2

# --- Cluster mode switcher ---
.PHONY: cluster-single cluster-multi
cluster-single:
	python scripts/cluster/switch_cluster_mode.py single --config $(CONFIG)

cluster-multi:
	python scripts/cluster/switch_cluster_mode.py multi --config $(CONFIG)

# --- Cluster stacks ---
.PHONY: up-data up-control up-app up-all
up-data:
	$(DATA_CMD) up -d --build

up-control:
	$(CONTROL_CMD) up -d --build

up-app:
	$(APP_CMD) up -d --build

up-all: up-data up-control up-app

.PHONY: down-data down-control down-app down-all

down-data:
	$(DATA_CMD) down -v --remove-orphans

down-control:
	$(CONTROL_CMD) down -v --remove-orphans

down-app:
	$(APP_CMD) down -v --remove-orphans

down-all: down-app down-control down-data

# --- Cluster checks ---
.PHONY: health seed check-dbs
health:
	@curl -kI https://localhost:18443/api/health/ | head -n 5

seed:
	$(APP_CMD) exec web python manage.py seed_apirequests --count 1000 --days 1

check-dbs:
	$(APP_CMD) exec web python manage.py check_cluster_dbs

# --- Observability ---
.PHONY: grafana prometheus targets

grafana:
	@echo "Grafana: https://$$(grep '^CONTROL_NODE_IP=' $(ENV_CLUSTER) | cut -d= -f2):3000"

prometheus:
	@echo "Prometheus: https://$$(grep '^CONTROL_NODE_IP=' $(ENV_CLUSTER) | cut -d= -f2):9090"

targets:
	@echo "Prometheus targets: https://$$(grep '^CONTROL_NODE_IP=' $(ENV_CLUSTER) | cut -d= -f2):9090/targets"

# --- Backup (cluster) ---
.PHONY: pgbackrest-info pgbackrest-check pgbackrest-full pgbackrest-full-repo2
pgbackrest-info:
	$(CONTROL_CMD) exec pgbackrest pgbackrest --stanza=apm info

pgbackrest-check:
	$(CONTROL_CMD) exec pgbackrest pgbackrest --stanza=apm check

pgbackrest-full:
	$(CONTROL_CMD) exec pgbackrest pgbackrest --stanza=apm --type=full backup

pgbackrest-full-repo2:
	$(CONTROL_CMD) exec pgbackrest pgbackrest --stanza=apm --repo=2 --type=full backup

# --- Scripts ---
.PHONY: bootstrap validate
bootstrap:
	bash scripts/dev/bootstrap.sh

validate:
	bash scripts/dev/validate.sh

.PHONY: steps-all
steps-all:
	bash scripts/run_all_tests.sh

.PHONY: test-main test-cluster
test-main:
	STACK=main APP_HTTPS_PORT=$(TEST_MAIN_HTTPS_PORT) DB_PORT=$(TEST_MAIN_DB_PORT) POSTGRES_PORT=$(TEST_MAIN_DB_PORT) bash scripts/run_all_tests.sh

test-cluster:
	STACK=cluster APP_HTTPS_PORT=$(TEST_CLUSTER_HTTPS_PORT) DB_PORT=$(TEST_CLUSTER_DB_PORT) POSTGRES_PORT=$(TEST_CLUSTER_DB_PORT) bash scripts/run_all_tests.sh

.PHONY: test-cluster-primary
test-cluster-primary:
	$(DATA_CMD) up -d db-replica db-replica-2
	$(APP_CMD) up -d --force-recreate web
	$(MAKE) test-cluster
