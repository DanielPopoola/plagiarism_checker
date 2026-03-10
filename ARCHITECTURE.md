# Architecture

## Overview

The system is structured as a monolithic FastAPI application with an asynchronous analysis pipeline handled by Celery. All plagiarism computation happens outside the request-response cycle.

```
Browser / API client
        │
        ▼
   FastAPI (uvicorn)
        │
   ┌────┴────────────────────────────┐
   │  Routers (HTTP only)            │
   │  Services (business logic)      │
   │  Repositories (DB queries)      │
   └────┬────────────────────────────┘
        │                    │
        ▼                    ▼
   SQLite / PostgreSQL     Redis
                             │
                        Celery Worker
                             │
                     Plagiarism Pipeline
                     (similarity + classifier)
```

---

## Layer Responsibilities

### Routers (`app/routers/`)

HTTP concerns only. Each route:
1. Authenticates and authorises the user
2. Parses the request
3. Delegates to a service
4. Returns the response or redirect

No queries, no business logic.

### Services (`app/services/`)

Business logic and orchestration. Services call repositories for data, enforce rules, raise `HTTPException` for violations, and trigger Celery tasks.

| Service | Responsibility |
|---|---|
| `auth.py` | Login verification, token creation, registration |
| `admin.py` | User/course/department/enrolment management |
| `dashboard.py` | Exam creation, exam detail assembly, pair review |
| `student.py` | Course browsing, enrolment, submission form data |
| `submission.py` | File validation, saving, encryption, text extraction, job dispatch |
| `similarity.py` | Pairwise document comparison (pure computation) |
| `classifier.py` | Plagiarism type classification (pure computation) |
| `crypto.py` | Fernet encrypt/decrypt for files and text |
| `audit.py` | Audit log writes |

### Repositories (`app/repositories/`)

All SQLAlchemy queries live here. Each function takes a `Session` and returns a model or raises `HTTPException(404)`. No business logic.

| Repository | Models |
|---|---|
| `user.py` | `User` |
| `course.py` | `Course` |
| `exam.py` | `Exam` |
| `submission.py` | `Submission`, `PlagiarismJob` |
| `department.py` | `Department` |
| `enrollment.py` | `Enrollment` |
| `pair.py` | `SimilarityPair` |

---

## Data Model

```
Department
  └── Course (many)
        ├── Enrollment (many) ──► User (student)
        └── Exam (many)
              ├── Submission (many) ──► User (student)
              │     └── SimilarityPair (many, a_id + b_id)
              │           ├── MatchedFragment (many)
              │           ├── PlagiarismTypeResult (one)
              │           └── ReviewDecision (one)
              └── PlagiarismJob (one)
```

Key constraints:
- `(exam_id, student_id)` is unique on `Submission` — one submission per student per exam, resubmission updates in place
- `(student_id, course_id)` is unique on `Enrollment`
- `exam_id` is unique on `PlagiarismJob` — one job per exam, re-runs reset the same record

---

## Authentication

JWT tokens, signed with `HS256`. Issued on login, valid for 8 hours. Accepted as:
- `Authorization: Bearer <token>` header (API clients)
- `session` cookie (browser sessions)

Passwords hashed with Argon2 via `passlib`.

Role-based access is enforced at the router level via `require_role()` dependency guards (`admin_only`, `lecturer_or_admin`, `student_only`).

---

## File Handling and Encryption

On upload:
1. File is streamed to disk under `uploads/{exam_id}/{uuid}.{ext}` with a size check enforced during streaming (no full read into memory)
2. The file on disk is encrypted with Fernet symmetric encryption
3. The file is immediately decrypted back into memory for text extraction
4. Extracted text is normalised and stored in the database, itself encrypted via `EncryptedText` (a SQLAlchemy `TypeDecorator` that encrypts on write and decrypts on read)

This means both the raw file and the extracted text are encrypted at rest.

---

## Plagiarism Analysis Pipeline

Triggered automatically on every submission (and resubmission). Runs asynchronously via Celery.

```
Submission saved
      │
      ▼
sub_repo.upsert_job()     — create or reset PlagiarismJob for this exam
      │
      ▼
run_plagiarism_analysis.delay(exam_id)   — dispatch Celery task
      │
      ▼ (worker process)
Load all submissions for exam
      │
      ▼
bulk_compare(texts)       — similarity detection
      │
      ▼
classify(fragments, ...)  — plagiarism type per pair
      │
      ▼
Write SimilarityPair + MatchedFragment + PlagiarismTypeResult
      │
      ▼
Write originality_score back to each Submission
      │
      ▼
PlagiarismJob.status = completed
```

Every re-run is idempotent: existing `SimilarityPair` records for the exam are deleted before new ones are written.

---

## Timezone Handling

All datetimes are stored as naive UTC in the database. Conversion to Africa/Lagos (UTC+1) is display-only, applied via a Jinja2 filter:

```python
# app/templates.py
templates.env.filters["lagos"] = _to_lagos
```

Used in templates as:
```
{{ exam.opens_at | lagos }}
{{ exam.opens_at | lagos("%d %b %Y") }}
```

Exam creation via the HTML form converts Lagos local time input → UTC before saving. The API (`/exams/`) accepts UTC datetimes directly from callers.

---

## Celery Configuration

No Beat scheduler. All tasks are event-driven (triggered by submission upload). The worker configuration:

```python
celery_app.conf.update(
    broker_url=settings.redis_url,
    result_backend=settings.redis_url,
    task_serializer="json",
    enable_utc=True,
)
```

Tasks use `bind=True, max_retries=3, default_retry_delay=60` — failed analysis jobs retry up to 3 times with a 60-second delay before marking as `failed`.