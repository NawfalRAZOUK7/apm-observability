.PHONY: up down logs install migrate makemigrations run shell createsuperuser test step6

up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down

logs:
	docker compose -f docker/docker-compose.yml logs -f

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

# Step 6: run full Django test suite
test:
	. .venv/bin/activate && python manage.py test -v 2

# Step 6: the stricter runner (checks pending migrations + logs)
step6:
	./scripts/step6_test.sh
