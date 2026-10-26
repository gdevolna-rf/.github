# ГДеволна 2.0 — частые команды. Всё выполняется в docker compose.
COMPOSE = docker compose
DEV = docker compose -f docker-compose.yml -f docker-compose.dev.yml
TEST_DB ?= test_gdevolna

.PHONY: up dev down logs ps migrate seed seed-reset shell test test-backend test-frontend test-e2e backup restore-check schema

up:            ## production-сборка (next build + standalone, код в образах)
	$(COMPOSE) up -d --build

dev:           ## dev-режим: исходники смонтированы, Next.js dev server с hot reload
	$(DEV) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

migrate:
	$(COMPOSE) run --rm backend python manage.py migrate

seed:
	$(COMPOSE) run --rm backend python manage.py seed_demo --if-empty

seed-reset:
	$(COMPOSE) run --rm backend python manage.py seed_demo --reset

shell:
	$(COMPOSE) run --rm backend python manage.py shell

schema:        ## OpenAPI-схема в docs/openapi.yml (0 ошибок и 0 предупреждений — иначе команда падает)
	$(COMPOSE) run --rm backend python manage.py spectacular --file /app/openapi.yml --validate --fail-on-warn && mv backend/openapi.yml docs/openapi.yml

test: test-backend test-frontend test-e2e

test-backend:
	$(COMPOSE) run --rm -e TEST_DB_NAME=$(TEST_DB) backend pytest --create-db

test-frontend: ## Vitest + проверка типов в одноразовом контейнере node (node_modules хоста не трогаются)
	docker run --rm -v "$(CURDIR)/frontend:/app" -v /app/node_modules -w /app node:22-alpine \
		sh -c "npm ci --no-audit --no-fund && npm test && npm run typecheck"

test-e2e:      ## e2e (Playwright) в контейнере против запущенного стенда
	$(COMPOSE) --profile e2e run --rm e2e

backup:
	./scripts/backup.sh

restore-check:
	./scripts/restore_check.sh
