from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel


class SourceMetadata(BaseModel):
    title: str
    durationSeconds: Optional[int] = None
    thumbnailUrl: Optional[str] = None
    creatorLabel: Optional[str] = None


class SourceCapabilities(BaseModel):
    videoContainers: List[str] = ["mp4", "webm"]
    audioContainers: List[str] = ["mp3", "m4a"]
    qualityPresets: List[str] = ["best-available", "1080p", "720p", "480p", "360p"]
    subtitles: bool = False
    playlist: bool = False


class SourcePolicyDecision(BaseModel):
    decision: str
    reasonCode: str
    message: Optional[str] = None


class InspectionResult(BaseModel):
    source: str
    sourceUrlRedacted: str
    metadata: SourceMetadata
    capabilities: SourceCapabilities
    policy: SourcePolicyDecision


class BaseSourceAdapter(ABC):
    @abstractmethod
    def identify(self, url: str) -> bool:
        pass

    @abstractmethod
    def validate(self, url: str) -> Tuple[bool, str, str]:
        pass

    @abstractmethod
    def inspect(self, url: str) -> InspectionResult:
        pass

    @abstractmethod
    def health(self) -> Dict[str, Any]:
        pass
