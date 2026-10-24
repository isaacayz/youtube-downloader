import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    BigInteger,
    DateTime,
    Text,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from app.db.session import Base


def utcnow():
    return datetime.now(timezone.utc)


class Asset(Base):
    __tablename__ = "assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)

    relative_path = Column(Text, nullable=False)
    original_filename_safe = Column(String(255), nullable=False)
    container = Column(String(20), nullable=False)
    video_codec = Column(String(50), nullable=True)
    audio_codec = Column(String(50), nullable=True)
    duration_seconds = Column(BigInteger, nullable=True)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), nullable=True)

    title = Column(Text, nullable=True)
    creator_label = Column(String(255), nullable=True)
    thumbnail_cache_key = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    delete_error_code = Column(String(100), nullable=True)
