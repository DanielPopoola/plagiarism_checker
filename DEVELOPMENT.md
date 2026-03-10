# Development Guide

## Project Structure

```
app/
├── main.py                  # App entry point, router registration
├── auth.py                  # JWT decode, password hashing, role guards
├── config.py                # Pydantic settings (env vars)
├── database.py              # SQLAlchemy engine, session, Base
├── models.py                # All ORM models
├── schemas.py               # Pydantic request/response models
├── templates.py             # Jinja2 Templates instance + lagos filter
├── encrypted_type.py        # SQLAlchemy EncryptedText column type
│
├── routers/                 # HTTP layer — auth, parse, call service, respond
├── services/                # Business logic — rules, orchestration
├── repositories/            # DB queries — SQLAlchemy only
└── tasks/
    └── analysis.py          # Celery task for plagiarism pipeline

templates/                   # Jinja2 HTML templates
tests/
├── conftest.py              # Fixtures, test DB, helpers
├── test_api.py              # HTTP integration tests (TestClient)
├── test_auth.py             # Auth unit + API tests
├── test_repositories.py     # Repository-layer unit tests
├── test_similarity.py       # Similarity service unit tests
├── test_classifier.py       # Classifier service unit tests
└── test_extraction.py       # Text extraction unit tests
```

---

## Adding a New Route

Follow the established pattern: router → service → repository.

**1. Repository** — write the query in `app/repositories/`:
```python
def get_thing(db: Session, thing_id: int) -> Thing:
    t = db.get(Thing, thing_id)
    if not t:
        raise HTTPException(status_code=404)
    return t
```

**2. Service** — write business logic in `app/services/`:
```python
def do_thing(db: Session, user: User, thing_id: int) -> Thing:
    thing = thing_repo.get_thing(db, thing_id)
    if thing.owner_id != user.id:
        raise HTTPException(status_code=403)
    return thing
```

**3. Router** — wire HTTP in `app/routers/`:
```python
@router.get("/things/{thing_id}")
def get_thing(thing_id: int, db: ..., user: ...):
    return thing_svc.do_thing(db, user, thing_id)
```

---

## Plagiarism Detection — How It Works

### Text Preparation

Before any comparison, submitted text is normalised:
- Unicode → ASCII (accents stripped)
- Lowercased
- Punctuation removed
- Whitespace collapsed
- Stopwords filtered (configurable via `FILTER_STOPWORDS`)

This happens at upload time in `services/extraction.py`. The normalised text is what gets stored and compared — not the raw file content.

### Similarity Detection (`services/similarity.py`)

Two independent similarity signals are computed for every pair of documents:

**Cosine similarity via TF-IDF**

Each document is represented as a vector of term weights (TF-IDF). The cosine of the angle between two vectors measures how similar their vocabulary distributions are, regardless of document length. Score of 1.0 = identical vocabulary distribution. Score of 0.0 = no shared terms.

```python
vectorizer = TfidfVectorizer()
matrix = vectorizer.fit_transform([text_a, text_b])
score = cosine_similarity(matrix[0], matrix[1])[0, 0]
```

This catches near-copies and paraphrasing where word choice is similar even if sentence structure differs.

**Jaccard similarity via k-shingles**

A shingle is a contiguous sequence of k tokens (default k=6). The Jaccard score is the ratio of shared shingles to total unique shingles across both documents:

```
Jaccard = |shingles_a ∩ shingles_b| / |shingles_a ∪ shingles_b|
```

This catches verbatim copying more directly than cosine — a copied phrase produces matching shingles exactly.

**Combined score**

The final similarity used for filtering and ranking is `max(cosine, jaccard)`. The originality score stored on each submission is `1.0 - max(cosine, jaccard)` across all pairs that submission appears in.

### Fragment Extraction

After scoring, matched text segments are located:

1. Build a lookup of all k-shingles in document B with their start positions
2. For each shingle in document A, check if it exists in B
3. When a match is found, extend it token by token until the texts diverge
4. Discard fragments shorter than `min_fragment_tokens` (default 8)
5. Merge overlapping fragments into single contiguous blocks

Fragments carry `(start_a, end_a, start_b, end_b)` token positions, enabling side-by-side highlighting in the UI.

---

## Scale Behaviour: The 500-Submission Threshold

Pairwise comparison is O(n²) in the number of submissions. For an exam with n submissions, there are `n(n-1)/2` pairs. At n=300 that is 44,850 pairs — manageable. At n=500 it is 124,750 pairs, and beyond that the full pairwise approach becomes slow.

The system switches strategy at `MINHASH_THRESHOLD = 500`.

### Below 500 submissions — Full pairwise

Every possible pair is compared. All submissions are vectorised together in a single `TfidfVectorizer.fit_transform()` call, producing a matrix. `cosine_similarity(matrix)` then computes all pairwise scores in one vectorised operation. Fragment extraction runs only on pairs that exceed `min_score`.

### At or above 500 submissions — MinHash LSH candidate filtering

Rather than comparing every pair, the system first identifies **candidate pairs** — those likely to be similar — using MinHash Locality Sensitive Hashing. Only candidates get full TF-IDF + fragment extraction.

**How MinHash works here:**

Each document is represented as a set of 6-shingles. A MinHash signature approximates the Jaccard similarity between two sets without computing it directly. The signature is a vector of `num_perm=128` hash values, where each value is the minimum hash of the document's shingles under a different hash function.

```python
# 128 independent hash functions: h(x) = (a*x + b) mod p
_a = rng.integers(1, 2**31, size=128)
_b = rng.integers(0, 2**31, size=128)

def minhash(text):
    shingles = all_6_shingles(text)
    hashes = [hash(s) & 0xFFFFFFFF for s in shingles]  # uint32
    return [(a * h + b) % p for h, a, b in zip(hashes, _a, _b)].min(per_function)
```

**LSH banding:**

The 128-element signature is split into `bands=16` bands of 8 values each. Two documents that share an identical band are placed in the same bucket — they become a candidate pair.

The probability that two documents with Jaccard similarity J share at least one band is:

```
P(candidate) = 1 - (1 - J^rows)^bands
             = 1 - (1 - J^8)^16
```

At J=0.5 this gives ~83% recall. At J=0.8 it gives ~99.9% recall. False negatives (similar pairs missed) are rare at meaningful similarity levels. False positives (dissimilar pairs flagged as candidates) are eliminated when the full TF-IDF comparison runs and finds a low score.

The numpy vectorised implementation computes all 128 hash values per document in a single matrix multiplication, making signature generation ~10x faster than a per-shingle loop.

---

## Plagiarism Classification (`services/classifier.py`)

Each flagged pair is classified into one of four types based on features extracted from the fragments and similarity scores.

### Features computed per pair

| Feature | Description |
|---|---|
| `longest` | Token length of the longest single matched fragment |
| `overlap_ratio` | Total matched tokens / average document length |
| `count` | Number of distinct matched fragments |
| `dispersion` | How evenly spread fragments are across the document (0=clustered, 1=even) |
| `order_preserved` | Whether fragments appear in the same relative order in both documents |

### Scoring functions

Each type has a raw scoring function that returns 0–1:

**Verbatim** — large contiguous block, few fragments
```
score = longest/80 * 0.7 + overlap_ratio * 0.2 + (1 - count/5) * 0.1
```

**Near-copy** — high cosine but no single dominant fragment (paraphrasing)
```
score = cosine * 0.5 + overlap_ratio * 0.3 + (1 - longest/40) * 0.2
```

**Patchwork** — many small fragments spread across both documents
```
score = min(count/10, 1) * 0.4 + dispersion * 0.4 + (1 - longest/30) * 0.2
```

**Structural** — order preserved, low token overlap (same structure, different words)
```
score = order_preserved * 0.5 + cosine * 0.3 + (1 - overlap_ratio*2) * 0.2
```

The four raw scores are normalised to sum to 1.0. The predicted type is the argmax. All four scores and the predicted type are stored in `PlagiarismTypeResult` for lecturer review.

When no fragments exist but cosine similarity is moderate, the structural branch activates directly — similarity without any matched segments implies structural or stylistic copying rather than textual copying.

---

## Testing Patterns

### Database isolation

Each test gets a function-scoped session bound to a connection-level transaction. The transaction is rolled back after the test, leaving the in-memory DB clean. The `_tables` session-scoped fixture creates the schema once.

```python
@pytest.fixture
def db():
    conn = _engine.connect()
    tx = conn.begin()
    session = _Session(bind=conn)
    yield session
    session.close()
    tx.rollback()
    conn.close()
```

**Important:** any `db.rollback()` called inside repo code during a test rolls back the outer transaction. Use `db.begin_nested()` (savepoint) in repo code that intentionally catches `IntegrityError` and falls back to a query — see `repositories/department.py`.

### Mocking the submission pipeline

The submission pipeline touches Celery, disk, encryption, and text extraction. Tests mock all four boundaries:

```python
patch("app.tasks.analysis.run_plagiarism_analysis", mock_task)
patch("app.services.submission._save_file", return_value="uploads/1/essay.txt")
patch("app.services.submission.encrypt_file")
patch("app.services.submission.decrypt_file", return_value=b"raw bytes")
patch("app.services.submission.extract_text", return_value="extracted text")
```

This lets submission tests exercise the full HTTP → service → repository path without Redis, disk, or NLTK.

### Enrolled student fixture

Tests that exercise the student exam listing path need an enrolled student. Use the `enrolled_student` fixture rather than `student` directly — it creates the `Enrollment` record against the `course` fixture.