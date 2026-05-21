"""
services/http_client.py

Base async HTTP client for all REST service calls.
No auth headers -- all services are reachable on agora-network without authentication.
"""

import httpx

from config.settings import settings

_DEFAULT_TIMEOUT = httpx.Timeout(
    connect=5.0,
    read=30.0,
    write=10.0,
    pool=5.0,
)

_workspace_client: httpx.AsyncClient | None = None
_users_client: httpx.AsyncClient | None = None


def _make_client(base_url: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=_DEFAULT_TIMEOUT,
        headers={"Content-Type": "application/json"},
        follow_redirects=True,
    )


def init_http_clients() -> None:
    global _workspace_client, _users_client
    _workspace_client = _make_client(settings.workspace_service_url)
    _users_client = _make_client(settings.users_service_url)


async def close_http_clients() -> None:
    if _workspace_client:
        await _workspace_client.aclose()
    if _users_client:
        await _users_client.aclose()


def get_workspace_client() -> httpx.AsyncClient:
    if _workspace_client is None:
        raise RuntimeError("HTTP clients not initialized. Call init_http_clients() on startup.")
    return _workspace_client


def get_users_client() -> httpx.AsyncClient:
    if _users_client is None:
        raise RuntimeError("HTTP clients not initialized. Call init_http_clients() on startup.")
    return _users_client


class ServiceError(Exception):
    def __init__(self, service: str, status_code: int, detail: str) -> None:
        self.service = service
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"[{service}] HTTP {status_code}: {detail}")


def raise_for_service_error(response: httpx.Response, service_name: str) -> None:
    if response.is_success:
        return

    detail: str
    try:
        body = response.json()
        detail = body.get("message") or body.get("error") or response.text
    except Exception:
        detail = response.text or f"status {response.status_code}"

    raise ServiceError(
        service=service_name,
        status_code=response.status_code,
        detail=detail,
    )
