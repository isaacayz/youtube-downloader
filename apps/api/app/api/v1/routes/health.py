from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import get_db
from app.services.queue import get_redis_client

router = APIRouter(tags=["Health"])


@router.get("/health/live", status_code=status.HTTP_200_OK)
def liveness():
    """Process liveness probe without external dependency calls."""
    return {"status": "live"}


@router.get("/health/ready", status_code=status.HTTP_200_OK)
def readiness(db: Session = Depends(get_db)):
    """Readiness probe checking PostgreSQL and Redis dependencies."""
    # Check Database
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {str(exc)}"
        )

    # Check Redis
    try:
        redis_client = get_redis_client()
        redis_client.ping()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Redis unavailable: {str(exc)}"
        )

    return {"status": "ready"}
