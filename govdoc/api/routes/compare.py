"""文档对比 API 路由。"""

from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from govdoc.compare.service import create_compare_bundle_from_bytes, get_compare_download
from govdoc.schemas.compare import CompareResponse


DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ALLOWED_EXTENSIONS = {".docx", ".pdf"}


router = APIRouter(
    prefix="/api/v1/compare",
    tags=["compare"],
)


def _ensure_supported(filename: str) -> None:
    """校验上传文件名是否为支持的文档格式。"""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 DOCX 和 PDF 文件。")


@router.post("", response_model=CompareResponse)
async def compare_uploaded_files(
    files: list[UploadFile] = File(...),
) -> CompareResponse:
    """接收 N 份 DOCX/PDF 文件并返回文档对比结果。"""
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="至少上传 2 份文件。")

    file_data: list[tuple[bytes, str]] = []
    for index, upload in enumerate(files):
        name = upload.filename or f"file_{index}.docx"
        _ensure_supported(name)
        file_data.append((await upload.read(), name))

    try:
        return create_compare_bundle_from_bytes(files=file_data)
    except (BadZipFile, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {exc}") from exc
    except (RuntimeError, OSError) as exc:
        raise HTTPException(status_code=502, detail=f"文档转换失败: {exc}") from exc


@router.get("/{review_id}/download/{file_index}")
def download_compare_file(
    review_id: str,
    file_index: int,
) -> FileResponse:
    """下载指定 review 中某个文件的高亮 DOCX 副本。"""
    try:
        download = get_compare_download(review_id=review_id, file_index=file_index)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="对比结果不存在。") from exc

    return FileResponse(
        path=download.path,
        filename=download.filename,
        media_type=DOCX_MEDIA_TYPE,
    )
