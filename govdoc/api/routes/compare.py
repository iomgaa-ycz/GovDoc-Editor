"""DOCX 文档对比 API 路由。"""

from __future__ import annotations

from typing import Literal
from zipfile import BadZipFile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from govdoc.api.deps import get_current_user
from govdoc.compare.service import create_compare_bundle_from_bytes, get_compare_download
from govdoc.db.models import User
from govdoc.schemas.compare import CompareResponse


DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


router = APIRouter(
    prefix="/api/v1/compare",
    tags=["compare"],
)


def _ensure_docx(filename: str) -> None:
    """校验上传文件名是否为 DOCX 文件。"""
    if not filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="仅支持 DOCX 文件。")


@router.post("", response_model=CompareResponse)
async def compare_uploaded_docx(
    first_file: UploadFile = File(...),
    second_file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> CompareResponse:
    """接收两份 DOCX 文件并返回文档对比结果。"""
    first_name = first_file.filename or "first.docx"
    second_name = second_file.filename or "second.docx"
    _ensure_docx(first_name)
    _ensure_docx(second_name)

    try:
        return create_compare_bundle_from_bytes(
            first_content=await first_file.read(),
            second_content=await second_file.read(),
            first_name=first_name,
            second_name=second_name,
        )
    except (BadZipFile, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"DOCX 文件解析失败: {exc}") from exc


@router.get("/{review_id}/download/{side}")
def download_compare_docx(
    review_id: str,
    side: Literal["first", "second"],
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """下载指定 review 的高亮 DOCX 副本。"""
    try:
        download = get_compare_download(review_id=review_id, side=side)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="对比结果不存在。") from exc

    return FileResponse(
        path=download.path,
        filename=download.filename,
        media_type=DOCX_MEDIA_TYPE,
    )
