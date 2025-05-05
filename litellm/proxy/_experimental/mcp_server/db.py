from typing import Dict, List, Literal, Optional, Union, cast

from prisma.models import LiteLLM_MCPServerTable
from litellm.proxy._types import NewMCPServerRequest
from litellm.proxy.utils import PrismaClient

async def fetch_all_mcp_servers(prisma_client: PrismaClient) -> List[LiteLLM_MCPServerTable]:
    """
    Returns all of the mcp servers from the db
    """

    mcp_servers = await prisma_client.db.litellm_mcpservertable.find_many()
    return mcp_servers


async def fetch_mcp_server(prisma_client: PrismaClient, server_id: str) -> Optional[LiteLLM_MCPServerTable]:
    """
    Returns the matching mcp server from the db iff exists
    """

    mcp_server: Optional[LiteLLM_MCPServerTable] = await prisma_client.db.litellm_mcpservertable.find_unique(
        where={
            "server_id": server_id,
        }
    )
    return mcp_server


async def fetch_mcp_servers(
    prisma_client: PrismaClient, team_id: List[str], user_id: Optional[str] = None
) -> List[LiteLLM_MCPServerTable]:
    """
    Get all the mcp servers filtered by the given user has access to.
    """
    ## GET ALL MEMBERSHIPS ##
    if not isinstance(user_id, str):
        user_id = str(user_id)

    # team_memberships = await prisma_client.db.litellm_teammembership.find_many(
    #     where=(
    #         {"user_id": user_id, "team_id": {"in": team_id}} if user_id is not None else {"team_id": {"in": team_id}}
    #     ),
    #     include={"litellm_budget_table": True},
    # )

    # returned_tm: List[LiteLLM_TeamMembership] = []
    # for tm in team_memberships:
    #     returned_tm.append(LiteLLM_TeamMembership(**tm.model_dump()))

    # TODO: complete
    return []


async def db_create_mcp_server(prisma_client: PrismaClient, data: NewMCPServerRequest) -> LiteLLM_MCPServerTable:
    """
    Create a new mcp server in the db
    """
    new_server = await prisma_client.db.litellm_mcpservertable.create(
        data=data.model_dump(),
    )
    return new_server


async def db_delete_mcp_server(prisma_client: PrismaClient, server_id: str) -> Optional[LiteLLM_MCPServerTable]:
    """
    Delete the mcp server from the db
    """
    deleted_server = await prisma_client.db.litellm_mcpservertable.delete(
        where={
            "server_id": server_id,
        },
    )
    return deleted_server