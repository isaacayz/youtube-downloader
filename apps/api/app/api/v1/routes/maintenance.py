from typing import Dict, Any
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.maintenance_service import MaintenanceService

router = APIRouter(prefix="/api/v1/maintenance", tags=["Maintenance"])


@router.post("/cleanup", status_code=status.HTTP_200_OK)
def trigger_cleanup(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Manually triggers a retention cleanup and maintenance pass."""
    return MaintenanceService.run_cleanup(db)


@router.get("/status")
def get_maintenance_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Returns the latest maintenance execution summary."""
    return MaintenanceService.get_status(db)
