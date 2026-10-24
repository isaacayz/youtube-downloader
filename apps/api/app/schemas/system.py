from typing import Dict, Any, Optional
from pydantic import BaseModel


class SystemCapabilities(BaseModel):
    youtubeDownloadEnabled: bool
    localUploadEnabled: bool
    maxUploadBytes: int
    maxOutputBytes: int


class SystemInfoResponse(BaseModel):
    version: str
    environment: str
    capabilities: SystemCapabilities


class SystemStatusResponse(BaseModel):
    status: str
    queueDepth: int
    activeJobs: int
    databaseConnected: bool
    redisConnected: bool
    workerCount: int
    diskFreeBytes: int
    diskTotalBytes: int


class SystemToolsResponse(BaseModel):
    ytDlpVersion: Optional[str] = None
    ffmpegVersion: Optional[str] = None
    ffprobeVersion: Optional[str] = None
    jsRuntimeVersion: Optional[str] = None
