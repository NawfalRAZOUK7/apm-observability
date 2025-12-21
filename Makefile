# --- Backup/Restore SSH key setup ---
setup-backup-ssh:
	docker compose -f docker/docker-compose.backup.yml exec db bash /backup/setup_postgres_ssh.sh /backup/id_rsa.pub
	echo "✅ SSH key for postgres user set up in db container."
.PHONY: up down logs build restart ps \
        install makemigrations migrate run shell createsuperuser \
        test step6 \
        docker-test docker-migrate

# --- Docker compose file ---
COMPOSE = docker compose -f docker/docker-compose.yml

# --- Docker shortcuts ---
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

# Step 6: run full Django test suite locally
test:
	. .venv/bin/activate && python manage.py test -v 2

# Step 6: stricter runner (checks pending migrations + logs)
step6:
	./scripts/step6_test.sh

# --- Run commands inside Docker web container ---
docker-migrate:
	$(COMPOSE) exec web python manage.py migrate --noinput

docker-test:
	$(COMPOSE) exec web python manage.py test -v 2
