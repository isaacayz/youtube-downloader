import os
import shutil
import subprocess
from sqlalchemy import text
from sqlalchemy.orm import Session
from rq import Worker

from app.core.config import settings
from app.services.queue import get_redis_client, get_queue
from app.schemas.system import (
    SystemInfoResponse,
    SystemCapabilities,
    SystemStatusResponse,
    SystemToolsResponse,
)


class SystemService:
    @staticmethod
    def get_system_info() -> SystemInfoResponse:
        return SystemInfoResponse(
            version="0.1.0",
            environment=settings.APP_ENV,
            capabilities=SystemCapabilities(
                youtubeDownloadEnabled=settings.ENABLE_YOUTUBE_DOWNLOAD,
                localUploadEnabled=True,
                maxUploadBytes=settings.MAX_UPLOAD_BYTES,
                maxOutputBytes=settings.MAX_OUTPUT_BYTES,
            ),
        )

    @staticmethod
    def get_system_status(db: Session) -> SystemStatusResponse:
        db_connected = False
        try:
            db.execute(text("SELECT 1"))
            db_connected = True
        except Exception:
            pass

        redis_connected = False
        queue_depth = 0
        worker_count = 0
        active_jobs = 0

        try:
            r = get_redis_client()
            r.ping()
            redis_connected = True
            q = get_queue()
            queue_depth = len(q)
            workers = Worker.all(connection=r)
            worker_count = len(workers)
            for w in workers:
                if w.get_current_job_id():
                    active_jobs += 1
        except Exception:
            pass

        disk_free = 0
        disk_total = 0
        try:
            target_path = settings.STAGING_DIR if os.path.exists(settings.STAGING_DIR) else "."
            usage = shutil.disk_usage(target_path)
            disk_free = usage.free
            disk_total = usage.total
        except Exception:
            pass

        overall_status = "healthy" if (db_connected and redis_connected) else "degraded"

        return SystemStatusResponse(
            status=overall_status,
            queueDepth=queue_depth,
            activeJobs=active_jobs,
            databaseConnected=db_connected,
            redisConnected=redis_connected,
            workerCount=worker_count,
            diskFreeBytes=disk_free,
            diskTotalBytes=disk_total,
        )

    @staticmethod
    def get_system_tools() -> SystemToolsResponse:
        def run_tool_version(cmd: list) -> str | None:
            try:
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=2)
                if res.returncode == 0:
                    return res.stdout.splitlines()[0].strip()
            except Exception:
                pass
            return None

        ffmpeg_ver = run_tool_version(["ffmpeg", "-version"])
        ffprobe_ver = run_tool_version(["ffprobe", "-version"])
        ytdlp_ver = run_tool_version(["yt-dlp", "--version"])
        node_ver = run_tool_version(["node", "--version"])

        return SystemToolsResponse(
            ytDlpVersion=ytdlp_ver,
            ffmpegVersion=ffmpeg_ver,
            ffprobeVersion=ffprobe_ver,
            jsRuntimeVersion=node_ver,
        )
