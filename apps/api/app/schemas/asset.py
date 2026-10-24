from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


class AssetResponse(BaseModel):
    id: str
    jobId: Optional[str] = None
    title: Optional[str] = None
    originalFilenameSafe: str
    container: str
    videoCodec: Optional[str] = None
    audioCodec: Optional[str] = None
    durationSeconds: Optional[int] = None
    sizeBytes: int
    sha256: Optional[str] = None
    createdAt: datetime
    expiresAt: Optional[datetime] = None
    downloadUrl: str


class AssetListResponse(BaseModel):
    items: List[AssetResponse]
    total: int
