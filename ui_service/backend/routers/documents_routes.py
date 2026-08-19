from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

import services.documents_service as documents_service
from deps import get_current_user
from models.auth import MessageResponse
from models.documents import (
    CreateFolderRequest,
    DocumentTree,
    DownloadUrlResponse,
    MoveFileRequest,
    TreeNode,
)

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("/tree", response_model=DocumentTree)
async def get_tree(
    user: dict[str, Any] = Depends(get_current_user),
) -> DocumentTree:
    return await documents_service.get_tree(user)


@router.post("/files", response_model=TreeNode, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(..., description="PDF file"),
    folder: Optional[str] = Form(None, description="Target folder, empty for root"),
    user: dict[str, Any] = Depends(get_current_user),
) -> TreeNode:
    return await documents_service.upload_document(user, folder, file)


@router.post("/files/move", response_model=TreeNode)
async def move_file(
    req: MoveFileRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> TreeNode:
    return await documents_service.move_file(user, req.path, req.folder)


@router.get("/files/download", response_model=DownloadUrlResponse)
async def get_download_url(
    path: str = Query(..., description="File path relative to your folder"),
    user: dict[str, Any] = Depends(get_current_user),
) -> DownloadUrlResponse:
    return await documents_service.get_download_url(user, path)


@router.delete("/files", response_model=MessageResponse)
async def delete_file(
    path: str = Query(..., description="File path relative to your folder"),
    user: dict[str, Any] = Depends(get_current_user),
) -> MessageResponse:
    return await documents_service.delete_file(user, path)


@router.post("/folders", response_model=TreeNode, status_code=status.HTTP_201_CREATED)
async def create_folder(
    req: CreateFolderRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> TreeNode:
    return await documents_service.create_folder(user, req.path)


@router.delete("/folders", response_model=MessageResponse)
async def delete_folder(
    path: str = Query(..., description="Folder path relative to your folder"),
    user: dict[str, Any] = Depends(get_current_user),
) -> MessageResponse:
    return await documents_service.delete_folder(user, path)
