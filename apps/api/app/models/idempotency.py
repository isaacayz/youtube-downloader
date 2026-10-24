from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.db.session import Base


def utcnow():
    return datetime.now(timezone.utc)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    key = Column(String(255), primary_key=True)
    request_hash = Column(String(64), nullable=False)
    job_id = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)
