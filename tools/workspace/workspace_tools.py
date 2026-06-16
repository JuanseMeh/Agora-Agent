"""
tools/workspace/workspace_tools.py

Workspace read tools.

Both tools are bound to a ToolContext at graph init time.
workspace_id comes from ctx, never from the LLM.
"""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from services.workspace_service import (
    get_all_workspaces,
    get_workspace_by_id,
)
from services.http_client import ServiceError
from tools.context import ToolContext

logger = logging.getLogger(__name__)


def make_workspace_tools(ctx: ToolContext) -> list:
    @tool
    async def list_workspaces() -> dict:
        """
        Lists all workspaces the platform knows about.
        Use this when the teacher refers to a workspace by name (e.g. 'Calculus 8A')
        and you need to resolve the name to a workspace ID before taking further action.
        Returns a list of workspaces with their IDs and names.
        """
        try:
            workspaces = await get_all_workspaces(user_id=ctx.user_id)
            return {
                "workspaces": [
                    {"id": str(ws.id), "name": ws.name, "description": ws.description}
                    for ws in workspaces
                ]
            }
        except ServiceError as e:
            logger.error("list_workspaces failed: %s", e)
            return {"error": str(e)}
        except Exception as e:
            logger.exception("list_workspaces unexpected error")
            return {"error": f"Unexpected error listing workspaces: {e}"}

    @tool
    async def get_workspace() -> dict:
        """
        Returns details for the current workspace from session context.
        Use this when the teacher asks about their current workspace, class, or course.
        Returns workspace name, description, and ID.
        """
        try:
            workspace_id = ctx.workspace_id_required()
        except ValueError as e:
            return {"error": str(e)}

        try:
            ws = await get_workspace_by_id(workspace_id)
            return {
                "id": str(ws.id),
                "name": ws.name,
                "description": ws.description,
                "ownerId": str(ws.ownerId) if ws.ownerId else None,
                "createdAt": ws.createdAt,
            }
        except ServiceError as e:
            logger.error("get_workspace failed: %s", e)
            return {"error": str(e)}
        except Exception as e:
            logger.exception("get_workspace unexpected error")
            return {"error": f"Unexpected error fetching workspace: {e}"}

    @tool
    async def select_workspace(workspace_id: str) -> dict:
        """
        Selects and activates a workspace for the current session.
        Call this when the teacher specifies which workspace to work with
        (e.g. 'use Test', 'work with Calculus 8A', 'go to my Math class').
        Accepts a workspace ID (numeric string like "1" or UUID) OR a workspace name.
        Once selected, subsequent tools will operate within this workspace.
        """
        try:
            ws = await get_workspace_by_id(workspace_id)
        except ServiceError:
            try:
                all_ws = await get_all_workspaces(user_id=ctx.user_id)
            except ServiceError as e2:
                return {"error": str(e2)}
            matches = [w for w in all_ws if w.name.lower() == workspace_id.lower()]
            if not matches:
                return {"error": f"No se encontró un espacio de trabajo con ID o nombre '{workspace_id}'."}
            ws = matches[0]

        from agent.session import update_session_workspace
        await update_session_workspace(ctx.session_id, str(ws.id))

        ctx.workspace_id = str(ws.id)

        logger.info("Workspace selected: session=%s workspace=%s", ctx.session_id, ws.id)
        return {
            "success": True,
            "workspace_id": str(ws.id),
            "name": ws.name,
            "description": ws.description,
        }

    return [list_workspaces, get_workspace, select_workspace]
