---
title: "Local Media Downloader"
subtitle: "Architecture and Implementation Blueprint"
date: "24 October 2026"
---

**Document version:** 1.0  
**Target deployment:** Self-hosted server, Docker Compose, local network optional  
**Primary languages:** Python and TypeScript  
**Design status:** Proposed implementation baseline

---

## Executive summary

Build a local-first media acquisition and conversion application with a React/TypeScript web UI, a Python/FastAPI API, an isolated Python worker, yt-dlp and FFmpeg for supported and authorized sources, Redis with RQ for background processing, PostgreSQL for durable application state, and local disk storage for finished media.

The application must not depend on a cloud control plane. It should start with Docker Compose, retain its database and media files across restarts, run background tasks outside HTTP requests, and be maintainable through explicit service boundaries and versioned APIs.

**Recommended baseline:**

- **Web:** React, TypeScript, Vite, Nginx.
- **API:** Python, FastAPI, Pydantic, SQLAlchemy, Alembic.
- **Queue:** Redis and RQ.
- **Worker:** Python, yt-dlp, FFmpeg/ffprobe, and a supported JavaScript runtime for yt-dlp's applicable extraction components.
- **Database:** PostgreSQL.
- **Storage:** a host-mounted downloads directory, with temporary and completed files separated.
- **Operations:** Docker Compose, container health checks, structured logs, backups, and a maintenance process.

This is designed first for one trusted local operator, but it leaves room for controlled LAN access, additional worker replicas, separate profiles, and a larger media library later.

> **Source permissions:** YouTube's terms restrict downloading or otherwise using content except where expressly authorized by the service or with the required permission. The source integration must therefore process only content and workflows the operator is authorized to download. This blueprint does not design DRM circumvention, credential extraction, or bypasses for protected content. Review YouTube's current terms and the rights for each source before enabling a source adapter. See References [1]-[2].

## 1. Goals, constraints, and non-goals

### 1.1 Goals

1. Enter a supported source URL or upload a local media file.
2. Inspect available metadata and supported output options before starting a job.
3. Support video output (initially MP4 and WebM where available) and audio output (MP3 and M4A).
4. Run slow network and conversion operations asynchronously.
5. Show job state, progress, errors, retry information, and completed outputs.
6. Keep completed files on the self-hosted server and make them available through the local web UI.
7. Support queue recovery, bounded retries, cleanup, backup, restore, and routine updates.
8. Default to a localhost-only deployment; make LAN exposure an explicit configuration choice.
9. Make source-specific logic replaceable so changes in any one source do not rewrite the rest of the app.
10. Respect user rights, source terms, rate limits, and applicable law.

### 1.2 Initial non-goals

- Public multi-tenant hosting or an internet-facing public service.
- DRM removal, access-control bypass, session-cookie harvesting, or extraction of private/authenticated content.
- Cloud storage or cloud-managed queues/databases.
- Transcoding every source into every codec combination.
- Video editing, streaming, transcoding farms, or a full media-server catalog in the first release.
- Downloading an entire playlist by default. Batch/playlist processing must be an explicit feature with limits.

### 1.3 Operating assumptions

- The container host has Docker Engine and Docker Compose v2.
- The host has reliable outbound internet access for supported remote sources and image updates.
- The deployment owns a persistent disk location for PostgreSQL and media.
- One worker and one concurrent media job is the safe default. Concurrency should be increased only after observing CPU, RAM, disk throughput, and network usage.
- YouTube-specific behavior can change independently of this codebase. Source adapter dependencies must be tested and updated intentionally.

## 2. Technology decisions

| Layer | Choice | Why | Boundary |
|---|---|---|---|
| UI | React + TypeScript + Vite | Fast client-side UI, strong typing, broad ecosystem | No source extraction logic in browser |
| Static web server | Nginx | Serves built assets and reverse-proxies `/api/` | Only service with a published host port |
| API | Python + FastAPI | Validation, type-driven request contracts, OpenAPI docs | Must not run media jobs inside request workers |
| Validation/settings | Pydantic Settings | Centralized typed configuration and validation | Reject unsafe config at startup |
| ORM/migrations | SQLAlchemy + Alembic | Durable state and repeatable schema changes | Migrations are reviewed and versioned |
| Queue | Redis + RQ | Small operational footprint for Python background work | Queue is not the durable application database |
| Worker | Python | Native integration with the source engine and the queue | Runs non-root, limited resources, restricted filesystem |
| Source engine | yt-dlp where permitted | Mature source-extraction tool with evolving site support | Encapsulated behind source adapters and policy checks |
| Media processing | FFmpeg + ffprobe | Media probing, stream merging, remuxing and conversion | Exact binaries/builds and licenses are tracked |
| Database | PostgreSQL | Durable jobs, asset catalog, events and settings; safer growth path for multiple workers | Not exposed to host network by default |
| File storage | Local host-mounted directory | Simple offline persistence and straightforward backup | Files are never stored in the container writable layer |
| Deployment | Docker Compose | Reproducible local deployment and isolated services | Only intended ports are published |
| Testing | pytest, HTTPX, React Testing Library, Playwright | Unit, API, UI, and container integration coverage | Tests use local fixtures rather than live sites when possible |

### 2.1 Important yt-dlp runtime dependency

The worker image must include the **FFmpeg and ffprobe executables**, not merely a Python package named `ffmpeg`. Current yt-dlp documentation also recommends `yt-dlp-ejs` and a supported JavaScript runtime/engine for full YouTube support. Include the required runtime in the worker image, pin compatible versions, and test the complete image after every update. See References [3]-[4].

The application can be written in Python and TypeScript even though the worker image contains other executable tools. These tools should be called as child processes with fixed argument arrays, never by composing a shell command from user-supplied text.

### 2.2 Why a persistent database is included

Redis is the queue and coordination layer; it should not be the only durable record of completed jobs or the media library. PostgreSQL stores the canonical job state, source metadata, outputs, event history, settings, and retention timestamps. The queue can be rebuilt or reconciled from application state after a Redis issue.

A much smaller single-user installation could replace PostgreSQL with SQLite, but this blueprint uses PostgreSQL as the default because the intended server may eventually have more than one worker or user.

## 3. High-level architecture

```text
Browser -> Web (React/Nginx) -> API (FastAPI) -> PostgreSQL
                                      |
                                      +-> Redis/RQ -> Worker (Python)
                                                       |-> authorized source
                                                       `-> staging/downloads
```

### 3.1 Service responsibilities

**Web** serves the single-page application and proxies same-origin `/api` calls to the API. It does not receive Redis or database credentials and does not run source tools.

**API** validates requests, enforces the source policy and resource limits, creates records, enqueues work, exposes status and history, authorizes file delivery, and supplies health endpoints. It should remain responsive even while a long video is downloading or transcoding.

**Worker** claims jobs, revalidates source policy, inspects metadata where appropriate, performs acquisition or conversion, updates durable state, and finalizes files. It is the only service that requires source-download egress and media-tool executables.

**Redis** supports RQ queue operations, job coordination, and transient queue state. Configure authentication only where needed for the network boundary; never publish its port to the host.

**PostgreSQL** is the source of truth for jobs, assets, settings, audit events and user profiles if multi-user operation is added.

**Maintenance process** expires outputs, reconciles abandoned work, prunes old events according to policy, checks storage thresholds, and cleans stale partial files. It can start as a scheduled command in the worker image and later become a dedicated Compose service.

### 3.2 Data flow

1. The browser submits a URL or uploads a file.
2. The API validates the request, normalizes supported URL forms, applies source policy, and inspects or queues an inspection operation.
3. The API creates a job record and dispatches an opaque job identifier plus validated options to RQ. It should not place arbitrary command-line arguments in the queue payload.
4. The worker loads the canonical job record, revalidates it, and transitions the job to `processing`.
5. The worker writes to a job-specific staging directory, reports coarse progress updates, and runs the approved media pipeline.
6. The worker validates the output with `ffprobe`, calculates size/duration/format, and atomically moves successful output into the completed area.
7. The worker persists the final asset record and `completed` status.
8. The UI polls or subscribes to server-sent events. A download route checks access and streams the selected file.
9. A retention process expires old outputs and removes files only after confirming that no active job still owns them.

## 4. Container topology and local deployment

### 4.1 Baseline services

| Service | Host port | Networks | Persistent data | Notes |
|---|---|---|---|---|
| `web` | `127.0.0.1:3000` -> container `8080` | `frontend` | None required | Nginx + static UI; reverse proxy to API as an unprivileged process |
| `api` | None | `frontend`, `backend` | Upload staging read/write; completed downloads read-only | No host-published port |
| `worker` | None | `backend`, `egress` | Staging and downloads read/write | Needs outbound access only for permitted source retrieval |
| `redis` | None | `backend` | `redis-data` | Queue state; private network only |
| `postgres` | None | `backend` | `postgres-data` | Canonical application state; private network only |
| `maintenance` | None | `backend`, `media` | Same media area | Optional separate scheduled process in a later phase |

Compose service names are DNS names on shared networks; refer to `postgres`, `redis`, and `api` by service name rather than fixed IP. Docker Compose networking and service discovery are documented in Reference [5].

### 4.2 Network design

- Publish only the web interface, bound to `127.0.0.1` by default.
- Do not publish the API, Redis, PostgreSQL, or worker ports.
- Keep Redis and PostgreSQL on the backend network only.
- Keep source egress limited operationally to the worker where practical. The worker needs internet access; the database and queue do not.
- A local port binding is not a substitute for application security. Enforce same-origin requests, validate `Host`/`Origin`, use a restrictive Content Security Policy, and avoid permissive CORS.
- If LAN access is later required, bind to a chosen LAN address or put the app behind an authenticated reverse proxy. Enable authentication, TLS, rate limits, and firewall restrictions before exposing it beyond the host.

### 4.3 Suggested repository layout

```text
local-media-downloader/
|-- compose.yaml
|-- .env.example
|-- README.md
|-- docs/
|   |-- architecture.md
|   |-- api.md
|   |-- operations.md
|   `-- threat-model.md
|-- apps/
|   |-- web/
|   |   |-- src/
|   |   |   |-- api/
|   |   |   |-- components/
|   |   |   |-- features/
|   |   |   |-- hooks/
|   |   |   |-- pages/
|   |   |   `-- types/
|   |   |-- nginx.conf
|   |   |-- Dockerfile
|   |   `-- package.json
|   |-- api/
|   |   |-- app/
|   |   |   |-- api/v1/routes/
|   |   |   |-- core/
|   |   |   |-- db/
|   |   |   |-- models/
|   |   |   |-- schemas/
|   |   |   |-- services/
|   |   |   |-- source_adapters/
|   |   |   `-- main.py
|   |   |-- migrations/
|   |   |-- tests/
|   |   |-- Dockerfile
|   |   `-- pyproject.toml
|   `-- worker/
|       |-- app/
|       |   |-- jobs/
|       |   |-- media/
|       |   |-- source_adapters/
|       |   |-- policy.py
|       |   `-- worker.py
|       |-- tests/
|       |-- Dockerfile
|       `-- pyproject.toml
|-- infra/
|   |-- postgres/init/          # optional first-run initialization only
|   `-- scripts/
|       |-- backup.sh
|       |-- restore.sh
|       `-- healthcheck.sh
`-- data/                       # host-mounted runtime data; gitignored
    |-- downloads/
    |-- staging/
    `-- backups/
```

Do not commit `.env`, database dumps, cookies, downloaded media, or other runtime artifacts.

## 5. Product scope and screens

### 5.1 Screens for release 1

1. **Home / Add media:** paste a supported URL or choose a local file; show validation results clearly.
2. **Source preview:** title, thumbnail where permitted, duration, available formats, estimated output and policy result.
3. **Format selection:** video/audio mode, container, quality preset, and subtitle selection where supported and authorized.
4. **Queue:** queued, inspecting, downloading, processing, finalizing, completed, failed and cancelled jobs.
5. **Job details:** progress, elapsed time, output information, safe error description, retry action if eligible.
6. **Downloads library:** completed files, format, size, duration, creation date, expiry, download and delete actions.
7. **Settings:** concurrency, retention period, default output format, storage path status, permitted source categories, and update status.
8. **System status:** service health, disk usage, worker availability, queue depth, tool versions, and last successful cleanup.

### 5.2 User-visible behaviors

- Disable the start button while the request is being validated or submitted.
- Make unknown duration and size values explicit; do not invent estimates.
- Explain unsupported formats and unsupported sources with safe, actionable messages.
- Persist history across container restarts.
- Keep UI progress smooth without writing every percentage update to PostgreSQL. Persist meaningful state changes and coarse milestones; keep volatile progress in queue metadata or an event stream.
- When a job fails, expose a concise classification and correlation ID, not a raw stack trace or secret-bearing URL.
- Cancel must terminate the actual child process and clean partial files, not just change a database flag.

## 6. Source adapter and authorization policy

### 6.1 Adapter interface

Keep source-specific behavior behind a stable internal interface. Each adapter should expose equivalent operations:

- `identify(url)` - identify a supported source host and content type.
- `validate(url, policy_context)` - normalize and decide if the source is permitted.
- `inspect(url)` - return a minimal metadata model and supported capabilities.
- `acquire(job, destination)` - perform acquisition only when policy permits it.
- `health()` - report the adapter/runtime version and basic availability.

Implement an adapter registry rather than embedding domain checks in every API route. The API and worker must both call the same policy package. The worker must revalidate because queued jobs can outlive configuration changes.

### 6.2 YouTube-specific boundary

A YouTube URL alone is not proof that downloading is authorized. The UI can accept YouTube links for identification or permitted metadata features, but actual retrieval must be enabled only through a route that is authorized by YouTube and the rights holder, or otherwise permitted under applicable law. A user checkbox is an acknowledgement, not proof of a license.

For creator-owned content, provide documentation for exporting or obtaining the user's own file through YouTube's supported creator tools, then importing that local file for conversion. Do not build features that extract login cookies, evade access restrictions, defeat DRM, or try to bypass anti-download controls. Check YouTube's current terms before changing this policy. See Reference [1].

### 6.3 Capabilities response

The API should advertise formats and features from the selected source and installed media tools. Example:

```json
{
  "source": "authorized-source",
  "metadata": {
    "title": "Example title",
    "durationSeconds": 245,
    "thumbnailAvailable": true
  },
  "capabilities": {
    "videoContainers": ["mp4", "webm"],
    "audioContainers": ["mp3", "m4a"],
    "qualityPresets": ["best-available", "1080p", "720p", "480p", "360p"],
    "subtitles": false,
    "playlist": false
  },
  "policy": {
    "decision": "allowed",
    "reasonCode": "SOURCE_ALLOWED"
  }
}
```

This is illustrative. Only advertise options the adapter and installed FFmpeg build can actually provide. Format availability depends on the specific source and its current implementation.

## 7. API design standards

### 7.1 General conventions

- Prefix: `/api/v1`.
- JSON request and response bodies except upload/download streams and server-sent events.
- Use UUIDs for job and asset IDs.
- Use UTC timestamps in ISO 8601 format.
- Use cursor or offset pagination with a hard maximum page size; prefer `limit` plus opaque cursor for history.
- Return `202 Accepted` when a long-running operation has been queued.
- Require an `Idempotency-Key` for job creation. Repeated requests with the same key and same payload return the original job; the same key with a different payload returns `409 Conflict`.
- Use `application/problem+json`-style errors with stable `code`, human-readable `detail`, `requestId`, and optional field validation details.
- Never return raw stack traces or internal filesystem paths in production responses.
- Use consistent status names and enum values across UI, API, database, and worker.
- Keep OpenAPI generated from FastAPI and include examples for each request/response model.

### 7.2 Error shape

```json
{
  "type": "about:blank",
  "title": "Source is not supported",
  "status": 422,
  "code": "SOURCE_NOT_SUPPORTED",
  "detail": "This source type is not enabled in the current configuration.",
  "requestId": "f4e6a4d8-3fc5-4d92-83ee-efbb9af90001"
}
```

Suggested error codes, grouped for easier handling:

- **Input and policy:** `INVALID_URL`, `SOURCE_NOT_SUPPORTED`, `SOURCE_NOT_ALLOWED`, `RIGHTS_CONFIRMATION_REQUIRED`.
- **Source and media:** `SOURCE_UNAVAILABLE`, `FORMAT_UNAVAILABLE`, `FILE_TOO_LARGE`, `OUTPUT_EXPIRED`.
- **Jobs, limits and dependencies:** `QUOTA_EXCEEDED`, `QUEUE_UNAVAILABLE`, `JOB_NOT_CANCELLABLE`, `JOB_NOT_RETRYABLE`, `DISK_SPACE_LOW`, `INTERNAL_ERROR`.

## 8. Endpoint inventory

### 8.1 Health and service information

- `GET /health/live` - **200.** Process liveness. No database call; use for the container liveness check.
- `GET /health/ready` - **200 / 503.** Readiness check of PostgreSQL and Redis using short timeouts.
- `GET /api/v1/system/info` - **200.** App/API version and enabled capabilities. Never return secrets, host paths, environment values or internal addresses.
- `GET /api/v1/system/status` - **200.** Queue depth, worker status, disk space and dependency status. Protect this view if LAN mode is enabled.
- `GET /api/v1/system/tools` - **200.** yt-dlp, FFmpeg, ffprobe and JavaScript runtime versions. Sanitize command output.

### 8.2 Source inspection and uploads

- `GET /api/v1/sources/capabilities` - **200.** Lists enabled source categories and app-wide output capabilities; it does not mean every URL is downloadable.
- `POST /api/v1/sources/inspect` - **200.** Validates a URL and returns metadata/capabilities. Enforce source policy, timeouts, rate limits and SSRF protections.
- `POST /api/v1/uploads` - **201.** Uploads a local media file for conversion. Use multipart streaming, hard size limits, and staging; never accept executable files as media.
- `GET /api/v1/uploads/{uploadId}` - **200.** Inspects uploaded input and its status. Add authorization/ownership checks if multi-user.
- `DELETE /api/v1/uploads/{uploadId}` - **204.** Deletes an unused upload; reject if an active job consumes it.

**Inspect request:**

```json
{
  "url": "https://source.example/media/123",
  "purpose": "download-or-convert",
  "rightsConfirmed": true
}
```

`rightsConfirmed` records user acknowledgement, but the adapter must still independently enforce the configured policy. The API must not automatically fetch arbitrary URLs just because they parse as valid URLs.

**Inspect response:** use the capabilities response in Section 6.3, plus a stable opaque `inspectionId` if the inspection needs to be referenced when the job is created.

### 8.3 Job lifecycle

- `POST /api/v1/jobs` - **202.** Creates and enqueues a source acquisition or file-conversion job. Validate options, rights/policy and idempotency before enqueueing.
- `GET /api/v1/jobs` - **200.** Lists job history. Filter by `status`, `type`, `createdAfter`, and `createdBefore`; paginate with a capped page size.
- `GET /api/v1/jobs/{jobId}` - **200.** Returns status, progress and output metadata. Return `404` when absent; do not expose another user's records.
- `GET /api/v1/jobs/{jobId}/events` - **200.** Streams state/progress events using SSE. Set keep-alive/no-cache headers and support reconnect using event IDs.
- `POST /api/v1/jobs/{jobId}/cancel` - **202 / 409.** Requests cancellation. Make repeat requests safe while cancellation is pending; the worker must terminate the subprocess.
- `POST /api/v1/jobs/{jobId}/retry` - **202.** Retries an eligible failed job after policy/source revalidation; track the new attempt.
- `DELETE /api/v1/jobs/{jobId}` - **204.** Deletes job history only after execution stops. Do not silently delete a completed asset.
- `GET /api/v1/jobs/{jobId}/download` - **200.** Downloads the primary output. Return `404`, `409`, or `410` for absent, not-ready, or expired output.

**Create job request:**

```json
{
  "source": {
    "type": "url",
    "url": "https://source.example/media/123",
    "inspectionId": "8a875a68-3277-4d39-b49b-009c23f19af0"
  },
  "output": {
    "mode": "audio",
    "container": "mp3",
    "quality": "high"
  },
  "rightsConfirmed": true
}
```

For local media, `source.type` is `upload` and includes `uploadId` instead of a URL. The backend maps user-friendly choices to a fixed internal profile. Never accept raw yt-dlp options, FFmpeg flags, filesystem paths, output templates, executable names, arbitrary headers, or shell fragments from the request.

**Create job response:**

```json
{
  "jobId": "b4bfbfed-4dc1-41ce-a06a-7fd672d9875b",
  "status": "queued",
  "createdAt": "2026-10-24T08:15:00Z",
  "statusUrl": "/api/v1/jobs/b4bfbfed-4dc1-41ce-a06a-7fd672d9875b",
  "eventsUrl": "/api/v1/jobs/b4bfbfed-4dc1-41ce-a06a-7fd672d9875b/events"
}
```

### 8.4 Download library and assets

- `GET /api/v1/assets` - **200.** Lists completed media assets; filter by format, date, source category and expiry.
- `GET /api/v1/assets/{assetId}` - **200.** Reads one asset's metadata, including size, duration, container, codec summary, checksum and expiry.
- `GET /api/v1/assets/{assetId}/download` - **200.** Streams the file with safe `Content-Disposition`, MIME type and range support where practical.
- `DELETE /api/v1/assets/{assetId}` - **204.** Deletes file and metadata. Record/reconcile the filesystem result before removing the canonical asset record.
- `POST /api/v1/assets/{assetId}/extend-retention` - **200.** Optional feature to extend expiry within the configured maximum; must not override disk policy.

### 8.5 Settings and maintenance

- `GET /api/v1/settings` - **200.** Reads safe user-configurable settings; omit or redact secrets and internal paths.
- `PATCH /api/v1/settings` - **200.** Updates only an allowlist of settings; validate all bounds server-side.
- `POST /api/v1/maintenance/cleanup` - **202.** Queues a cleanup pass for the local operator; never accept user-provided filesystem paths.
- `GET /api/v1/maintenance/status` - **200.** Reports last run, removed/skipped files and errors without disclosing full server paths.
- `GET /openapi.json` - **200.** Serves FastAPI's OpenAPI schema by default. `/docs` and `/redoc` are optional interactive documentation routes; disable or protect them in LAN-exposed deployments.

Do not implement a generic endpoint such as `POST /run-command`, `POST /ffmpeg`, or `GET /download?path=...`. All operations should use typed, narrow routes and server-owned profiles.

### 8.6 HTTP response and status conventions

| Situation | HTTP status | Application code |
|---|---:|---|
| Created/enqueued asynchronous job | `202 Accepted` | `JOB_QUEUED` |
| Input syntax or schema invalid | `400` or `422` | `VALIDATION_ERROR` |
| Rights/source policy rejects request | `403` or `422` | `SOURCE_NOT_ALLOWED` |
| Resource does not exist | `404` | `NOT_FOUND` |
| Idempotency conflict or invalid state transition | `409` | `CONFLICT` |
| Request too large | `413` | `FILE_TOO_LARGE` |
| Rate/quota limit exceeded | `429` | `QUOTA_EXCEEDED` |
| Dependency unavailable | `503` | `DEPENDENCY_UNAVAILABLE` |
| Expired output | `410 Gone` | `OUTPUT_EXPIRED` |
| Unexpected error | `500` | `INTERNAL_ERROR` |

## 9. Job model and state machine

### 9.1 States

- `pending` - accepted and persisted but not yet sent to queue.
- `queued` - waiting for a worker.
- `inspecting` - obtaining source metadata or validating input.
- `processing` - acquisition or conversion is in progress.
- `finalizing` - output validation, metadata extraction and atomic move.
- `completed` - all required output and metadata records are durable.
- `cancel_requested` - cancellation was accepted; process termination is pending.
- `cancelled` - execution stopped and staging cleanup completed or safely scheduled.
- `failed` - a terminal failure occurred or retries were exhausted.
- `expired` - the job's output/history has reached its configured retention state.

### 9.2 Allowed transitions

```text
pending -> queued -> inspecting -> processing -> finalizing -> completed
   |          |          |             |              |
   +--------> failed <---+-------------+--------------+
              ^
queued / inspecting / processing -> cancel_requested -> cancelled
failed -> queued  (explicit retry only, after revalidation)
completed -> expired (retention policy; asset deletion is separately recorded)
```

Enforce transitions in a single domain service, not ad hoc across routes. Use an optimistic version field or conditional update to prevent an API cancellation and worker completion from overwriting each other. A completed job must not be moved back to processing; retries should increment an attempt counter or create a linked attempt record.

### 9.3 Progress contract

Progress is best-effort because source tools may not provide a trustworthy percentage. Store:

- `phase`: `inspect`, `download`, `merge`, `transcode`, `validate`, `finalize`.
- `percent`: nullable integer from 0 to 100.
- `bytesProcessed`, `totalBytes`: nullable integers.
- `speedBytesPerSecond`, `etaSeconds`: nullable estimates.
- `updatedAt`: UTC timestamp.

Do not show `100%` until the output has passed validation and the completed asset is durable. The UI should handle unknown values without manufacturing progress.

## 10. Database model

### 10.1 Core tables

**`jobs`**

- `id` UUID primary key.
- `job_type` (`remote_acquisition`, `file_conversion`, `metadata_inspection`).
- `status`, `phase`, `progress_percent`, `progress_bytes`, `total_bytes`, `speed_bytes_per_second`, `eta_seconds`.
- `source_type`, `source_host`, `source_url_redacted`, and a protected `source_url_private`/source reference for worker execution. The private value is never returned to the UI or written to logs; if it may contain signed tokens, encrypt it with a key stored outside PostgreSQL.
- `rights_attested_at`, `policy_decision`, `policy_reason_code`.
- `requested_container`, `requested_mode`, `requested_quality`, `requested_subtitles`.
- `attempt_count`, `max_attempts`, `last_error_code`, `last_error_safe_message`.
- `idempotency_key`, `request_fingerprint`.
- `created_at`, `updated_at`, `started_at`, `completed_at`, `expires_at`.
- `version` for conditional state transitions.

**`assets`**

- `id` UUID primary key; `job_id` foreign key.
- `relative_path` (relative to configured media root, never an absolute user path).
- `original_filename_safe`, `container`, `video_codec`, `audio_codec`, `duration_seconds`, `size_bytes`, `sha256`.
- `created_at`, `expires_at`, `deleted_at`, `delete_error_code`.
- optional source metadata fields such as title, channel/creator label, and thumbnail cache key.

**`job_events`**

- `id` bigserial primary key; `job_id` foreign key; `event_type`, `phase`, `progress_percent`, `safe_message`, `created_at`.
- Store structured events, not raw environment values, full signed URLs or unfiltered subprocess output.
- Apply retention limits so event history cannot grow indefinitely.

**`app_settings`**

- `key` primary key; JSON value; `updated_at`.
- Validate setting names and values through Pydantic models; do not allow arbitrary configuration or secrets to be read through the API.

**`idempotency_records`** (or equivalent fields on jobs)

- idempotency key, normalized request hash, resulting job ID, creation and expiry timestamps.

**`users`** (optional when LAN/multi-user access is enabled)

- ID, username/email, password hash or external identity reference, role, disabled flag, timestamps.
- Do not add a real authentication system for local use unless needed, but do not assume localhost-only deployment will always remain local.

### 10.2 Indexes and retention

Index `jobs(status, created_at)`, `jobs(source_host, created_at)`, `assets(expires_at)`, and `job_events(job_id, created_at)`. Use database migrations for every schema change. Use cascading behavior carefully: removing a job must not accidentally orphan a physical file or delete a file that another record references.

### 10.3 Source URL handling

Do not store or log URL user-info credentials. Prefer not to support authenticated URLs in v1. The worker needs a private execution URL for a remote job; keep it in a protected column or source-reference record, encrypt it if it can contain signed tokens, keep the encryption key outside PostgreSQL, and never return it from the API or write it to logs. Redact query parameters likely to contain signed tokens or secrets before logging. Document retention and purge the protected URL when it is no longer needed. Never accept browser cookies or arbitrary authentication headers in the first release.

## 11. Media worker pipeline

### 11.1 Pipeline stages

1. Load job from PostgreSQL and validate current status.
2. Re-check source policy, URL constraints, job limits and permitted output profile.
3. Create a unique staging directory such as `staging/<job-uuid>/<attempt-number>/`.
4. Inspect source metadata with strict timeouts and output-size limits.
5. Select a fixed source and output profile from server configuration.
6. Invoke yt-dlp or FFmpeg with a list of arguments, `shell=False`, a controlled environment and process timeout. The tool should not inherit application secrets.
7. Capture stdout/stderr with byte limits; parse only expected progress lines; sanitize untrusted strings.
8. Monitor cancellation, elapsed time, bytes written, free disk, and worker shutdown signals.
9. On conversion completion, run ffprobe and verify a valid expected container/stream combination, reasonable duration, and a non-empty file.
10. Calculate size and checksum; generate a safe final filename; move the artifact atomically from staging to `downloads/<asset-uuid>/` on the same filesystem.
11. In a short database transaction, create the asset record and set the job to `completed`.
12. Remove remaining partial files and update events.

### 11.2 Output profiles

Expose user-level profiles rather than arbitrary codec switches:

- `video-best-available`: best source-compatible video/audio streams within configured ceilings; merge only when needed.
- `video-1080p`, `video-720p`, `video-480p`, `video-360p`: maximum height presets when supported.
- `audio-m4a`: preserve a compatible audio stream/container where possible to avoid needless transcoding.
- `audio-mp3-high`: extract or transcode to a configured MP3 quality target.
- `convert-uploaded-video-mp4`: convert an uploaded local file using a known FFmpeg profile.
- `convert-uploaded-audio-mp3`: convert an uploaded local file to MP3.

For every profile, define allowed input types, output container, codecs, max duration, max size, expected extension, time limit, and whether transcoding is required. Quality labels are presets, not promises about source quality.

### 11.3 Child-process safety

- Launch subprocesses with an argument list and `shell=False`.
- Keep executable paths fixed in configuration and validate them at startup.
- Do not accept raw CLI flags, arbitrary post-processors, output templates or paths from API requests.
- Use process groups/sessions so cancellation can terminate children and grandchildren.
- Enforce per-job time, memory, process and output-size limits at both app and container levels where possible.
- Capture only limited output in memory; rotate or discard verbose tool logs.
- Treat all titles, filenames, metadata, subtitles and source responses as untrusted data.

### 11.4 Cancellation and shutdown

When cancellation is requested, update `cancel_requested` conditionally, signal the worker, terminate the process group, wait for process exit, and clean the staging directory. If termination fails, escalate to kill after a grace period. On container shutdown, stop claiming new jobs, give the current process a bounded grace period, and leave enough durable state for the next worker to reconcile the job.

### 11.5 Retry policy

- Retry transient DNS/connection/timeouts and dependency hiccups with exponential backoff and jitter; cap attempts, for example at three.
- Do not automatically retry policy rejections, invalid URLs, unsupported source types, unavailable requested formats, file-too-large, quota exceeded, or invalid media.
- Reinspect source metadata on retry; formats and availability can change.
- A user-requested retry must revalidate policy and must not reuse stale signed URLs or stale inspection results blindly.
- Quarantine incomplete output in staging and delete it after a safe cleanup check.

RQ supports background execution and retry patterns, while FastAPI's own `BackgroundTasks` are more appropriate for small in-process work rather than heavy, independently managed media processing. See References [6]-[7].

## 12. Security and abuse prevention

A URL downloader is an SSRF-sensitive application because a user-controlled URL can make the server initiate network requests. Treat URL validation as a security boundary, not just input formatting. OWASP notes that hostname allowlisting alone does not prevent DNS rebinding; resolved IPs and redirects also need enforcement. See Reference [8].

### 12.1 SSRF and URL policy

- Only permit `https` by default; allow `http` only if a specific adapter requires it and policy allows it.
- Reject URL user-info, unsupported schemes, malformed IDNs, local hostnames, localhost, loopback, link-local, private, multicast, reserved and cloud metadata IP ranges.
- Apply a source allowlist/adapter registry. A valid public URL is not automatically an allowed source.
- Revalidate every redirect destination and each resolved IPv4/IPv6 address. Defend against DNS rebinding by ensuring the connection uses the validated destination or by routing downloads through a hardened egress proxy.
- Do not permit URLs to internal admin consoles, Docker host gateways, the Postgres/Redis services, or arbitrary RFC1918 addresses.
- Set connect/read/total timeouts, maximum redirects, response-size limits and a conservative user-agent policy.
- Avoid arbitrary URL fetching in thumbnails. Cache thumbnails only after the same source validation or obtain them through the source adapter.
- Reject IP-literal URLs unless explicitly required by a trusted adapter.

### 12.2 Local browser security

- Bind the published web port to `127.0.0.1` by default.
- Keep API/database/Redis ports unpublished.
- Enforce same-origin API requests and explicit allowed `Origin` values; do not use `Access-Control-Allow-Origin: *` with credentials.
- Use a restrictive Content Security Policy, `X-Content-Type-Options: nosniff`, frame restrictions, and safe `Content-Disposition` for files.
- Validate the `Host` header and prevent DNS-rebinding-style host confusion.
- Apply CSRF protection for state-changing cookie-authenticated actions, or use a local session/token design with appropriate browser protections.
- Do not load remote scripts into the UI. External thumbnails and metadata must be treated as untrusted.

### 12.3 Upload security

- Enforce upload size at Nginx and API layers.
- Stream uploads to staging instead of reading the whole file into RAM.
- Validate extension, media signature and actual stream details with ffprobe; never trust the supplied MIME type.
- Generate the stored filename yourself; ignore path components provided by the client.
- Keep uploads non-executable, use a separate staging location, and do not serve staging files directly.
- Cap duration, dimensions, stream count and output size to reduce resource-exhaustion risk.

### 12.4 Container hardening

- Run API, worker and web as non-root users where possible.
- Drop Linux capabilities; use `no-new-privileges`; avoid privileged mode and host PID/network modes.
- Mount only the paths each service needs. The worker has read/write access to staging and downloads, but must not mount the Docker socket or the host root.
- Use a read-only root filesystem where practical and mount explicit writable temp/cache paths.
- Set CPU, memory, PID, file-size and job-time limits.
- Pin base images and major dependencies; update them intentionally and scan images/dependencies.
- Do not use mutable `latest` tags in the finished deployment. Prefer pinned versions and digests for production-like repeatability.
- Use Compose secrets or a protected local `.env` file for local credentials. Do not commit secrets or include them in log output.
- Consider an egress firewall/proxy on a server that hosts other sensitive services.

### 12.5 Filesystem safety

- Store only relative paths in the database; resolve paths under a configured media root and verify that the result remains within that root.
- Create safe filenames from normalized metadata; remove control characters, path separators, reserved names and excessive length.
- Never accept `path`, `outputDir` or `filenameTemplate` as unrestricted API parameters.
- Use unique asset directories and atomic rename/finalization on the same filesystem.
- Before deleting an asset, verify its resolved path is within the configured media root and is not a directory shared by another asset.

### 12.6 Rights and policy enforcement

- Require user acknowledgement where appropriate, but also enforce a server-side source policy.
- Keep a record of policy decisions and reason codes without storing unnecessary personal data.
- Provide a source disable switch so a source can be disabled immediately if permission, terms or safety requirements change.
- Do not offer circumvention of DRM, access controls, or anti-download protections.
- Review terms and local law before public sharing or commercial use; self-hosting by itself does not grant permission to download content.

## 13. Resource limits and capacity planning

Set initial defaults in configuration and make each limit observable in `/api/v1/system/status`.

| Limit | Initial policy | Tune based on |
|---|---|---|
| Concurrent media jobs | 1 | CPU, disk, RAM, network and typical media sizes |
| Max source duration | Configurable; conservative in v1 | Intended use and storage budget |
| Max input/output file size | Explicit configured ceiling | Free disk and expected source sizes |
| Max upload size | Explicit configured ceiling | Network and storage capacity |
| Max redirects | Small bounded value | Adapter behavior |
| Source inspection timeout | Short bounded timeout | Source latency; do not block API worker indefinitely |
| Media job timeout | Profile-specific hard cap | Media duration and conversion speed |
| Retry count | Up to 3 for transient failures | Source reliability and rate limits |
| Completed-output retention | Example: 7 days by default | Available storage and usage pattern |
| Event retention | Example: 30 days | Debugging need and database size |
| Job history retention | Example: 90 days | Product preference and database size |
| Playlist/batch size | Disabled in v1; later strictly capped | Source policy and capacity |

These values are initial design defaults, not universal sizing advice. Validate disk free space before queueing and during processing. Reserve enough free space for partial downloads and conversion intermediates; a conversion may need input and output files at the same time.

## 14. Storage and lifecycle management

Recommended host layout:

```text
data/
|-- staging/         # Temporary job-specific files; API and worker need write access
|-- downloads/       # Completed assets; API read-only, worker read/write
|-- thumbnails/      # Optional bounded cache
`-- backups/
    |-- database/
    `-- metadata/

PostgreSQL and Redis use Docker named volumes in the Compose example; do not edit
those internal data directories manually.
```

Prefer Docker named volumes for database internals and host bind mounts for `data/staging` and `data/downloads` so files are easy to browse and back up. Mount staging read/write into the API for streaming uploads and into the worker for processing; mount completed downloads read-only into the API and read/write into the worker. Do not edit the PostgreSQL data directory manually.

### 14.1 Atomic finalization

Never treat a file in staging as a completed download. Write to a unique temporary name, validate the container and streams, compute size/checksum, move atomically to the final directory, then commit the asset row and completed state. If database finalization fails after the move, a reconciler should identify unreferenced final files and either register them safely or move them to quarantine.

### 14.2 Retention cleanup

- Delete only assets whose expiry has passed and that are not referenced by active jobs.
- Mark an asset as deletion-pending before filesystem removal; mark it deleted after success.
- Retry deletion failures and surface them in maintenance status.
- Clean partial artifacts older than a defined threshold only when no active worker owns the job.
- Do not remove source input files before a conversion has completed.
- Keep cleanup bounded by batch size to avoid long blocking transactions.

### 14.3 Backup and restore

Back up PostgreSQL with a database-aware dump, not by copying a live data directory. Back up the completed media directory separately; record its path and backup timestamp. Redis can be rebuilt from PostgreSQL and need not be the authoritative part of a full backup.

A backup must include enough metadata to match assets to files and configuration. Keep secrets separately. Test restoration to a clean Compose project regularly and verify that the application can list and download restored assets.

## 15. Observability and operations

### 15.1 Structured logging

Emit JSON logs with `timestamp`, `level`, `service`, `requestId`, `jobId`, `attempt`, `phase`, `event`, `durationMs`, `errorCode`, and a redacted message. Never log full signed URLs, cookies, authorization headers, environment contents, or unfiltered tool output.

### 15.2 Metrics/status indicators

At minimum, report:

- API liveness/readiness and dependency status.
- Number of queued, active, completed, failed and stale jobs.
- Worker heartbeat and last claimed job.
- Job duration by phase and failure code.
- Disk total/free/used and staging bytes.
- PostgreSQL and Redis connection status.
- Tool versions and last successful cleanup.
- Number of outputs approaching expiry and cleanup failures.

A local status page is enough for v1. Prometheus/OpenTelemetry can be added later if the server is already monitored that way.

### 15.3 Health-check rules

- Liveness must not fail merely because Redis or PostgreSQL is temporarily unavailable.
- Readiness checks dependencies with short timeouts and returns unavailable when a required dependency cannot be reached.
- Worker health requires a fresh heartbeat, working queue connection, and validated tool availability.
- Database startup should use container health checks and migrations should run as a controlled release step, not concurrently in every API replica.

### 15.4 Updates

- Review yt-dlp/yt-dlp-ejs/JavaScript-runtime and FFmpeg changes before updating the worker image.
- Pin versions for repeatable builds; rebuild and run regression tests before production update.
- Back up the database before migrations.
- Do not let a running job silently switch media-tool versions halfway through a deployment. Drain workers or allow the active job to finish before replacement.
- Keep a short release note listing dependency changes, data migrations, and rollback steps.

## 16. Example Compose deployment blueprint

This skeleton illustrates topology and is intentionally not a complete runnable release: Dockerfiles, Nginx reverse-proxy configuration, health-check scripts, secrets and application code must be implemented first. Pin image versions and configure credentials in a protected `.env` or Compose secrets before running it.

```yaml
name: local-media-downloader

services:
  web:
    build: ./apps/web
    ports:
      - "127.0.0.1:3000:8080"
    depends_on:
      api:
        condition: service_healthy
    networks: [frontend]
    restart: unless-stopped
    read_only: true
    tmpfs:
      - /var/cache/nginx
      - /var/run
      - /tmp
    security_opt:
      - no-new-privileges:true
    cap_drop: [ALL]

  api:
    build: ./apps/api
    environment:
      APP_ENV: production
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: redis://redis:6379/0
      MEDIA_ROOT: /downloads
      STAGING_DIR: /staging
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./data/staging:/staging
      - ./data/downloads:/downloads:ro
    networks: [frontend, backend]
    healthcheck:
      test: ["CMD", "/usr/local/bin/healthcheck.sh"]
      interval: 10s
      timeout: 3s
      retries: 5
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    cap_drop: [ALL]

  worker:
    build: ./apps/worker
    environment:
      APP_ENV: production
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: redis://redis:6379/0
      MEDIA_ROOT: /downloads
      STAGING_DIR: /staging
      MAX_CONCURRENT_JOBS: "1"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./data/staging:/staging
      - ./data/downloads:/downloads
    networks: [backend, egress]
    restart: unless-stopped
    init: true
    security_opt:
      - no-new-privileges:true
    cap_drop: [ALL]
    # Set mem_limit, cpus and pids_limit after measuring the host.

  redis:
    image: redis:7-alpine # Pin to an approved patch/digest for reproducible deployment.
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis-data:/data
    networks: [backend]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10
    restart: unless-stopped

  postgres:
    image: postgres:17-alpine # Pin to an approved patch/digest for reproducible deployment.
    environment:
      POSTGRES_DB: mediaapp
      POSTGRES_USER: mediaapp
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks: [backend]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mediaapp -d mediaapp"]
      interval: 5s
      timeout: 3s
      retries: 15
    restart: unless-stopped

networks:
  frontend: {}
  backend:
    internal: true
  egress: {}

volumes:
  postgres-data:
  redis-data:
```

**Important Compose notes:**

- The web container should run Nginx as a non-root user listening on port `8080`; the host maps `127.0.0.1:3000` to that unprivileged port. The Nginx config must proxy `/api/` to `http://api:8000` on the shared frontend network. The API image should copy `infra/scripts/healthcheck.sh` to `/usr/local/bin/healthcheck.sh`; the script uses Python standard-library HTTP access to call `/health/ready` with a short timeout.
- The example uses image tags to make the intended services legible. Before actual deployment, pin approved patch versions and preferably immutable digests, then update through a tested change process.
- The worker writes to staging and completed-download directories. The API writes only to staging for uploads and mounts completed downloads read-only. Create host folders and align numeric UID/GID permissions deliberately.
- The API and web share the frontend network. If stricter egress isolation for the API is required, use a dedicated reverse-proxy/network design and host firewall policy, then test it on the target Docker platform.
- `internal: true` on the backend network prevents it from providing ordinary external connectivity. The worker uses the separate `egress` network for approved external source access.
- Set secrets through `.env` only as a local baseline; for higher assurance use Compose secrets and tightly control filesystem permissions. Do not commit `.env`.
- Add migrations as a one-off release step. Do not run migrations concurrently from every application replica.
- Verify that the exact image tags, configuration options, resource limits and health-check tools are supported by the installed Docker Compose version.

## 17. Configuration contract

Store configuration in environment variables, with typed validation on startup. Suggested keys:

The local `.env.example` should include placeholders for `POSTGRES_PASSWORD` and `DATABASE_URL`; never commit the populated `.env`. Point the PostgreSQL DSN at the Compose service `postgres`, and percent-encode URL-reserved password characters.

| Variable | Purpose | Example/default |
|---|---|---|
| `APP_ENV` | Runtime mode | `production` |
| `APP_PORT` | API listen port | `8000` internal only |
| `DATABASE_URL` | PostgreSQL connection | Secret/config value |
| `REDIS_URL` | Redis connection | `redis://redis:6379/0` |
| `POSTGRES_PASSWORD` | Initial PostgreSQL password | High-entropy secret in `.env` or Compose secret |
| `MEDIA_ROOT` | Completed assets root | `/downloads` |
| `STAGING_DIR` | Temporary/upload staging root | `/staging` |
| `MAX_CONCURRENT_JOBS` | Worker concurrency | `1` |
| `MAX_UPLOAD_BYTES` | Upload ceiling | Explicit deployment-specific value |
| `MAX_OUTPUT_BYTES` | Output ceiling | Explicit deployment-specific value |
| `MAX_JOB_DURATION_SECONDS` | Hard job timeout | Profile-specific ceiling |
| `MAX_REDIRECTS` | Redirect policy | Small bounded integer |
| `JOB_RETRY_MAX` | Transient retry ceiling | `3` |
| `OUTPUT_RETENTION_DAYS` | Completed output retention | `7` |
| `EVENT_RETENTION_DAYS` | Job event retention | `30` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `ALLOWED_ORIGINS` | Browser origin allowlist | `http://localhost:3000` |
| `PUBLIC_BASE_URL` | URL used by frontend links | `http://localhost:3000` |
| `ENABLE_LAN_ACCESS` | Explicit LAN-mode switch | `false` |
| `ENABLE_YOUTUBE_DOWNLOAD` | Policy gate for authorized integration | `false` until approved workflow is validated |

Defaults should be set in code. Production config should fail closed when a required secret, database URL, output root, or policy configuration is absent or invalid.

## 18. Testing strategy

### 18.1 Unit tests

- URL normalization, scheme/host checks, IDN and IP validation.
- Source adapter selection and allow/deny policy decisions.
- Output profile mapping and rejection of arbitrary parameters.
- State-machine transitions and race conditions.
- Safe filename generation and path containment.
- Error-code mapping and URL/log redaction.
- Retention date calculations.

### 18.2 API tests

- `202` job creation and idempotency behavior.
- Invalid and unsupported URL behavior.
- Rights/policy rejection behavior.
- Pagination and filtering of history.
- Cancel/retry transitions and duplicate requests.
- Download authorization, expiry and correct headers.
- Upload size enforcement and malformed media rejection.
- Dependency degradation and readiness behavior.

### 18.3 Worker integration tests

Use small, local, redistributable test fixtures and a local HTTP test server. Do not make the test suite depend on a live YouTube URL or on another website remaining stable.

Test successful download/import flow, conversion to each promised output, ffprobe validation, transient failure retry, permanent failure, timeout, output-size limit, disk-space low state, worker termination mid-job, cleanup of partial files, and restart/reconciliation after a crash.

### 18.4 Security tests

- URLs pointing at localhost/private networks, IPv4/IPv6 loopback, link-local ranges and common metadata addresses are rejected.
- Redirects to private/internal IPs are blocked.
- DNS changes between validation and fetch cannot bypass the egress policy.
- File names containing `../`, separators, control characters or reserved names cannot escape storage root.
- Subprocess arguments cannot be injected through titles, URLs or output options.
- Browser-origin and CSRF protections work.
- API, Redis and PostgreSQL do not have published host ports in the default Compose configuration.
- Logs and API errors do not disclose secrets or full signed URLs.

### 18.5 End-to-end acceptance tests

- Bring the project up from a clean checkout using the documented steps.
- Submit one permitted test source and one local upload.
- Confirm queue state and progress appear in the UI.
- Confirm completed output plays and metadata matches ffprobe.
- Restart all containers and confirm durable job history and finished assets remain available.
- Cancel a long-running test and verify the child process stops and partial output is removed.
- Fill staging to the configured test limit and confirm the application returns a safe disk/limit error.
- Restore a backup into a clean environment and verify assets remain downloadable.

## 19. Delivery plan

### Phase 0 - Repository and infrastructure

- Create monorepo folders and pinned dependency manifests.
- Add Dockerfiles, Compose networks, health checks, non-root users, and local `.env.example`.
- Confirm web/API connectivity and private database/Redis networking.
- Add CI checks for formatting, linting, static typing, unit tests and image builds.

**Exit criterion:** Clean checkout starts all required containers; only the web port is published.

### Phase 1 - API, database and queue

- Define SQLAlchemy models and Alembic migrations.
- Implement health/readiness and system-info endpoints.
- Implement job creation, status, history, state transitions, idempotency and RQ enqueueing.
- Add worker heartbeat and reconciliation for queued/abandoned jobs.

**Exit criterion:** A synthetic job can be created, queued, executed by a dummy worker and displayed in the UI.

### Phase 2 - Media conversion from local files

- Implement uploads to staging, ffprobe inspection, fixed FFmpeg profiles and finalization.
- Add size/time/disk limits, cancellation, safe filenames and cleanup.
- Implement asset library and browser download delivery.

**Exit criterion:** Supported test files convert reliably and survive restarts; invalid files fail safely.

### Phase 3 - Authorized remote source adapter

- Implement adapter registry, URL policy, redirect validation and source inspection.
- Integrate yt-dlp and its required runtime components in the isolated worker image for sources and workflows where downloading is authorized.
- Record tool versions and add adapter regression tests.

**Exit criterion:** Only policy-approved sources can reach the worker acquisition path, with documented test cases and bounded failure behavior.

### Phase 4 - Hardening and operations

- Add all SSRF, path traversal, cancellation and crash-recovery tests.
- Add retention, backup/restore scripts, storage status and maintenance logs.
- Pin images by digest and document update/rollback steps.
- Run a restore rehearsal and a worker crash/restart exercise.

**Exit criterion:** Operational runbook has been followed successfully by someone other than the original implementer.

### Phase 5 - Optional enhancements

- Authenticated LAN access and roles.
- Additional source adapters that meet permission requirements.
- Explicit playlist/batch mode with item/size/time caps.
- Subtitle import/selection, thumbnail library, search, checksum-based duplicate detection, notifications and per-user quotas.
- SQLite compact profile only if there is a strong need for fewer services; treat migration and backup as first-class tasks.

## 20. Operations runbook

### Start / update

```bash
mkdir -p data/staging data/downloads data/backups
docker compose config
docker compose up -d --build
docker compose ps
docker compose logs -f api worker
```

Before an update: read release notes, back up PostgreSQL and media metadata, build the new images, run tests, apply migrations once, and deploy. If jobs are active, stop queue consumption or allow them to finish before replacing workers.

### Stop

```bash
docker compose stop
```

To remove containers while preserving named volumes:

```bash
docker compose down
```

**Do not use `docker compose down -v` as routine maintenance**; it removes named volumes and can delete persisted data.

### Diagnose

```bash
docker compose ps
docker compose logs --tail=200 api worker redis postgres
docker compose exec postgres pg_isready -U mediaapp -d mediaapp
docker compose exec redis redis-cli ping
docker system df
```

The commands above are operational examples; adapt database credentials and container names to the approved deployment config.

### Incident response checklist

1. Stop accepting new jobs if disk or dependency health is degraded.
2. Preserve logs and job IDs; do not publish raw signed URLs or secrets.
3. Check worker heartbeat, queue depth, storage free space, PostgreSQL and Redis health.
4. Determine whether the failure is policy-related, a source change, transient network, media corruption, resource exhaustion or application defect.
5. Retry only when the error category is retryable and the source policy still permits the job.
6. If an update caused failures, roll back the worker image/version and restore the previous configuration. Do not roll back database schema blindly; follow migration rollback notes.
7. Reconcile orphaned staging/final files after the system is stable.

## 21. Definition of done for v1

The first production-like release is complete when all of the following are true:

- The stack is started/stopped by Compose and stores data outside disposable container layers.
- Only the local web port is published by default.
- API endpoints are documented and versioned with request/response models and predictable errors.
- Job state is durable in PostgreSQL; queue failures or worker restarts do not silently lose completed history.
- Media work is executed in an isolated worker process with bounded time, space, retries and concurrency.
- Supported video/audio profiles pass fixture tests; outputs are validated before being marked complete.
- Cancellation stops the underlying child process; partial files are cleaned or safely quarantined.
- URL validation and SSRF protections are tested against private IPs, redirects and DNS-rebinding scenarios.
- File paths cannot escape the configured storage root; client input cannot become shell arguments.
- Source policy is checked at inspection, job creation and execution.
- Logs are structured and redacted; failure messages are safe and actionable.
- Retention, backup, restore, update and rollback procedures are documented and tested.
- The UI clearly represents unknown progress and unavailable formats without inventing data.

## 22. Decisions to keep explicit

The implementation should record these decisions in an ADR (Architecture Decision Record) if they change:

1. **Single-user localhost vs LAN/multi-user:** localhost-only is the default; LAN mode requires authentication, TLS/reverse proxy, explicit firewall controls and per-user authorization.
2. **PostgreSQL vs SQLite:** PostgreSQL is the recommended baseline for this robust blueprint. SQLite is an optional compact mode, not a drop-in high-concurrency replacement.
3. **Source permissions:** YouTube support stays disabled unless the exact workflow is authorized. Remote URL support is adapter-based and allowlisted.
4. **Worker concurrency:** start at one; increase only after load tests and resource monitoring.
5. **Retention and quotas:** define real capacity values on the target host before exposing the UI to a second user.
6. **Updates:** yt-dlp, yt-dlp-ejs, JavaScript runtime, FFmpeg, Python dependencies, Node/npm dependencies and container images are all part of the supply chain and need controlled updates.

## References

These official or primary references were checked while preparing this blueprint. Re-check them at implementation time because source behavior and software releases evolve.

1. YouTube Terms of Service, especially “Permissions and Restrictions”: <https://www.youtube.com/t/terms>
2. YouTube Help - download your own uploaded videos (creator workflow): <https://support.google.com/youtube/answer/56100>
3. yt-dlp README, dependencies and supported sites: <https://github.com/yt-dlp/yt-dlp/blob/master/README.md>
4. yt-dlp EJS guidance for JavaScript runtime support: <https://github.com/yt-dlp/yt-dlp/wiki/EJS>
5. Docker Docs - Networking in Compose: <https://docs.docker.com/compose/how-tos/networking/>
6. FastAPI docs - Background Tasks and limits for heavier work: <https://fastapi.tiangolo.com/tutorial/background-tasks/>
7. RQ docs - Python job queue: <https://python-rq.org/docs/>
8. OWASP Cheat Sheet - Server-Side Request Forgery Prevention: <https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html>
9. FFmpeg documentation: <https://ffmpeg.org/documentation.html>
10. Docker Compose docs - service definitions and networking: <https://docs.docker.com/reference/compose-file/services/>

---

**End of blueprint**
