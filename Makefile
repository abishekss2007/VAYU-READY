# VAYU-READY. On Windows without make, run the command shown after each target (see README).
COMPOSE ?= docker-compose
RUN = $(COMPOSE) run --rm --no-deps

.PHONY: setup train seed test up down logs backup restore

setup:            ## build the images and create .env
	@test -f .env || cp .env.example .env
	$(COMPOSE) build

train:            ## train all models once; saved in models/ (mounted into the api container)
	$(RUN) --user 0 api python -m ml.train

seed:             ## (re)load the synthetic demo data: score starts at 71
	$(COMPOSE) up -d db
	$(COMPOSE) run --rm api python seed.py

test:             ## backend tests (SQLite inside the container; no database needed)
	$(RUN) api python -m pytest -q

up:               ## start everything: web on :3000, API docs on :8000/docs
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f api worker

backup:           ## encrypted backup of database and files into ./backups
	sh scripts/backup.sh

restore:          ## restore the newest backup (asks for the passphrase)
	sh scripts/restore.sh
