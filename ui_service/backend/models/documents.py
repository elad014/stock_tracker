from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class TreeNode(BaseModel):
    name: str
    path: str = Field(..., description="Path relative to the user's own folder")
    type: Literal["file", "folder"]
    size: Optional[int] = None
    last_modified: Optional[datetime] = None
    children: list["TreeNode"] = Field(default_factory=list)


TreeNode.model_rebuild()


class DocumentTree(BaseModel):
    nodes: list[TreeNode]
    file_count: int
    max_files: int


class CreateFolderRequest(BaseModel):
    path: str = Field(
        ...,
        min_length=1,
        description="Folder path relative to the user's own folder",
    )


class MoveFileRequest(BaseModel):
    path: str = Field(..., min_length=1, description="Current file path")
    folder: str = Field(
        "",
        description="Destination folder relative to the user's own folder. Empty is the root.",
    )


class DownloadUrlResponse(BaseModel):
    url: str
    expires_in: int
