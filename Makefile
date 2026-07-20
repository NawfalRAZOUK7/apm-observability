# APM Observability helper targets
# Keep targets short and composable.

SHELL := /bin/bash
ROOT := $(CURDIR)

# Main stack (docker/docker-compose.yml)
ENV_DOCKER := .env.docker
ENV_PORTS := docker/.env.ports
ENV_PORTS_LOCAL := docker/.env.ports.localdev
ENV_CLUSTER := docker/cluster/.env.cluster

MAIN_ENV_ARGS := $(foreach f,$(ENV_DOCKER) $(ENV_PORTS) $(ENV_PORTS_LOCAL),$(if $(wildcard $(f)),--env-file $(f),))
CLUSTER_ENV_ARGS := $(foreach f,$(ENV_DOCKER) $(ENV_PORTS) $(ENV_PORTS_LOCAL) $(ENV_CLUSTER),$(if $(wildcard $(f)),--env-file $(f),))

COMPOSE := docker compose $(MAIN_ENV_ARGS) -f docker/docker-compose.yml

# Cluster stack envs + compose files
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

APP_CMD := docker compose -p apm-app $(CLUSTER_ENV_ARGS) -f $(APP_COMPOSE)
DATA_CMD := docker compose -p apm-data $(CLUSTER_ENV_ARGS) -f $(DATA_COMPOSE)
CONTROL_CMD := docker compose -p apm-control $(CLUSTER_ENV_ARGS) -f $(CONTROL_COMPOSE)

.PHONY: help
help:
	@echo "APM Observability Makefile"
	@echo ""
	@echo "Quick demo (single-node):"
	@echo "  make demo        # FULL stack (TimescaleDB + 3 pillars) + seed + URLs"
	@echo "  make loadtest    # drive traffic with k6 (BASE_URL/BATCH/ERROR_RATIO)"
	@echo "  make demo-down   # tear down the demo stack"
	@echo ""
	@echo "Kubernetes / GitOps:"
	@echo "  make helm-lint | k8s-deploy | argocd-up | argocd-app | argocd-password | argocd-down"
	@echo ""
	@echo "Main stack (docker/docker-compose.yml):"
	@echo "  make up | build | down | logs | restart | ps"
	@echo ""
	@echo "Local venv:"
	@echo "  make install | compile-deps | makemigrations | migrate | run | shell | createsuperuser | test"
	@echo "  make step6"
	@echo ""
	@echo "Docker (main stack):"
	@echo "  make docker-migrate | docker-test"
	@echo ""
	@echo "Backup:"
	@echo "  make certs-dev | setup-backup-ssh"
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

# --- Local TLS / key material ---
.PHONY: certs-dev
certs-dev:
	bash docker/certs/setup-ssl.sh
	bash docker/certs/gen_pgbackrest_mtls.sh

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

.PHONY: compile-deps
compile-deps:
	. .venv/bin/activate && pip install pip-tools && pip-compile --resolver=backtracking --no-strip-extras --output-file=requirements.txt requirements.in

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
	./scripts/tests/step6_test.sh

# --- Run commands inside Docker web container ---
.PHONY: docker-migrate docker-test
docker-migrate:
	$(COMPOSE) exec web python manage.py migrate --noinput

docker-test:
	$(COMPOSE) exec web python manage.py test -v 2

# --- One-command demo (single-node stack) ---
# Brings up the full single-node stack, seeds data, and prints the URLs.
BASE_URL ?= https://localhost:8443
SEED_COUNT ?= 2000
SEED_DAYS ?= 2

.PHONY: demo demo-down _demo-urls loadtest
# Full single-node stack: TimescaleDB + analytics + the three observability pillars.
demo:
	@echo ">> Generating local TLS assets (idempotent)..."
	@bash docker/certs/setup-ssl.sh >/dev/null 2>&1 || true
	@echo ">> Building and starting the FULL single-node stack (TimescaleDB)..."
	$(COMPOSE) up -d --build
	@echo ">> Waiting for the API to become healthy..."
	@for i in $$(seq 1 60); do \
		if curl -kfsS $(BASE_URL)/api/health/ >/dev/null 2>&1; then echo "API is up."; break; fi; \
		sleep 2; \
	done
	@echo ">> Seeding $(SEED_COUNT) events over $(SEED_DAYS) day(s)..."
	@$(COMPOSE) exec -T web python manage.py seed_apirequests --count $(SEED_COUNT) --days $(SEED_DAYS) || \
		echo "(seed skipped/failed - check 'make logs')"
	@$(MAKE) --no-print-directory _demo-urls

_demo-urls:
	@echo ""
	@echo "=================== APM Observability demo ==================="
	@echo "  API root       : $(BASE_URL)/api/requests/"
	@echo "  Swagger UI     : $(BASE_URL)/api/docs/"
	@echo "  ReDoc          : $(BASE_URL)/api/redoc/"
	@echo "  OpenAPI schema : $(BASE_URL)/api/schema/"
	@echo "  Metrics        : $(BASE_URL)/metrics"
	@echo "  Grafana        : http://localhost:33000  (admin / \$$GRAFANA_ADMIN_PASSWORD)"
	@echo "  Prometheus     : http://localhost:9090"
	@echo "  Alertmanager   : http://localhost:9093"
	@echo "=============================================================="
	@echo "Next: 'make loadtest' to drive traffic, or 'make demo-features'"
	@echo "      to seed a tenant + API key, send OTLP traces, and fire an alert."

# --- End-to-end feature demo (Phases 4-9) ---
# Seeds a demo tenant + ingestion API key, sends sample OTLP traces to
# /v1/traces (span storage + service map), and fires a test alert at
# /sink/notify (notification sink + incident workflow). Requires the stack to be
# up ('make demo'); runs inside the web container.
DEMO_TRACES ?= 25
.PHONY: demo-features
demo-features:
	@echo ">> Running end-to-end feature demo (OTLP traces + test alert)..."
	@$(COMPOSE) exec -T web python manage.py demo_e2e --traces $(DEMO_TRACES) || \
		echo "(demo-features failed - is the stack up? run 'make demo' first)"

# Tears down the demo stack.
demo-down:
	$(COMPOSE) down -v --remove-orphans

# --- Load test (k6) ---
loadtest:
	BASE_URL=$(BASE_URL) $(if $(BATCH),BATCH=$(BATCH),) $(if $(ERROR_RATIO),ERROR_RATIO=$(ERROR_RATIO),) k6 run --insecure-skip-tls-verify loadtest/ingest_and_read.js

# --- Data quality gate ---
.PHONY: data-quality
data-quality:
	$(COMPOSE) exec -T web python manage.py check_data_quality --max-age-minutes 1440

# --- SLO-as-code (Sloth) ---
# Generate Prometheus SLI/burn-rate rules + alerts from the declarative SLO spec.
.PHONY: slo-generate
slo-generate:
	sloth generate -i slo/apm-observability.slo.yaml -o slo/rules.gen.yml
	@echo ">> Wrote slo/rules.gen.yml — add it to your Prometheus rule_files."

# --- Kubernetes (Helm + ArgoCD) ---
HELM_CHART := deploy/helm/apm-observability
K8S_NAMESPACE ?= apm
ARGOCD_APP ?= deploy/argocd/application-local.yaml
.PHONY: helm-lint helm-template k8s-deploy k8s-argocd argocd-up argocd-app argocd-password argocd-ui argocd-down
helm-lint:
	helm lint $(HELM_CHART)

helm-template:
	helm template apm $(HELM_CHART)

k8s-deploy:
	helm upgrade --install apm $(HELM_CHART) --namespace $(K8S_NAMESPACE) --create-namespace

k8s-argocd:
	kubectl apply -f deploy/argocd/application.yaml

# Install Argo CD into the current kube-context and deploy the app via GitOps.
argocd-up:
	bash deploy/argocd/bootstrap.sh

# (Re)apply the Argo CD Application (defaults to the local-image variant).
argocd-app:
	kubectl apply -f $(ARGOCD_APP)

# Print the initial Argo CD admin password.
argocd-password:
	@kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo

# Port-forward the Argo CD UI to https://localhost:8080 (admin / see argocd-password).
argocd-ui:
	kubectl -n argocd port-forward svc/argocd-server 8080:443

# Remove the Application and uninstall Argo CD.
argocd-down:
	-kubectl delete -f $(ARGOCD_APP) --ignore-not-found
	-kubectl delete namespace argocd --ignore-not-found

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

# --- Terraform / OpenTofu IaC (Phase 14) ---
TF ?= terraform
TF_ENV ?= local
TF_DIR := infra/terraform/environments/$(TF_ENV)
.PHONY: tf-fmt tf-validate tf-init tf-plan tf-apply tf-destroy
tf-fmt:
	$(TF) fmt -recursive infra/terraform
tf-validate:
	$(TF) -chdir=$(TF_DIR) init -backend=false && $(TF) -chdir=$(TF_DIR) validate
tf-init:
	$(TF) -chdir=$(TF_DIR) init
tf-plan:
	$(TF) -chdir=$(TF_DIR) plan
tf-apply:
	$(TF) -chdir=$(TF_DIR) apply
tf-destroy:
	$(TF) -chdir=$(TF_DIR) destroy

# --- Secrets (SOPS) (Phase 15) ---
SOPS_FILE ?= infra/secrets/sops/apm-secret.enc.yaml
.PHONY: secrets-encrypt secrets-decrypt secrets-apply
secrets-encrypt:
	cd infra/secrets/sops && sops --encrypt --in-place $(notdir $(SOPS_FILE))
secrets-decrypt:
	sops --decrypt $(SOPS_FILE)
secrets-apply:
	sops --decrypt $(SOPS_FILE) | kubectl apply -f -
