import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.core.config import settings
from app.db.session import get_db
from app.models.asset import Asset
from app.schemas.asset import AssetResponse, AssetListResponse

router = APIRouter(prefix="/api/v1/assets", tags=["Assets"])


def map_asset_to_response(asset: Asset) -> AssetResponse:
    asset_id_str = str(asset.id)
    return AssetResponse(
        id=asset_id_str,
        jobId=str(asset.job_id) if asset.job_id else None,
        title=asset.title,
        originalFilenameSafe=asset.original_filename_safe,
        container=asset.container,
        videoCodec=asset.video_codec,
        audioCodec=asset.audio_codec,
        durationSeconds=asset.duration_seconds,
        sizeBytes=asset.size_bytes,
        sha256=asset.sha256,
        createdAt=asset.created_at,
        expiresAt=asset.expires_at,
        downloadUrl=f"/api/v1/assets/{asset_id_str}/download",
    )


@router.get("", response_model=AssetListResponse)
def list_assets(db: Session = Depends(get_db)):
    query = select(Asset).filter(Asset.deleted_at.is_(None)).order_by(desc(Asset.created_at))
    assets = db.execute(query).scalars().all()
    items = [map_asset_to_response(a) for a in assets]
    return AssetListResponse(items=items, total=len(items))


@router.get("/{asset_id}", response_model=AssetResponse)
def get_asset(asset_id: str, db: Session = Depends(get_db)):
    try:
        parsed_id = uuid.UUID(asset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid asset UUID format.")

    asset = db.execute(select(Asset).filter_by(id=parsed_id, deleted_at=None)).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found.")

    return map_asset_to_response(asset)


@router.get("/{asset_id}/download")
def download_asset(asset_id: str, db: Session = Depends(get_db)):
    try:
        parsed_id = uuid.UUID(asset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid asset UUID format.")

    asset = db.execute(select(Asset).filter_by(id=parsed_id, deleted_at=None)).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found.")

    # Resolve physical path safely within MEDIA_ROOT
    full_path = os.path.abspath(os.path.join(settings.MEDIA_ROOT, asset.relative_path))
    if not full_path.startswith(os.path.abspath(settings.MEDIA_ROOT)):
        raise HTTPException(status_code=403, detail="Path traversal security violation.")

    if not os.path.exists(full_path):
        raise HTTPException(status_code=410, detail="Asset media file is no longer available.")

    media_type = "video/mp4"
    if asset.container == "webm":
        media_type = "video/webm"
    elif asset.container == "mp3":
        media_type = "audio/mpeg"
    elif asset.container == "m4a":
        media_type = "audio/mp4"

    return FileResponse(
        path=full_path,
        media_type=media_type,
        filename=asset.original_filename_safe,
    )


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(asset_id: str, db: Session = Depends(get_db)):
    try:
        parsed_id = uuid.UUID(asset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid asset UUID format.")

    asset = db.execute(select(Asset).filter_by(id=parsed_id, deleted_at=None)).scalar_one_or_none()
    if not asset:
        return None

    # Delete physical file
    full_path = os.path.abspath(os.path.join(settings.MEDIA_ROOT, asset.relative_path))
    if full_path.startswith(os.path.abspath(settings.MEDIA_ROOT)) and os.path.exists(full_path):
        try:
            os.remove(full_path)
            # Remove parent asset dir if empty
            parent_dir = os.path.dirname(full_path)
            if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                os.rmdir(parent_dir)
        except Exception:
            pass

    asset.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return None
