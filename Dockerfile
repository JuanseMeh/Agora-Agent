# --- Builder ---
FROM python:3.11-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1

COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

COPY . .

RUN if [ -d "proto" ] && ls proto/*.proto > /dev/null 2>&1; then \
    mkdir -p proto/generated && \
    uv run python -m grpc_tools.protoc \
        -I./proto \
        --python_out=./proto/generated \
        --grpc_python_out=./proto/generated \
        proto/*.proto && \
    touch proto/generated/__init__.py; \
    fi

# --- Runtime ---
FROM python:3.11-slim-bookworm AS runtime

WORKDIR /app

COPY --from=builder /app .

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["/app/.venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]