from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Integer,
    DateTime,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from app.db.session import Base


def utcnow():
    return datetime.now(timezone.utc)


class JobEvent(Base):
    __tablename__ = "job_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)

    event_type = Column(String(50), nullable=False)
    phase = Column(String(50), nullable=True)
    progress_percent = Column(Integer, nullable=True)
    safe_message = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("ix_job_events_job_id_created_at", "job_id", "created_at"),
    )
