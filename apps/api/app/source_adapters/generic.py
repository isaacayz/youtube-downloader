import os
from urllib.parse import urlparse
from typing import Tuple, Dict, Any

from app.core.url_security import validate_url_security
from app.source_adapters.base import (
    BaseSourceAdapter,
    InspectionResult,
    SourceMetadata,
    SourceCapabilities,
    SourcePolicyDecision,
)


class GenericMediaAdapter(BaseSourceAdapter):
    SUPPORTED_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"}

    def identify(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            return any(path.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS)
        except Exception:
            return False

    def validate(self, url: str) -> Tuple[bool, str, str]:
        is_safe, ip, err = validate_url_security(url)
        if not is_safe:
            return False, "SSRF_SECURITY_VIOLATION", err or "Unsafe destination URL"

        return True, "SOURCE_ALLOWED", "Direct media URL authorized."

    def inspect(self, url: str) -> InspectionResult:
        is_allowed, reason_code, message = self.validate(url)
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path) or "remote_media"
        redacted_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        ext = os.path.splitext(filename)[1].lower()
        is_audio = ext in {".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg"}

        return InspectionResult(
            source="generic_direct",
            sourceUrlRedacted=redacted_url,
            metadata=SourceMetadata(
                title=filename,
                durationSeconds=None,
                thumbnailUrl=None,
                creatorLabel=parsed.netloc,
            ),
            capabilities=SourceCapabilities(
                videoContainers=["mp4", "webm"] if not is_audio else [],
                audioContainers=["mp3", "m4a"],
                qualityPresets=["best-available"],
                subtitles=False,
                playlist=False,
            ),
            policy=SourcePolicyDecision(
                decision="allowed" if is_allowed else "denied",
                reasonCode=reason_code,
                message=message,
            ),
        )

    def health(self) -> Dict[str, Any]:
        return {"adapter": "generic_direct", "available": True}
