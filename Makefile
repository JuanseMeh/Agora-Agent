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
	uv run python -m grpc_tools.protoc -I./proto --python_out=./proto --grpc_python_out=./proto ./proto/*.proto
	sed -i 's/^import ai_service_pb2/from proto import ai_service_pb2/' proto/ai_service_pb2_grpc.py
