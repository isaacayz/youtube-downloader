import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    BigInteger,
    DateTime,
    Boolean,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from app.db.session import Base


def utcnow():
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type = Column(String(50), nullable=False, default="remote_acquisition")
    status = Column(String(50), nullable=False, default="pending")
    phase = Column(String(50), nullable=True)

    progress_percent = Column(Integer, nullable=True)
    progress_bytes = Column(BigInteger, nullable=True)
    total_bytes = Column(BigInteger, nullable=True)
    speed_bytes_per_second = Column(BigInteger, nullable=True)
    eta_seconds = Column(Integer, nullable=True)

    source_type = Column(String(50), nullable=False, default="url")
    source_host = Column(String(255), nullable=True)
    source_url_redacted = Column(Text, nullable=True)
    source_url_private = Column(Text, nullable=True)

    rights_attested_at = Column(DateTime(timezone=True), nullable=True)
    policy_decision = Column(String(50), nullable=False, default="allowed")
    policy_reason_code = Column(String(100), nullable=False, default="POLICY_APPROVED")

    requested_container = Column(String(20), nullable=True)
    requested_mode = Column(String(20), nullable=True)
    requested_quality = Column(String(50), nullable=True)
    requested_subtitles = Column(Boolean, default=False)

    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    last_error_code = Column(String(100), nullable=True)
    last_error_safe_message = Column(Text, nullable=True)

    idempotency_key = Column(String(255), nullable=True, index=True)
    request_fingerprint = Column(String(64), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    version = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index("ix_jobs_status_created_at", "status", "created_at"),
        Index("ix_jobs_source_host_created_at", "source_host", "created_at"),
    )
