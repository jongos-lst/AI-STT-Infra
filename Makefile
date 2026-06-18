.PHONY: up down rebuild logs ps clean test backend-test frontend-test \
        api-shell migrate fresh

up:
	docker compose up --build -d

down:
	docker compose down

rebuild:
	docker compose build --no-cache

logs:
	docker compose logs -f --tail=200 api stt-worker llm-worker outbox-sweeper

ps:
	docker compose ps

clean:
	docker compose down -v

# Run the migration job by itself (after a schema change).
migrate:
	docker compose run --rm db-migrate

# Wipe volumes + rebuild + bring up.
fresh: clean
	docker compose up --build -d

api-shell:
	docker compose exec api bash

backend-test:
	cd backend && .venv/bin/python -m pytest tests/unit -v

frontend-test:
	cd frontend && npm test

test: backend-test frontend-test
