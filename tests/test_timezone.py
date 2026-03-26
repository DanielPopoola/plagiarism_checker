from datetime import datetime

import pytest
from fastapi import HTTPException

from app.services import dashboard as dash_svc
from app.timezone import to_wat, utc_naive, wat_input_to_utc_naive


def test_wat_input_to_utc_naive_converts_datetime_local_value():
    converted = wat_input_to_utc_naive("2026-03-26T10:25")
    assert converted == datetime(2026, 3, 26, 9, 25)


def test_to_wat_converts_stored_utc_naive_for_frontend_display():
    wat = to_wat(datetime(2026, 3, 26, 9, 30))
    assert wat.tzinfo is not None
    assert wat.hour == 10
    assert wat.minute == 30


def test_utc_naive_normalizes_aware_datetimes():
    wat_dt = datetime(2026, 3, 26, 10, 30, tzinfo=to_wat(datetime(2026, 3, 26, 9, 30)).tzinfo)
    assert utc_naive(wat_dt) == datetime(2026, 3, 26, 9, 30)


def test_dashboard_create_exam_stores_wat_window_as_utc(db, lecturer, course):
    exam = dash_svc.create_exam(
        db,
        lecturer,
        course_id=course.id,
        title="WAT window exam",
        description="",
        opens_at="2026-03-26T10:25",
        closes_at="2026-03-26T10:30",
        allowed_formats="pdf,docx,txt",
        max_file_mb=10,
        similarity_threshold=0.4,
    )

    assert exam.opens_at == datetime(2026, 3, 26, 9, 25)
    assert exam.closes_at == datetime(2026, 3, 26, 9, 30)


def test_dashboard_create_exam_rejects_invalid_time_values(db, lecturer, course):
    with pytest.raises(HTTPException) as exc:
        dash_svc.create_exam(
            db,
            lecturer,
            course_id=course.id,
            title="Bad exam",
            description="",
            opens_at="bad-time",
            closes_at="2026-03-26T10:30",
            allowed_formats="pdf,docx,txt",
            max_file_mb=10,
            similarity_threshold=0.4,
        )
    assert "Invalid date format" in str(exc.value)
