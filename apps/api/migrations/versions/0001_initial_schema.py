"""Initial schema for jobs, assets, job_events, app_settings, and idempotency

Revision ID: 0001
Revises: 
Create Date: 2026-10-24 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. jobs table
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('phase', sa.String(length=50), nullable=True),
        sa.Column('progress_percent', sa.Integer(), nullable=True),
        sa.Column('progress_bytes', sa.BigInteger(), nullable=True),
        sa.Column('total_bytes', sa.BigInteger(), nullable=True),
        sa.Column('speed_bytes_per_second', sa.BigInteger(), nullable=True),
        sa.Column('eta_seconds', sa.Integer(), nullable=True),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('source_host', sa.String(length=255), nullable=True),
        sa.Column('source_url_redacted', sa.Text(), nullable=True),
        sa.Column('source_url_private', sa.Text(), nullable=True),
        sa.Column('rights_attested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('policy_decision', sa.String(length=50), nullable=False, server_default='allowed'),
        sa.Column('policy_reason_code', sa.String(length=100), nullable=False, server_default='POLICY_APPROVED'),
        sa.Column('requested_container', sa.String(length=20), nullable=True),
        sa.Column('requested_mode', sa.String(length=20), nullable=True),
        sa.Column('requested_quality', sa.String(length=50), nullable=True),
        sa.Column('requested_subtitles', sa.Boolean(), server_default='false'),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('last_error_code', sa.String(length=100), nullable=True),
        sa.Column('last_error_safe_message', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.String(length=255), nullable=True),
        sa.Column('request_fingerprint', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
    )
    op.create_index('ix_jobs_idempotency_key', 'jobs', ['idempotency_key'])
    op.create_index('ix_jobs_status_created_at', 'jobs', ['status', 'created_at'])
    op.create_index('ix_jobs_source_host_created_at', 'jobs', ['source_host', 'created_at'])

    # 2. assets table
    op.create_table(
        'assets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('relative_path', sa.Text(), nullable=False),
        sa.Column('original_filename_safe', sa.String(length=255), nullable=False),
        sa.Column('container', sa.String(length=20), nullable=False),
        sa.Column('video_codec', sa.String(length=50), nullable=True),
        sa.Column('audio_codec', sa.String(length=50), nullable=True),
        sa.Column('duration_seconds', sa.BigInteger(), nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('creator_label', sa.String(length=255), nullable=True),
        sa.Column('thumbnail_cache_key', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delete_error_code', sa.String(length=100), nullable=True),
    )
    op.create_index('ix_assets_expires_at', 'assets', ['expires_at'])

    # 3. job_events table
    op.create_table(
        'job_events',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('phase', sa.String(length=50), nullable=True),
        sa.Column('progress_percent', sa.Integer(), nullable=True),
        sa.Column('safe_message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_job_events_job_id_created_at', 'job_events', ['job_id', 'created_at'])

    # 4. app_settings table
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(length=100), primary_key=True),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 5. idempotency_records table
    op.create_table(
        'idempotency_records',
        sa.Column('key', sa.String(length=255), primary_key=True),
        sa.Column('request_hash', sa.String(length=64), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('idempotency_records')
    op.drop_table('app_settings')
    op.drop_table('job_events')
    op.drop_table('assets')
    op.drop_table('jobs')
