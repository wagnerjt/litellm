"""
Allow proxy admin to perform create,update, and delete operations on MCP servers in the db

Endpoints here:

/v*/mcp/{model_id}/update - PATCH endpoint for model update.
"""

#### MODEL MANAGEMENT ####

import asyncio
import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request, Query, Response, status
from fastapi.responses import JSONResponse
from prisma.models import LiteLLM_MCPServerTable

from litellm._logging import verbose_proxy_logger
from litellm.constants import LITELLM_PROXY_ADMIN_NAME
from litellm.proxy._experimental.mcp_server.db import (
    db_create_mcp_server,
    db_delete_mcp_server,
    fetch_all_mcp_servers,
    fetch_mcp_server,
)
from litellm.proxy._experimental.mcp_server.server import global_mcp_server_manager
from litellm.proxy._types import (
    CommonProxyErrors,
    MCPServerCreateResponseObject,
    LiteLLM_ProxyModelTable,
    LiteLLM_TeamTable,
    LitellmTableNames,
    LitellmUserRoles,
    ModelInfoDelete,
    NewMCPServerDeleteRequest,
    NewMCPServerRequest,
    PrismaCompatibleUpdateDBModel,
    ProxyErrorTypes,
    ProxyException,
    TeamModelAddRequest,
    UpdateTeamRequest,
    UserAPIKeyAuth,
)
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from litellm.proxy.common_utils.encrypt_decrypt_utils import encrypt_value_helper
from litellm.proxy.management_endpoints.common_utils import _is_user_team_admin
from litellm.proxy.management_endpoints.team_endpoints import (
    team_model_add,
    update_team,
)
from litellm.proxy.management_helpers.audit_logs import create_object_audit_log
from litellm.proxy.management_helpers.utils import management_endpoint_wrapper
from litellm.types.router import (
    Deployment,
    DeploymentTypedDict,
    LiteLLMParamsTypedDict,
    updateDeployment,
)
from litellm.utils import get_utc_datetime

router = APIRouter(prefix="/v1/mcp", tags=["mcp"])

## FastAPI Routes

@router.get(
    "/load",
    description="Returns the mcp server list",
    dependencies=[Depends(user_api_key_auth)],
)
async def load_servers_from_db(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    # perform authz check to filter the mcp servers user has access to
    mcp_servers = await global_mcp_server_manager.load_from_db()
    return mcp_servers

@router.get(
    "/server",
    description="Returns the mcp server list",
    dependencies=[Depends(user_api_key_auth)],
    response_model=List[LiteLLM_MCPServerTable],
)
async def get_all_mcp_servers(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Get all of the configured mcp servers in the db

    ```
    curl --location 'http://localhost:4000/v1/mcp/server' \
    --header 'Authorization: Bearer your_api_key_here'
    ```
    """
    from litellm.proxy.proxy_server import prisma_client

    if prisma_client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Database not connected. Connect a database to your proxy - https://docs.litellm.ai/docs/simple_proxy#managing-auth---virtual-keys"
            },
        )

    # perform authz check to filter the mcp servers user has access to
    resp = await fetch_all_mcp_servers(prisma_client)
    return resp


@router.get(
    "/server/{server_id}",
    description="Returns the mcp server info",
    dependencies=[Depends(user_api_key_auth)],
    response_model=LiteLLM_MCPServerTable,
)
async def get_mcp_server_info(
    server_id: str,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Get the info on the mcp server specified by the `server_id`

    Parameters:
    - server_id: str - Required. The unique identifier of the mcp server to get info on.

    ```
    curl --location 'http://localhost:4000/v1/mcp/server/server_id' \
    --header 'Authorization: Bearer your_api_key_here'
    ```
    """
    from litellm.proxy.proxy_server import prisma_client

    if prisma_client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Database not connected. Connect a database to your proxy - https://docs.litellm.ai/docs/simple_proxy#managing-auth---virtual-keys"
            },
        )

    # TODO: implement authz restriction from requested user
    mcp_server = await fetch_mcp_server(prisma_client, server_id)

    if mcp_server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": f"MCP Server with id {server_id} not found"},
        )
    return mcp_server


@router.get(
    "/server/{server_id}/tools",
    description="Returns the mcp server's tools",
    dependencies=[Depends(user_api_key_auth)],
    response_model=LiteLLM_MCPServerTable,
)
async def get_mcp_server_tools(
    http_request: Request,
    server_id: str,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Get all the tools from the mcp server specified by the `server_id`

    Parameters:
    - server_id: str - Required. The unique identifier of the mcp server to get info on.

    ```
    curl --location 'http://localhost:4000/v1/mcp/server/server_id/tools' \
    --header 'Authorization: Bearer your_api_key_here'
    ```
    """
    # TODO: Find the mcp servers for the key and make tool call request
    # TODO: implement authz restriction from requested user
    # TODO: request the tools
    pass


@router.post(
    "/server",
    description="Allows creation of mcp servers",
    dependencies=[Depends(user_api_key_auth)],
    response_model=LiteLLM_MCPServerTable,
)
@management_endpoint_wrapper
async def create_mcp_server(
    payload: NewMCPServerRequest,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
    litellm_changed_by: Optional[str] = Header(
        None,
        description="The litellm-changed-by header enables tracking of actions performed by authorized users on behalf of other users, providing an audit trail for accountability",
    ),
):
    """
    Allow users to add a new external mcp server.
    """
    from litellm.proxy.proxy_server import prisma_client

    if prisma_client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Database not connected. Connect a database to your proxy - https://docs.litellm.ai/docs/simple_proxy#managing-auth---virtual-keys"
            },
        )

    if payload.server_id is not None:
        # fail if the mcp server with id already exists
        mcp_server = await fetch_mcp_server(prisma_client, payload.server_id)
        if mcp_server is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": f"MCP Server with id {payload.server_id} already exists. Cannot overwrite."},
            )

    # restrict only admins to create mcp servers
    if user_api_key_dict.user_role is None or user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "User does not have permission to create mcp servers. You can only create mcp servers if you are a PROXY_ADMIN."
            },
        )

    # TODO: audit log for create

    # attempt to create the mcp server
    try:
        new_mcp_server = await db_create_mcp_server(prisma_client, payload)
    except Exception as e:
        verbose_proxy_logger.exception(f"Error creating mcp server: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Error creating mcp server: {str(e)}"},
        )
    return new_mcp_server


@router.delete(
    "/server/{server_id}",
    description="Allows deleting mcp serves in the db",
    dependencies=[Depends(user_api_key_auth)],
    response_class=JSONResponse,
)
@management_endpoint_wrapper
async def delete_mcp_server(
    server_id: str,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
    litellm_changed_by: Optional[str] = Header(
        None,
        description="The litellm-changed-by header enables tracking of actions performed by authorized users on behalf of other users, providing an audit trail for accountability",
    ),
):
    """
    Delete MCP Server from db and associated MCP related server entities.

    Parameters:
    - server_id: str - Required. The unique identifier of the mcp server to delete.

    ```
    curl -X "DELETE" --location 'http://localhost:4000/v1/mcp/server/server_id' \
    --header 'Authorization: Bearer your_api_key_here'
    ```
    """
    from litellm.proxy.proxy_server import (
        create_audit_log_for_update,
        litellm_proxy_admin_name,
        prisma_client,
    )

    if prisma_client is None:
        raise HTTPException(status_code=500, detail={"error": "No db connected"})

    # restrict only admins to delete mcp servers
    if user_api_key_dict.user_role is None or user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "User does not have permission to delete mcp servers. You can only delete mcp servers if you are a PROXY_ADMIN."
            },
        )

    # TODO: Finish audit log trail
    mcp_server_delete = await db_delete_mcp_server(prisma_client, server_id)

    if mcp_server_delete is None:
        raise HTTPException(status_code=404, detail={"error": f"MCP Server with id {server_id} not found"})

    return Response(status_code=status.HTTP_202_ACCEPTED)