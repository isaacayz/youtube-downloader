import json
import subprocess
from urllib.parse import urlparse
from typing import Tuple, Dict, Any

from app.core.config import settings
from app.core.url_security import validate_url_security
from app.source_adapters.base import (
    BaseSourceAdapter,
    InspectionResult,
    SourceMetadata,
    SourceCapabilities,
    SourcePolicyDecision,
)


class YouTubeSourceAdapter(BaseSourceAdapter):
    YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}

    def identify(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            return any(host == yh or host.endswith("." + yh) for yh in self.YOUTUBE_HOSTS)
        except Exception:
            return False

    def validate(self, url: str) -> Tuple[bool, str, str]:
        is_safe, ip, err = validate_url_security(url)
        if not is_safe:
            return False, "SSRF_SECURITY_VIOLATION", err or "Unsafe destination URL"

        if not settings.ENABLE_YOUTUBE_DOWNLOAD:
            return (
                False,
                "YOUTUBE_DOWNLOAD_DISABLED",
                "YouTube source downloading is disabled by operator policy. Set ENABLE_YOUTUBE_DOWNLOAD=true to authorize."
            )

        return True, "SOURCE_ALLOWED", "Authorized YouTube source."

    def inspect(self, url: str) -> InspectionResult:
        is_allowed, reason_code, message = self.validate(url)
        parsed = urlparse(url)
        redacted_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        if not is_allowed:
            return InspectionResult(
                source="youtube",
                sourceUrlRedacted=redacted_url,
                metadata=SourceMetadata(
                    title="YouTube Video",
                    durationSeconds=None,
                    thumbnailUrl=None,
                    creatorLabel=None,
                ),
                capabilities=SourceCapabilities(),
                policy=SourcePolicyDecision(
                    decision="denied",
                    reasonCode=reason_code,
                    message=message,
                ),
            )

        # Run yt-dlp metadata inspection with child process safety
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-playlist",
            "--skip-download",
            "--no-warnings",
            "--socket-timeout", "10",
            url
        ]

        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15,
                shell=False
            )
            if res.returncode != 0:
                return InspectionResult(
                    source="youtube",
                    sourceUrlRedacted=redacted_url,
                    metadata=SourceMetadata(title="Unknown YouTube Video"),
                    capabilities=SourceCapabilities(),
                    policy=SourcePolicyDecision(
                        decision="denied",
                        reasonCode="SOURCE_UNAVAILABLE",
                        message="Failed to retrieve video metadata from YouTube.",
                    ),
                )

            data = json.loads(res.stdout)
            title = data.get("title", "YouTube Video")
            duration = data.get("duration")
            thumbnail = data.get("thumbnail")
            uploader = data.get("uploader") or data.get("channel")

            return InspectionResult(
                source="youtube",
                sourceUrlRedacted=redacted_url,
                metadata=SourceMetadata(
                    title=title,
                    durationSeconds=duration,
                    thumbnailUrl=thumbnail,
                    creatorLabel=uploader,
                ),
                capabilities=SourceCapabilities(
                    videoContainers=["mp4", "webm"],
                    audioContainers=["mp3", "m4a"],
                    qualityPresets=["best-available", "1080p", "720p", "480p", "360p"],
                    subtitles=bool(data.get("subtitles")),
                    playlist=False,
                ),
                policy=SourcePolicyDecision(
                    decision="allowed",
                    reasonCode="SOURCE_ALLOWED",
                    message="Metadata successfully retrieved.",
                ),
            )
        except Exception as exc:
            return InspectionResult(
                source="youtube",
                sourceUrlRedacted=redacted_url,
                metadata=SourceMetadata(title="YouTube Video"),
                capabilities=SourceCapabilities(),
                policy=SourcePolicyDecision(
                    decision="denied",
                    reasonCode="INSPECTION_FAILED",
                    message=f"Metadata extraction failed: {str(exc)}",
                ),
            )

    def health(self) -> Dict[str, Any]:
        return {"adapter": "youtube", "available": True}
