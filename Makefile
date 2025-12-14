.PHONY: up down logs venv install migrate run shell createsuperuser

up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down

logs:
	docker compose -f docker/docker-compose.yml logs -f

install:
	. .venv/bin/activate && pip install -r requirements.txt

migrate:
	. .venv/bin/activate && python manage.py migrate

run:
	. .venv/bin/activate && python manage.py runserver

shell:
	. .venv/bin/activate && python manage.py shell

createsuperuser:
	. .venv/bin/activate && python manage.py createsuperuser
