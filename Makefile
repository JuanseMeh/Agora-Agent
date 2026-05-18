.PHONY: install up down logs test migrate proto

install:
	uv sync

up:
	DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1 docker compose up -d

down:
	docker compose down -v

logs:
	docker compose logs -f

test:
	docker compose run --rm agent pytest

migrate:
	docker compose exec agent uv run -- alembic upgrade head


proto:
	python -m grpc_tools.protoc -I./proto --python_out=./api/proto --grpc_python_out=./api/proto ./proto/*.proto
	touch api/proto/__init__.py
