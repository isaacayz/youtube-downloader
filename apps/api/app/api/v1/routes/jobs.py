import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.job_service import JobService, map_job_to_response
from app.schemas.job import (
    JobCreateRequest,
    JobCreateResponse,
    JobResponse,
    JobListResponse,
)

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=JobCreateResponse)
def create_job(
    request: JobCreateRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    job = JobService.create_job(db, request, idempotency_key=idempotency_key)
    job_id_str = str(job.id)

    return JobCreateResponse(
        jobId=job_id_str,
        status=job.status,
        createdAt=job.created_at,
        statusUrl=f"/api/v1/jobs/{job_id_str}",
        eventsUrl=f"/api/v1/jobs/{job_id_str}/events",
    )


@router.get("", response_model=JobListResponse)
def list_jobs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    jobs, total = JobService.list_jobs(db, limit=limit, offset=offset)
    items = [map_job_to_response(j) for j in jobs]
    return JobListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    job = JobService.get_job(db, parsed_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return map_job_to_response(job)


@router.post("/{job_id}/cancel", status_code=status.HTTP_202_ACCEPTED, response_model=JobResponse)
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    job = JobService.cancel_job(db, parsed_id)
    return map_job_to_response(job)
