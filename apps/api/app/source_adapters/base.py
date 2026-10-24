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
    decision: str  # "allowed" or "denied"
    reasonCode: str  # "SOURCE_ALLOWED", "POLICY_RESTRICTED", etc.
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
        """Return True if this adapter handles the specified URL."""
        pass

    @abstractmethod
    def validate(self, url: str) -> Tuple[bool, str, str]:
        """
        Validate URL security and operator policy.
        Returns: (is_allowed, reason_code, message)
        """
        pass

    @abstractmethod
    def inspect(self, url: str) -> InspectionResult:
        """Extract media metadata and supported output capabilities."""
        pass

    @abstractmethod
    def health(self) -> Dict[str, Any]:
        """Report adapter version and tool availability."""
        pass
