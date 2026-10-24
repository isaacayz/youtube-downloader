from typing import Optional, Any, Dict
from pydantic import BaseModel, Field


class ProblemDetail(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    code: str
    detail: str
    requestId: Optional[str] = None
    invalidParams: Optional[Dict[str, Any]] = None
