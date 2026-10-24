from pydantic import BaseModel, Field
from typing import Optional
from fastapi import APIRouter, HTTPException, status

from app.source_adapters.registry import registry
from app.source_adapters.base import InspectionResult

router = APIRouter(prefix="/api/v1/sources", tags=["Sources"])


class InspectRequest(BaseModel):
    url: str = Field(..., description="Source media URL to inspect")
    purpose: Optional[str] = Field("download-or-convert", description="Intended purpose")
    rightsConfirmed: bool = Field(True, description="Operator confirmation of source rights")


class CapabilitiesResponse(BaseModel):
    enabledAdapters: list[str]
    supportedVideoContainers: list[str] = ["mp4", "webm"]
    supportedAudioContainers: list[str] = ["mp3", "m4a"]


@router.get("/capabilities", response_model=CapabilitiesResponse)
def get_capabilities():
    return CapabilitiesResponse(
        enabledAdapters=registry.list_capabilities(),
        supportedVideoContainers=["mp4", "webm"],
        supportedAudioContainers=["mp3", "m4a"],
    )


@router.post("/inspect", response_model=InspectionResult)
def inspect_source(request: InspectRequest):
    adapter = registry.get_adapter(request.url)
    if not adapter:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Source URL does not match any registered or supported media adapters."
        )

    result = adapter.inspect(request.url)
    return result
