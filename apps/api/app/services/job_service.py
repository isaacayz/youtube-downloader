import hashlib
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.core.config import settings
from app.models.job import Job
from app.models.job_event import JobEvent
from app.models.idempotency import IdempotencyRecord
from app.schemas.job import JobCreateRequest, JobResponse, JobProgressSchema
from app.services.queue import get_queue


def utcnow():
    return datetime.now(timezone.utc)


def compute_payload_hash(payload: dict) -> str:
    serialized = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def map_job_to_response(job: Job) -> JobResponse:
    return JobResponse(
        id=str(job.id),
        jobType=job.job_type,
        status=job.status,
        progress=JobProgressSchema(
            phase=job.phase,
            percent=job.progress_percent,
            bytesProcessed=job.progress_bytes,
            totalBytes=job.total_bytes,
            speedBytesPerSecond=job.speed_bytes_per_second,
            etaSeconds=job.eta_seconds,
            updatedAt=job.updated_at,
        ),
        sourceType=job.source_type,
        sourceHost=job.source_host,
        sourceUrlRedacted=job.source_url_redacted,
        requestedContainer=job.requested_container,
        requestedMode=job.requested_mode,
        requestedQuality=job.requested_quality,
        attemptCount=job.attempt_count,
        maxAttempts=job.max_attempts,
        lastErrorCode=job.last_error_code,
        lastErrorSafeMessage=job.last_error_safe_message,
        createdAt=job.created_at,
        updatedAt=job.updated_at,
        startedAt=job.started_at,
        completedAt=job.completed_at,
        expiresAt=job.expires_at,
    )


class JobService:
    @staticmethod
    def create_job(db: Session, request: JobCreateRequest, idempotency_key: Optional[str] = None) -> Job:
        if not request.rightsConfirmed:
            raise HTTPException(
                status_code=422,
                detail="Rights and authorization policy must be confirmed to proceed with media jobs."
            )

        payload_dict = request.model_dump()
        payload_hash = compute_payload_hash(payload_dict)

        # Idempotency validation
        if idempotency_key:
            record = db.execute(
                select(IdempotencyRecord).filter_by(key=idempotency_key)
            ).scalar_one_or_none()

            if record:
                if record.request_hash == payload_hash:
                    # Return original job
                    existing_job = db.execute(
                        select(Job).filter_by(id=record.job_id)
                    ).scalar_one_or_none()
                    if existing_job:
                        return existing_job
                else:
                    raise HTTPException(
                        status_code=409,
                        detail="Idempotency key reused with different request payload."
                    )

        # Determine job type and validate policy
        source_type = request.source.type
        source_url = request.source.url or ""
        source_host = None
        source_url_redacted = None
        job_type = "remote_acquisition"

        if source_type == "synthetic":
            job_type = "synthetic_test"
            source_url_redacted = "synthetic://test-run"
        elif source_type == "url":
            parsed = urlparse(source_url)
            source_host = parsed.netloc.lower()
            source_url_redacted = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

            # Check YouTube policy switch
            if any(domain in source_host for domain in ["youtube.com", "youtu.be"]):
                if not settings.ENABLE_YOUTUBE_DOWNLOAD:
                    raise HTTPException(
                        status_code=422,
                        detail="YouTube source extraction is currently disabled by operator policy."
                    )
        elif source_type == "upload":
            if not request.source.uploadId:
                raise HTTPException(status_code=422, detail="Missing uploadId for upload source.")
            job_type = "file_conversion"
            source_url_redacted = f"upload://{request.source.uploadId}"
            source_url_private = request.source.uploadId
        else:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported source type: {source_type}"
            )

        new_job_id = uuid.uuid4()
        now = utcnow()
        expires_at = now + timedelta(days=settings.OUTPUT_RETENTION_DAYS)

        job = Job(
            id=new_job_id,
            job_type=job_type,
            status="queued",
            phase="enqueued",
            progress_percent=0,
            source_type=source_type,
            source_host=source_host,
            source_url_redacted=source_url_redacted,
            source_url_private=source_url_private if source_type in ["url", "upload"] else None,
            rights_attested_at=now,
            policy_decision="allowed",
            policy_reason_code="POLICY_APPROVED",
            requested_container=request.output.container,
            requested_mode=request.output.mode,
            requested_quality=request.output.quality,
            requested_subtitles=request.output.subtitles,
            idempotency_key=idempotency_key,
            request_fingerprint=payload_hash,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            version=1,
        )

        db.add(job)

        # Log event
        event = JobEvent(
            job_id=new_job_id,
            event_type="job_enqueued",
            phase="enqueued",
            progress_percent=0,
            safe_message="Job accepted and enqueued for background execution.",
            created_at=now,
        )
        db.add(event)

        # Save idempotency record
        if idempotency_key:
            idemp = IdempotencyRecord(
                key=idempotency_key,
                request_hash=payload_hash,
                job_id=new_job_id,
                created_at=now,
                expires_at=now + timedelta(days=1),
            )
            db.add(idemp)

        db.commit()
        db.refresh(job)

        # Enqueue job ID to RQ
        queue = get_queue()
        queue.enqueue("app.jobs.processor.process_media_job", str(job.id))

        return job

    @staticmethod
    def get_job(db: Session, job_id: uuid.UUID) -> Optional[Job]:
        return db.execute(select(Job).filter_by(id=job_id)).scalar_one_or_none()

    @staticmethod
    def list_jobs(db: Session, limit: int = 50, offset: int = 0) -> Tuple[List[Job], int]:
        total = db.query(Job).count()
        query = select(Job).order_by(desc(Job.created_at)).limit(limit).offset(offset)
        jobs = db.execute(query).scalars().all()
        return jobs, total

    @staticmethod
    def cancel_job(db: Session, job_id: uuid.UUID) -> Job:
        job = db.execute(select(Job).filter_by(id=job_id)).scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if job.status in ["completed", "failed", "cancelled", "expired"]:
            raise HTTPException(status_code=409, detail=f"Cannot cancel job in state: {job.status}")

        if job.status in ["pending", "queued"]:
            job.status = "cancelled"
            job.phase = "cancelled"
        else:
            job.status = "cancel_requested"

        job.updated_at = utcnow()
        job.version += 1

        event = JobEvent(
            job_id=job.id,
            event_type="cancellation_requested",
            phase=job.phase,
            progress_percent=job.progress_percent,
            safe_message="User requested cancellation.",
            created_at=utcnow(),
        )
        db.add(event)
        db.commit()
        db.refresh(job)
        return job
