# Plagiarism Detection System

A written exam submission and automated plagiarism analysis platform for academic institutions. Lecturers create exams, students upload written work, and the system automatically detects and classifies similarity between submissions.

---

## What This Is

This is not a full online examination platform. It is a **submission intake and plagiarism analysis system** for long-form written assessments. It does not deliver timed questions, render multiple-choice items, or provide proctoring. What it does:

- Accepts student file uploads (PDF, DOCX, TXT) against a defined exam window
- Extracts and normalises text from submitted files
- Runs pairwise similarity analysis across all submissions for an exam
- Classifies the type of plagiarism pattern detected
- Presents ranked results to lecturers for review and decision

---

## Roles

| Role | Capabilities |
|---|---|
| **Student** | Browse courses, enrol, upload submissions within the exam window |
| **Lecturer** | Create exams, view similarity reports, review and classify flagged pairs |
| **Admin** | Manage users, departments, courses, enrolments |

---

## Quick Start

### Prerequisites

- Python 3.12
- Redis (for Celery broker and result backend)

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Set SECRET_KEY, FERNET_KEY, REDIS_URL, DATABASE_URL in .env

# Generate a Fernet key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Docker Compose (recommended)

```bash
cp .env.example .env
# Set SECRET_KEY and FERNET_KEY before first start

docker compose up --build
```

This starts FastAPI (`web`), Celery (`worker`), Redis, and PostgreSQL. On startup, the web container runs `scripts/seed_departments_courses.py` once to ensure an admin, departments, and courses are present (idempotent).

### Running without Docker

Three processes must run concurrently:

```bash
# Terminal 1 — web server
uvicorn app.main:app --reload

# Terminal 2 — Celery worker (plagiarism analysis)
celery -A app.tasks.analysis.celery_app worker --loglevel=info

# Terminal 3 — Redis (if not running as a service)
redis-server
```

### Seed data

```bash
python scripts/seed_departments_courses.py
```

Optional environment variables:
- `SEED_ADMIN_EMAIL` (default: `admin@example.com`)
- `SEED_ADMIN_PASSWORD` (default: `admin123`)
- `SEED_ADMIN_NAME` (default: `System Admin`)

---

## Tests

```bash
pytest
```

Tests use an in-memory SQLite database. Celery tasks, file I/O, encryption, and text extraction are mocked at the boundary. See `tests/conftest.py` for fixture design.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./plagiarism.db` | SQLAlchemy connection string |
| `SECRET_KEY` | `change-me-in-production` | JWT signing key |
| `FERNET_KEY` | *(required)* | Fernet symmetric key for file/text encryption |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker and backend |
| `UPLOAD_DIR` | `uploads` | Directory for uploaded files |
| `MAX_FILE_SIZE_MB` | `10` | Per-file upload limit |
| `FILTER_STOPWORDS` | `true` | Strip stopwords before similarity analysis |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | JWT lifetime (8 hours) |

---

## Stack

- **FastAPI** — web framework and API
- **SQLAlchemy** — ORM, SQLite (dev) / PostgreSQL (prod)
- **Jinja2** — server-rendered HTML templates
- **Celery + Redis** — async plagiarism analysis pipeline
- **scikit-learn** — TF-IDF vectorisation and cosine similarity
- **Fernet (cryptography)** — symmetric encryption for uploaded files and extracted text
- **passlib (argon2)** — password hashing
- **python-jose** — JWT tokens