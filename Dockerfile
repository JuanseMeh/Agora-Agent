# --- Builder Stage ---
FROM python:3.11-slim-bookworm AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1

COPY pyproject.toml uv.lock .python-version ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

COPY . .

# Generate gRPC stubs (if proto directory exists)
RUN if [ -d "proto" ]; then \
    mkdir -p api/proto && \
    PROTO_FILES="$(ls -1 proto/*.proto 2>/dev/null || true)" && \
    if [ -n "$PROTO_FILES" ]; then \
      uv run -- python -m grpc_tools.protoc -I./proto --python_out=./api/proto --grpc_python_out=./api/proto $PROTO_FILES ; \
    fi && \
    touch api/proto/__init__.py; \
    fi

# --- Runtime Stage ---
FROM python:3.11-slim-bookworm AS runtime

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./

# Install dependencies again inside runtime (using uv-managed environment)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev && \
    uv run -- python -c "import uvicorn"

# Copy application code (including generated proto stubs from builder output)
COPY --from=builder /app /app

EXPOSE 8000

CMD ["uv", "run", "--", "python", "main.py"]