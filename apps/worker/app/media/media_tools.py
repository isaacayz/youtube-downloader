import os
import re
import json
import signal
import hashlib
import subprocess
from typing import Optional, Dict, Any, Callable


def calculate_file_checksum(file_path: str) -> str:
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def probe_media(file_path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return None

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path,
    ]

    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            shell=False,
        )
        if res.returncode != 0:
            return None

        data = json.loads(res.stdout)
        fmt = data.get("format", {})
        streams = data.get("streams", [])

        if not streams:
            return None

        video_codec = None
        audio_codec = None
        for stream in streams:
            codec_type = stream.get("codec_type")
            if codec_type == "video" and not video_codec:
                video_codec = stream.get("codec_name")
            elif codec_type == "audio" and not audio_codec:
                audio_codec = stream.get("codec_name")

        duration = None
        try:
            duration_val = fmt.get("duration")
            if duration_val:
                duration = int(float(duration_val))
        except (ValueError, TypeError):
            pass

        size_bytes = int(fmt.get("size", os.path.getsize(file_path)))
        format_name = fmt.get("format_name", "")

        return {
            "format": format_name,
            "duration": duration,
            "size": size_bytes,
            "video_codec": video_codec,
            "audio_codec": audio_codec,
            "stream_count": len(streams),
        }
    except Exception:
        return None


def _parse_time_to_seconds(time_str: str) -> float:
    try:
        parts = time_str.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        pass
    return 0.0


def transcode_media(
    input_path: str,
    output_path: str,
    target_mode: str = "video",
    target_container: str = "mp4",
    total_duration: Optional[int] = None,
    progress_callback: Optional[Callable[[int], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> bool:
    """
    Executes FFmpeg transcoding using predefined secure profiles and process groups.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    cmd = ["ffmpeg", "-y", "-i", input_path]

    if target_mode == "audio":
        if target_container == "mp3":
            cmd += ["-vn", "-c:a", "libmp3lame", "-q:a", "2"]
        elif target_container == "m4a":
            cmd += ["-vn", "-c:a", "aac", "-b:a", "192k"]
        else:
            cmd += ["-vn", "-c:a", "libmp3lame", "-q:a", "2"]
    else:  # video
        if target_container == "mp4":
            cmd += [
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
            ]
        elif target_container == "webm":
            cmd += [
                "-c:v", "libvpx-vp9",
                "-crf", "32",
                "-b:v", "0",
                "-c:a", "libopus",
            ]
        else:
            cmd += ["-c:v", "libx264", "-c:a", "aac"]

    cmd.append(output_path)

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True,
        start_new_session=True,  # Isolate in own process group
    )

    time_pattern = re.compile(r"time=(\d{2}:\d{2}:\d{2}\.\d+)")

    try:
        if process.stderr:
            for line in process.stderr:
                if cancel_check and cancel_check():
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    process.wait(timeout=3)
                    return False

                match = time_pattern.search(line)
                if match and total_duration and total_duration > 0 and progress_callback:
                    current_secs = _parse_time_to_seconds(match.group(1))
                    pct = min(99, int((current_secs / total_duration) * 100))
                    progress_callback(pct)

        process.wait(timeout=600)
        return process.returncode == 0
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        return False
    except Exception:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except Exception:
            pass
        return False
