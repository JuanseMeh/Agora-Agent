"""
tools/users/user_tools.py

User profile read tools.

The LLM uses get_user_by_id after resolving a user reference from
a member list or submission. get_user_by_email handles cases where
the teacher identifies a student by their email address.
"""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from services.users_service import get_user_by_id, get_user_by_email
from services.http_client import ServiceError
from tools.context import ToolContext

logger = logging.getLogger(__name__)


def make_user_tools(ctx: ToolContext) -> list:
    _ = ctx

    @tool
    async def get_user(user_id: str) -> dict:
        """
        Returns the profile for a specific user by their ID.
        Use this to look up a student's name, email, or role after
        you have their user ID from a submission or member list.
        Args:
            user_id: The user UUID to fetch.
        """
        try:
            user = await get_user_by_id(user_id)
            return {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "createdAt": user.createdAt,
            }
        except ServiceError as e:
            logger.error("get_user(%s) failed: %s", user_id, e)
            return {"error": str(e)}
        except Exception as e:
            logger.exception("get_user unexpected error")
            return {"error": f"Unexpected error fetching user {user_id}: {e}"}

    @tool
    async def get_user_by_email_address(email: str) -> dict:
        """
        Returns the profile for a user identified by their email address.
        Use this when the teacher refers to a student by email
        (e.g. 'what did maria@school.edu submit?').
        Args:
            email: The student's email address.
        """
        try:
            user = await get_user_by_email(email)
            return {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "createdAt": user.createdAt,
            }
        except ServiceError as e:
            logger.error("get_user_by_email(%s) failed: %s", email, e)
            return {"error": str(e)}
        except Exception as e:
            logger.exception("get_user_by_email unexpected error")
            return {"error": f"Unexpected error fetching user by email {email}: {e}"}

    @tool
    async def list_workspace_members() -> dict:
        """
        Lists all members of the current workspace.
        Use this when the teacher asks who is in their class, or when you need
        to resolve a student name to a user ID before fetching their submissions.
        Returns member user IDs and roles.
        """
        from services.workspace_service import get_workspace_members
        try:
            workspace_id = ctx.workspace_id_required()
        except ValueError as e:
            return {"error": str(e)}

        try:
            members = await get_workspace_members(workspace_id)
            return {
                "workspace_id": workspace_id,
                "count": len(members),
                "members": [
                    {
                        "userId": str(m.userId),
                        "role": m.role,
                        "joinedAt": m.joinedAt,
                    }
                    for m in members
                ],
            }
        except ServiceError as e:
            logger.error("list_workspace_members failed: %s", e)
            return {"error": str(e)}
        except Exception as e:
            logger.exception("list_workspace_members unexpected error")
            return {"error": f"Unexpected error listing members: {e}"}

    return [get_user, get_user_by_email_address, list_workspace_members]
