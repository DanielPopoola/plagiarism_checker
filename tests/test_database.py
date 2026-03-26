from app import database


class _Cursor:
    def __init__(self):
        self.calls = []
        self.closed = False

    def execute(self, sql):
        self.calls.append(sql)

    def close(self):
        self.closed = True


class _Conn:
    def __init__(self):
        self._cursor = _Cursor()

    def cursor(self):
        return self._cursor


def test_force_utc_session_timezone_for_postgres(monkeypatch):
    monkeypatch.setattr(database.settings, "database_url", "postgresql+psycopg://u:p@localhost/db")
    conn = _Conn()

    database._force_utc_session_timezone(conn, None)

    assert conn._cursor.calls == ["SET TIME ZONE 'UTC'"]
    assert conn._cursor.closed is True


def test_force_utc_session_timezone_skips_sqlite(monkeypatch):
    monkeypatch.setattr(database.settings, "database_url", "sqlite:///./app.db")
    conn = _Conn()

    database._force_utc_session_timezone(conn, None)

    assert conn._cursor.calls == []
