import os
import shutil
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from app.core.config import settings
from app.models.job import Job
from app.models.asset import Asset
from app.models.job_event import JobEvent
from app.models.setting import AppSetting


def utcnow():
    return datetime.now(timezone.utc)


class MaintenanceService:
    @staticmethod
    def run_cleanup(db: Session) -> Dict[str, Any]:
        """
        Runs a comprehensive maintenance pass:
        1. Expires completed assets whose expires_at is past and removes their files
        2. Cleans stale staging folders older than 24h that are not claimed by active jobs
        3. Prunes job_events older than EVENT_RETENTION_DAYS
        """
        now = utcnow()
        assets_removed = 0
        staging_dirs_cleaned = 0
        events_pruned = 0
        errors = []

        # 1. Expire assets past retention
        expired_assets_query = select(Asset).filter(
            Asset.deleted_at.is_(None),
            Asset.expires_at.is_not(None),
            Asset.expires_at <= now,
        )
        expired_assets = db.execute(expired_assets_query).scalars().all()

        for asset in expired_assets:
            try:
                full_path = os.path.abspath(os.path.join(settings.MEDIA_ROOT, asset.relative_path))
                if full_path.startswith(os.path.abspath(settings.MEDIA_ROOT)) and os.path.exists(full_path):
                    os.remove(full_path)
                    parent_dir = os.path.dirname(full_path)
                    if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                        os.rmdir(parent_dir)

                asset.deleted_at = now
                assets_removed += 1
            except Exception as exc:
                errors.append(f"Failed to delete asset {asset.id}: {str(exc)}")

        # 2. Clean orphaned staging directories older than 24h
        if os.path.exists(settings.STAGING_DIR):
            active_job_ids = {
                str(j_id) for j_id in db.execute(
                    select(Job.id).filter(Job.status.in_(["pending", "queued", "inspecting", "processing", "finalizing"]))
                ).scalars().all()
            }

            cutoff_time = time.time() - (24 * 3600)
            try:
                for entry in os.listdir(settings.STAGING_DIR):
                    entry_path = os.path.join(settings.STAGING_DIR, entry)
                    if os.path.isdir(entry_path):
                        # Don't delete active job staging or uploads folder directly
                        if entry in active_job_ids:
                            continue
                        if entry == "uploads":
                            # Clean uploads older than 24h
                            for upload_entry in os.listdir(entry_path):
                                upload_path = os.path.join(entry_path, upload_entry)
                                if os.path.getmtime(upload_path) < cutoff_time:
                                    shutil.rmtree(upload_path, ignore_errors=True)
                                    staging_dirs_cleaned += 1
                        else:
                            if os.path.getmtime(entry_path) < cutoff_time:
                                shutil.rmtree(entry_path, ignore_errors=True)
                                staging_dirs_cleaned += 1
            except Exception as exc:
                errors.append(f"Staging cleanup error: {str(exc)}")

        # 3. Prune old job_events
        event_cutoff = now - timedelta(days=settings.EVENT_RETENTION_DAYS)
        try:
            delete_events = delete(JobEvent).where(JobEvent.created_at < event_cutoff)
            result = db.execute(delete_events)
            events_pruned = result.rowcount or 0
        except Exception as exc:
            errors.append(f"Event pruning error: {str(exc)}")

        # Save maintenance status
        status_payload = {
            "lastRun": now.isoformat(),
            "assetsRemoved": assets_removed,
            "stagingDirsCleaned": staging_dirs_cleaned,
            "eventsPruned": events_pruned,
            "errors": errors,
            "success": len(errors) == 0,
        }

        setting = db.execute(select(AppSetting).filter_by(key="maintenance_status")).scalar_one_or_none()
        if setting:
            setting.value = status_payload
            setting.updated_at = now
        else:
            setting = AppSetting(key="maintenance_status", value=status_payload, updated_at=now)
            db.add(setting)

        db.commit()
        return status_payload

    @staticmethod
    def get_status(db: Session) -> Dict[str, Any]:
        setting = db.execute(select(AppSetting).filter_by(key="maintenance_status")).scalar_one_or_none()
        if setting and isinstance(setting.value, dict):
            return setting.value
        return {
            "lastRun": None,
            "assetsRemoved": 0,
            "stagingDirsCleaned": 0,
            "eventsPruned": 0,
            "errors": [],
            "success": True,
        }
