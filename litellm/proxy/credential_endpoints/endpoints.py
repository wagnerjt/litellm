"""
CRUD endpoints for storing reusable credentials.
"""

import asyncio
import traceback
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response

import litellm
from litellm._logging import verbose_proxy_logger
from litellm.proxy._types import CommonProxyErrors, UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from litellm.proxy.utils import handle_exception_on_proxy, jsonify_object
from litellm.types.utils import CredentialItem

router = APIRouter()


@router.post(
    "/v1/credentials",
    dependencies=[Depends(user_api_key_auth)],
    tags=["credential management"],
)
async def create_credential(
    request: Request,
    fastapi_response: Response,
    credential: CredentialItem,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Stores credential in DB.
    Reloads credentials in memory.
    """
    from litellm.proxy.proxy_server import prisma_client

    try:
        if prisma_client is None:
            raise HTTPException(
                status_code=500,
                detail={"error": CommonProxyErrors.db_not_connected_error.value},
            )

        credentials_dict = credential.model_dump()
        credentials_dict_jsonified = jsonify_object(credentials_dict)
        await prisma_client.db.litellm_credentialstable.create(
            data={
                **credentials_dict_jsonified,
                "created_by": user_api_key_dict.user_id,
                "updated_by": user_api_key_dict.user_id,
            }
        )

        return {"success": True, "message": "Credential created successfully"}
    except Exception as e:
        verbose_proxy_logger.exception(e)
        raise handle_exception_on_proxy(e)


@router.get(
    "/v1/credentials",
    dependencies=[Depends(user_api_key_auth)],
    tags=["credential management"],
)
async def get_credentials(
    request: Request,
    fastapi_response: Response,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    try:
        return {"success": True, "credentials": litellm.credential_list}
    except Exception as e:
        return handle_exception_on_proxy(e)


@router.get(
    "/v1/credentials/{credential_name}",
    dependencies=[Depends(user_api_key_auth)],
    tags=["credential management"],
)
async def get_credential(
    request: Request,
    fastapi_response: Response,
    credential_name: str,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    try:
        for credential in litellm.credential_list:
            if credential.credential_name == credential_name:
                return {"success": True, "credential": credential}
        return {"success": False, "message": "Credential not found"}
    except Exception as e:
        return handle_exception_on_proxy(e)


@router.delete(
    "/v1/credentials/{credential_name}",
    dependencies=[Depends(user_api_key_auth)],
    tags=["credential management"],
)
async def delete_credential(
    request: Request,
    fastapi_response: Response,
    credential_name: str,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    try:
        litellm.credential_list = [
            credential
            for credential in litellm.credential_list
            if credential.credential_name != credential_name
        ]
        return {"success": True, "message": "Credential deleted successfully"}
    except Exception as e:
        return handle_exception_on_proxy(e)


@router.put(
    "/v1/credentials/{credential_name}",
    dependencies=[Depends(user_api_key_auth)],
    tags=["credential management"],
)
async def update_credential(
    request: Request,
    fastapi_response: Response,
    credential_name: str,
    credential: CredentialItem,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    try:
        for i, c in enumerate(litellm.credential_list):
            if c.credential_name == credential_name:
                litellm.credential_list[i] = credential
                return {"success": True, "message": "Credential updated successfully"}
        return {"success": False, "message": "Credential not found"}
    except Exception as e:
        return handle_exception_on_proxy(e)
