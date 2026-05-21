"""
services/users_service.py

Typed async client for user-service (Java/Spring, port 8080).

Endpoints verified:
  GET /users/get-user          -- fetch profile by user ID (header: X-User-Id)
  GET /users/email/{email}     -- fetch profile by email address
  GET /users/exists/{email}    -- check whether an email is registered
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from services.http_client import get_users_client, raise_for_service_error

logger = logging.getLogger(__name__)

_SVC = "user-service"


class UserDTO(BaseModel):
    id: Any
    name: str | None = None
    email: str | None = None
    role: str | None = None
    createdAt: str | None = None


class UserExistsDTO(BaseModel):
    exists: bool


async def get_user_by_id(user_id: str | int) -> UserDTO:
    client = get_users_client()
    response = await client.get(
        "/users/get-user",
        headers={"X-User-Id": str(user_id)},
    )
    raise_for_service_error(response, _SVC)
    return UserDTO(**response.json())


async def get_user_by_email(email: str) -> UserDTO:
    client = get_users_client()
    response = await client.get(f"/users/email/{email}")
    raise_for_service_error(response, _SVC)
    return UserDTO(**response.json())


async def user_exists(email: str) -> bool:
    client = get_users_client()
    response = await client.get(f"/users/exists/{email}")
    raise_for_service_error(response, _SVC)
    data = response.json()
    if isinstance(data, bool):
        return data
    return UserExistsDTO(**data).exists


if __name__ == "__main__":
    import asyncio
    import sys
    from services.http_client import init_http_clients, close_http_clients

    async def smoke_test(user_id: str) -> None:
        init_http_clients()
        try:
            user = await get_user_by_id(user_id)
            print(f"get_user_by_id({user_id}) -> {user}")
        except Exception as e:
            print(f"ERROR: {e}")
        finally:
            await close_http_clients()

    uid = sys.argv[1] if len(sys.argv) > 1 else "1"
    asyncio.run(smoke_test(uid))
