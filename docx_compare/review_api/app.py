from __future__ import annotations

from pathlib import Path
import json
import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .review_service import create_review_bundle


BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "runtime" / "reviews"
SAMPLES_DIR = BASE_DIR / "samples"
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"


app = FastAPI(
    title="DOCX Review Studio",
    description="Review and highlight common text across two DOCX files.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_docx(filename: str) -> None:
    if not filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only DOCX files are supported.")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/review")
async def review_uploaded_files(
    first_file: UploadFile = File(...),
    second_file: UploadFile = File(...),
) -> JSONResponse:
    _ensure_docx(first_file.filename or "")
    _ensure_docx(second_file.filename or "")

    upload_dir = RUNTIME_DIR / "_incoming"
    upload_dir.mkdir(exist_ok=True)

    token = uuid.uuid4().hex[:8]
    first_temp_path = upload_dir / f"{token}_first.docx"
    second_temp_path = upload_dir / f"{token}_second.docx"

    first_temp_path.write_bytes(await first_file.read())
    second_temp_path.write_bytes(await second_file.read())

    payload = create_review_bundle(
        first_path=first_temp_path,
        second_path=second_temp_path,
        output_root=RUNTIME_DIR,
        first_name=first_file.filename,
        second_name=second_file.filename,
    )
    return JSONResponse(payload)


@app.post("/api/review/sample")
def review_sample_files() -> JSONResponse:
    first_path = SAMPLES_DIR / "test_file_a.docx"
    second_path = SAMPLES_DIR / "test_file_b.docx"

    if not first_path.exists() or not second_path.exists():
        raise HTTPException(status_code=404, detail="Sample DOCX files are missing.")

    payload = create_review_bundle(
        first_path=first_path,
        second_path=second_path,
        output_root=RUNTIME_DIR,
        first_name=first_path.name,
        second_name=second_path.name,
    )
    return JSONResponse(payload)


@app.get("/api/reviews/{review_id}/download/{side}")
def download_review_docx(review_id: str, side: str) -> FileResponse:
    if side not in {"first", "second"}:
        raise HTTPException(status_code=404, detail="Unknown review side.")

    review_dir = RUNTIME_DIR / review_id / "downloads"
    if not review_dir.exists():
        raise HTTPException(status_code=404, detail="Review download not found.")

    metadata_path = RUNTIME_DIR / review_id / "review.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Review download not found.")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    file_path = (
        review_dir / "first_reviewed.docx"
        if side == "first"
        else review_dir / "second_reviewed.docx"
    )
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Review download not found.")

    filename = (
        metadata["artifacts"]["firstDownloadName"]
        if side == "first"
        else metadata["artifacts"]["secondDownloadName"]
    )
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )


if FRONTEND_DIST_DIR.exists():
    assets_dir = FRONTEND_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    def serve_index() -> FileResponse:
        return FileResponse(FRONTEND_DIST_DIR / "index.html")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found.")
        candidate = FRONTEND_DIST_DIR / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST_DIR / "index.html")
else:

    @app.get("/")
    def frontend_placeholder() -> dict:
        return {
            "message": "Frontend build not found. Run `npm install` and `npm run build` in the frontend directory."
        }
