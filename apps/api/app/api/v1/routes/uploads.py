import os
import shutil
import uuid
import re
from fastapi import APIRouter, UploadFile, File, HTTPException, status

from app.core.config import settings
from app.schemas.upload import UploadResponse
from app.media.media_tools import probe_media

router = APIRouter(prefix="/api/v1/uploads", tags=["Uploads"])


def sanitize_filename(filename: str) -> str:
    cleaned = re.sub(r"[^\w\s.-]", "", filename).strip()
    return cleaned[:100] or "uploaded_media"


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UploadResponse)
async def upload_media_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename in upload.")

    safe_name = sanitize_filename(file.filename)
    upload_id = str(uuid.uuid4())
    upload_dir = os.path.join(settings.STAGING_DIR, "uploads", upload_id)
    os.makedirs(upload_dir, exist_ok=True)

    dest_path = os.path.join(upload_dir, safe_name)
    bytes_written = 0

    try:
        with open(dest_path, "wb") as buffer:
            while chunk := await file.read(65536):
                bytes_written += len(chunk)
                if bytes_written > settings.MAX_UPLOAD_BYTES:
                    buffer.close()
                    shutil.rmtree(upload_dir, ignore_errors=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Upload exceeded maximum allowed size of {settings.MAX_UPLOAD_BYTES} bytes."
                    )
                buffer.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {str(exc)}")

    # Probe media format with ffprobe
    probe_info = probe_media(dest_path)
    if not probe_info:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is not a recognized or valid media file."
        )

    return UploadResponse(
        uploadId=upload_id,
        originalFilename=safe_name,
        sizeBytes=bytes_written,
        format=probe_info.get("format"),
        durationSeconds=probe_info.get("duration"),
    )


@router.get("/{upload_id}", response_model=UploadResponse)
def get_upload_info(upload_id: str):
    upload_dir = os.path.join(settings.STAGING_DIR, "uploads", upload_id)
    if not os.path.exists(upload_dir):
        raise HTTPException(status_code=404, detail="Upload not found.")

    files = os.listdir(upload_dir)
    if not files:
        raise HTTPException(status_code=404, detail="Upload file not found.")

    filename = files[0]
    file_path = os.path.join(upload_dir, filename)
    probe_info = probe_media(file_path) or {}

    return UploadResponse(
        uploadId=upload_id,
        originalFilename=filename,
        sizeBytes=os.path.getsize(file_path),
        format=probe_info.get("format"),
        durationSeconds=probe_info.get("duration"),
    )


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_upload(upload_id: str):
    upload_dir = os.path.join(settings.STAGING_DIR, "uploads", upload_id)
    if os.path.exists(upload_dir):
        shutil.rmtree(upload_dir, ignore_errors=True)
    return None
