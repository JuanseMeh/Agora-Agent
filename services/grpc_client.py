"""
services/grpc_client.py

gRPC channel + stub lifecycle for ai-orchestrator (Rust/Tonic, port 50051).

The channel is created once on startup and reused across all requests.
grpc.aio (asyncio-native) is used throughout -- do not mix with synchronous grpc stubs.

Generated stubs are expected at: proto/ai_service_pb2.py and proto/ai_service_pb2_grpc.py
Run `make proto` to regenerate after any .proto changes.
"""

from __future__ import annotations

import logging

import grpc
import grpc.aio

from config.settings import settings

try:
    from proto import ai_service_pb2_grpc  # type: ignore[import]
except ImportError as exc:
    raise ImportError(
        "gRPC stubs not found. Run `make proto` to generate them from proto/ai_service.proto"
    ) from exc

logger = logging.getLogger(__name__)

_channel: grpc.aio.Channel | None = None
_stub: ai_service_pb2_grpc.AiServiceStub | None = None


async def init_grpc_client() -> None:
    global _channel, _stub

    target = f"{settings.orchestrator_grpc_host}:{settings.orchestrator_grpc_port}"
    logger.info("Connecting to ai-orchestrator at %s", target)

    _channel = grpc.aio.insecure_channel(
        target,
        options=[
            ("grpc.keepalive_time_ms", 30_000),
            ("grpc.keepalive_timeout_ms", 10_000),
            ("grpc.keepalive_permit_without_calls", True),
            ("grpc.max_reconnect_backoff_ms", 5_000),
        ],
    )
    _stub = ai_service_pb2_grpc.AiServiceStub(_channel)
    logger.info("gRPC stub initialized")


async def close_grpc_client() -> None:
    global _channel, _stub
    if _channel is not None:
        await _channel.close(grace=5.0)
        _channel = None
        _stub = None
        logger.info("gRPC channel closed")


def get_stub() -> ai_service_pb2_grpc.AiServiceStub:
    if _stub is None:
        raise RuntimeError(
            "gRPC client not initialized. Call init_grpc_client() on startup."
        )
    return _stub
