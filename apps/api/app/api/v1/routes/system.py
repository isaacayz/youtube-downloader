from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.system_service import SystemService
from app.schemas.system import (
    SystemInfoResponse,
    SystemStatusResponse,
    SystemToolsResponse,
)

router = APIRouter(prefix="/api/v1/system", tags=["System"])


@router.get("/info", response_model=SystemInfoResponse)
def get_system_info():
    return SystemService.get_system_info()


@router.get("/status", response_model=SystemStatusResponse)
def get_system_status(db: Session = Depends(get_db)):
    return SystemService.get_system_status(db)


@router.get("/tools", response_model=SystemToolsResponse)
def get_system_tools():
    return SystemService.get_system_tools()
