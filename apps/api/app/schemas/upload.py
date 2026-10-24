from typing import Optional
from pydantic import BaseModel


class UploadResponse(BaseModel):
    uploadId: str
    originalFilename: str
    sizeBytes: int
    format: Optional[str] = None
    durationSeconds: Optional[int] = None
