import os
import glob
import shutil
import uuid
import signal
import subprocess
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.job import Job
from app.models.asset import Asset
from app.models.job_event import JobEvent
from app.core.config import worker_settings
from app.media.media_tools import probe_media, transcode_media, calculate_file_checksum
from app.source_adapters.registry import registry


def utcnow():
    return datetime.now(timezone.utc)


def log_event(db: Session, job_id: uuid.UUID, event_type: str, phase: str, percent: int, message: str):
    event = JobEvent(
        job_id=job_id,
        event_type=event_type,
        phase=phase,
        progress_percent=percent,
        safe_message=message,
        created_at=utcnow(),
    )
    db.add(event)
    db.commit()


def check_cancellation(db: Session, job_id: uuid.UUID) -> bool:
    job = db.execute(select(Job).filter_by(id=job_id)).scalar_one_or_none()
    if job and job.status in ["cancel_requested", "cancelled"]:
        job.status = "cancelled"
        job.phase = "cancelled"
        job.updated_at = utcnow()
        db.commit()
        return True
    return False


def process_media_job(job_id_str: str):
    job_uuid = uuid.UUID(job_id_str)
    db: Session = SessionLocal()

    try:
        job = db.execute(select(Job).filter_by(id=job_uuid)).scalar_one_or_none()
        if not job:
            return

        if job.status in ["cancel_requested", "cancelled"]:
            job.status = "cancelled"
            job.phase = "cancelled"
            job.updated_at = utcnow()
            db.commit()
            return

        job.status = "inspecting"
        job.phase = "inspect"
        job.started_at = utcnow()
        job.updated_at = utcnow()
        job.attempt_count += 1
        db.commit()

        log_event(db, job.id, "job_started", "inspect", 5, "Job execution claimed by media worker.")

        if job.job_type == "synthetic_test":
            _run_synthetic_job(db, job)
        elif job.job_type == "file_conversion":
            _run_file_conversion(db, job)
        elif job.job_type == "remote_acquisition":
            _run_remote_acquisition(db, job)
        else:
            job.status = "failed"
            job.last_error_code = "JOB_TYPE_UNSUPPORTED"
            job.last_error_safe_message = f"Unsupported job type: {job.job_type}"
            job.updated_at = utcnow()
            db.commit()
            log_event(db, job.id, "job_failed", "inspect", 0, job.last_error_safe_message)

    except Exception as exc:
        db.rollback()
        try:
            job = db.execute(select(Job).filter_by(id=job_uuid)).scalar_one_or_none()
            if job and job.status not in ["completed", "cancelled"]:
                job.status = "failed"
                job.last_error_code = "INTERNAL_ERROR"
                job.last_error_safe_message = f"Execution failed: {str(exc)}"
                job.updated_at = utcnow()
                db.commit()
                log_event(db, job.id, "job_failed", "error", 0, job.last_error_safe_message)
        except Exception:
            pass
        raise exc
    finally:
        db.close()


def _run_synthetic_job(db: Session, job: Job):
    import time
    stages = [
        ("download", 30, "Simulating media retrieval..."),
        ("transcode", 65, "Simulating format conversion and validation..."),
        ("finalize", 95, "Simulating ffprobe integrity verification..."),
    ]

    for phase, percent, msg in stages:
        time.sleep(1.2)
        if check_cancellation(db, job.id):
            log_event(db, job.id, "job_cancelled", "cancelled", percent, "Job cancelled by operator.")
            return

        job.status = "processing" if percent < 90 else "finalizing"
        job.phase = phase
        job.progress_percent = percent
        job.updated_at = utcnow()
        db.commit()
        log_event(db, job.id, f"phase_{phase}", phase, percent, msg)

    time.sleep(0.8)
    job.status = "completed"
    job.phase = "completed"
    job.progress_percent = 100
    job.completed_at = utcnow()
    job.updated_at = utcnow()
    db.commit()
    log_event(db, job.id, "job_completed", "completed", 100, "Synthetic pipeline completed.")


def _run_file_conversion(db: Session, job: Job):
    upload_id = job.source_url_private
    if not upload_id:
        raise ValueError("Missing upload identifier for file conversion job.")

    upload_dir = os.path.join(worker_settings.STAGING_DIR, "uploads", upload_id)
    if not os.path.exists(upload_dir) or not os.listdir(upload_dir):
        raise FileNotFoundError(f"Staged upload file not found for upload {upload_id}")

    input_filename = os.listdir(upload_dir)[0]
    input_file_path = os.path.join(upload_dir, input_filename)

    staging_dir = os.path.join(worker_settings.STAGING_DIR, str(job.id), str(job.attempt_count))
    os.makedirs(staging_dir, exist_ok=True)

    try:
        input_probe = probe_media(input_file_path)
        if not input_probe:
            raise ValueError("Input file failed ffprobe integrity check.")

        duration = input_probe.get("duration")
        base_name, _ = os.path.splitext(input_filename)
        container = (job.requested_container or "mp4").lower()
        mode = (job.requested_mode or "video").lower()
        output_temp_filename = f"converted.{container}"
        output_temp_path = os.path.join(staging_dir, output_temp_filename)

        job.status = "processing"
        job.phase = "transcode"
        job.progress_percent = 10
        job.updated_at = utcnow()
        db.commit()
        log_event(db, job.id, "conversion_started", "transcode", 10, f"Beginning transcode to {container.upper()}.")

        def on_progress(percent: int):
            job.progress_percent = max(10, min(95, percent))
            job.updated_at = utcnow()
            db.commit()

        success = transcode_media(
            input_path=input_file_path,
            output_path=output_temp_path,
            target_mode=mode,
            target_container=container,
            total_duration=duration,
            progress_callback=on_progress,
            cancel_check=lambda: check_cancellation(db, job.id),
        )

        if not success:
            if check_cancellation(db, job.id):
                return
            raise RuntimeError("Transcoding process failed or was interrupted.")

        # Finalizing: probe output
        job.status = "finalizing"
        job.phase = "validate"
        job.progress_percent = 96
        job.updated_at = utcnow()
        db.commit()
        log_event(db, job.id, "validation_started", "validate", 96, "Validating output media integrity.")

        output_probe = probe_media(output_temp_path)
        if not output_probe:
            raise ValueError("Generated output failed ffprobe validation.")

        sha256 = calculate_file_checksum(output_temp_path)
        size_bytes = os.path.getsize(output_temp_path)

        # Atomic move to downloads area
        asset_id = uuid.uuid4()
        final_filename = f"{base_name}.{container}"
        asset_rel_dir = os.path.join("assets", str(asset_id))
        asset_full_dir = os.path.join(worker_settings.MEDIA_ROOT, asset_rel_dir)
        os.makedirs(asset_full_dir, exist_ok=True)
        final_output_path = os.path.join(asset_full_dir, final_filename)

        shutil.move(output_temp_path, final_output_path)

        asset = Asset(
            id=asset_id,
            job_id=job.id,
            relative_path=os.path.join(asset_rel_dir, final_filename),
            original_filename_safe=final_filename,
            container=container,
            video_codec=output_probe.get("video_codec"),
            audio_codec=output_probe.get("audio_codec"),
            duration_seconds=output_probe.get("duration"),
            size_bytes=size_bytes,
            sha256=sha256,
            title=base_name,
            created_at=utcnow(),
            expires_at=job.expires_at,
        )
        db.add(asset)

        job.status = "completed"
        job.phase = "completed"
        job.progress_percent = 100
        job.completed_at = utcnow()
        job.updated_at = utcnow()
        db.commit()

        log_event(db, job.id, "job_completed", "completed", 100, "Media conversion successfully completed.")
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def _run_remote_acquisition(db: Session, job: Job):
    url = job.source_url_private
    if not url:
        raise ValueError("Missing private source URL for acquisition.")

    adapter = registry.get_adapter(url)
    if not adapter:
        raise ValueError(f"No adapter registered for source URL: {url}")

    is_allowed, reason_code, message = adapter.validate(url)
    if not is_allowed:
        job.status = "failed"
        job.last_error_code = reason_code
        job.last_error_safe_message = message
        job.updated_at = utcnow()
        db.commit()
        log_event(db, job.id, "policy_rejected", "inspect", 0, message)
        return

    staging_dir = os.path.join(worker_settings.STAGING_DIR, str(job.id), str(job.attempt_count))
    os.makedirs(staging_dir, exist_ok=True)

    try:
        job.status = "processing"
        job.phase = "download"
        job.progress_percent = 15
        job.updated_at = utcnow()
        db.commit()
        log_event(db, job.id, "download_started", "download", 15, "Acquiring media from source.")

        container = (job.requested_container or "mp4").lower()
        mode = (job.requested_mode or "video").lower()

        # Build yt-dlp child process command
        output_template = os.path.join(staging_dir, "%(title).80s.%(ext)s")
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--restrict-filenames",
            "--no-warnings",
            "--socket-timeout", "20",
            "-o", output_template,
        ]

        if mode == "audio":
            cmd += ["-x", "--audio-format", container if container in ["mp3", "m4a"] else "mp3"]
        else:
            if container == "mp4":
                cmd += ["--merge-output-format", "mp4"]
            elif container == "webm":
                cmd += ["--merge-output-format", "webm"]

        cmd.append(url)

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            start_new_session=True,
        )

        try:
            if process.stdout:
                for line in process.stdout:
                    if check_cancellation(db, job.id):
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                        process.wait(timeout=3)
                        return
                    # Parse yt-dlp percent e.g. "[download]  45.0% of"
                    if "[download]" in line and "%" in line:
                        try:
                            parts = line.split("%")[0].split()
                            val = float(parts[-1])
                            pct = min(90, max(15, int(val * 0.75 + 15)))
                            job.progress_percent = pct
                            job.updated_at = utcnow()
                            db.commit()
                        except Exception:
                            pass

            process.wait(timeout=1800)
            if process.returncode != 0:
                raise RuntimeError(f"Source acquisition failed with exit code {process.returncode}")
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            raise TimeoutError("Media download exceeded maximum timeout.")

        # Locate downloaded artifact in staging
        downloaded_files = [f for f in glob.glob(os.path.join(staging_dir, "*")) if os.path.isfile(f)]
        if not downloaded_files:
            raise FileNotFoundError("No output media was produced by the acquisition pipeline.")

        downloaded_path = downloaded_files[0]
        filename = os.path.basename(downloaded_path)
        base_name, ext = os.path.splitext(filename)
        ext_clean = ext.lstrip(".").lower()

        # Validate with ffprobe
        job.status = "finalizing"
        job.phase = "validate"
        job.progress_percent = 95
        job.updated_at = utcnow()
        db.commit()
        log_event(db, job.id, "validation_started", "validate", 95, "Verifying acquired media stream integrity.")

        probe_info = probe_media(downloaded_path)
        if not probe_info:
            raise ValueError("Downloaded file failed ffprobe integrity validation.")

        sha256 = calculate_file_checksum(downloaded_path)
        size_bytes = os.path.getsize(downloaded_path)

        # Atomic move to downloads area
        asset_id = uuid.uuid4()
        asset_rel_dir = os.path.join("assets", str(asset_id))
        asset_full_dir = os.path.join(worker_settings.MEDIA_ROOT, asset_rel_dir)
        os.makedirs(asset_full_dir, exist_ok=True)
        final_output_path = os.path.join(asset_full_dir, filename)

        shutil.move(downloaded_path, final_output_path)

        asset = Asset(
            id=asset_id,
            job_id=job.id,
            relative_path=os.path.join(asset_rel_dir, filename),
            original_filename_safe=filename,
            container=ext_clean,
            video_codec=probe_info.get("video_codec"),
            audio_codec=probe_info.get("audio_codec"),
            duration_seconds=probe_info.get("duration"),
            size_bytes=size_bytes,
            sha256=sha256,
            title=base_name,
            created_at=utcnow(),
            expires_at=job.expires_at,
        )
        db.add(asset)

        job.status = "completed"
        job.phase = "completed"
        job.progress_percent = 100
        job.completed_at = utcnow()
        job.updated_at = utcnow()
        db.commit()

        log_event(db, job.id, "job_completed", "completed", 100, "Remote source acquired and finalized successfully.")
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)
