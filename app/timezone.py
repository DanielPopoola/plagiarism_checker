from datetime import UTC, datetime
from zoneinfo import ZoneInfo

WAT = ZoneInfo("Africa/Lagos")


def utc_naive(dt: datetime) -> datetime:
    """Normalize datetime to naive UTC for safe DB/time-window comparisons."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(UTC).replace(tzinfo=None)


def wat_input_to_utc_naive(value: str) -> datetime:
    """Convert frontend WAT datetime-local input to naive UTC."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=WAT)
    else:
        parsed = parsed.astimezone(WAT)
    return parsed.astimezone(UTC).replace(tzinfo=None)


def to_wat(dt: datetime) -> datetime:
    """Convert stored UTC datetime (aware/naive) to WAT-aware datetime."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(WAT)
