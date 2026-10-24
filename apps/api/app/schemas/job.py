from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class JobSourceSchema(BaseModel):
    type: str = Field(..., description="Source type: 'url', 'upload', or 'synthetic'")
    url: Optional[str] = Field(None, description="Media URL for remote acquisition or synthetic test")
    uploadId: Optional[str] = Field(None, description="Staged upload ID for file conversion")
    inspectionId: Optional[str] = Field(None, description="Pre-inspection ID if available")


class JobOutputSchema(BaseModel):
    mode: str = Field(default="video", description="Output mode: 'video' or 'audio'")
    container: str = Field(default="mp4", description="Output container: 'mp4', 'webm', 'mp3', 'm4a'")
    quality: Optional[str] = Field(default="best-available", description="Quality preset name")
    subtitles: Optional[bool] = Field(default=False, description="Whether to include subtitles")


class JobCreateRequest(BaseModel):
    source: JobSourceSchema
    output: JobOutputSchema = Field(default_factory=JobOutputSchema)
    rightsConfirmed: bool = Field(..., description="User attestation of source rights/authorization")


class JobCreateResponse(BaseModel):
    jobId: str
    status: str
    createdAt: datetime
    statusUrl: str
    eventsUrl: str


class JobProgressSchema(BaseModel):
    phase: Optional[str] = None
    percent: Optional[int] = None
    bytesProcessed: Optional[int] = None
    totalBytes: Optional[int] = None
    speedBytesPerSecond: Optional[int] = None
    etaSeconds: Optional[int] = None
    updatedAt: Optional[datetime] = None


class JobResponse(BaseModel):
    id: str
    jobType: str
    status: str
    progress: JobProgressSchema
    sourceType: str
    sourceHost: Optional[str] = None
    sourceUrlRedacted: Optional[str] = None
    requestedContainer: Optional[str] = None
    requestedMode: Optional[str] = None
    requestedQuality: Optional[str] = None
    attemptCount: int
    maxAttempts: int
    lastErrorCode: Optional[str] = None
    lastErrorSafeMessage: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    expiresAt: Optional[datetime] = None


class JobListResponse(BaseModel):
    items: List[JobResponse]
    total: int
    limit: int
    offset: int
