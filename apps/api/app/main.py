import uuid
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.api.v1.routes import health, system, jobs, uploads, sources, assets

app = FastAPI(
    title="Local Media Downloader API",
    description="Local-first media acquisition and conversion service",
    version="0.1.0",
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url="/redoc" if settings.APP_ENV != "production" else None,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(health.router)
app.include_router(system.router)
app.include_router(jobs.router)
app.include_router(uploads.router)
app.include_router(sources.router)
app.include_router(assets.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = str(uuid.uuid4())
    code_map = {
        400: "VALIDATION_ERROR",
        403: "SOURCE_NOT_ALLOWED",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "FILE_TOO_LARGE",
        422: "POLICY_VIOLATION",
        429: "QUOTA_EXCEEDED",
        503: "DEPENDENCY_UNAVAILABLE",
    }
    code = code_map.get(exc.status_code, "REQUEST_ERROR")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": "about:blank",
            "title": exc.detail if isinstance(exc.detail, str) else "Request error",
            "status": exc.status_code,
            "code": code,
            "detail": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            "requestId": request_id,
        },
        headers={"Content-Type": "application/problem+json"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = str(uuid.uuid4())
    return JSONResponse(
        status_code=422,
        content={
            "type": "about:blank",
            "title": "Validation error",
            "status": 422,
            "code": "VALIDATION_ERROR",
            "detail": "The request body or parameters failed validation.",
            "requestId": request_id,
            "invalidParams": exc.errors(),
        },
        headers={"Content-Type": "application/problem+json"},
    )
