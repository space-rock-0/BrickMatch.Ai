"""SQLite feedback event history and current user-scoped ratings."""
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path


class FeedbackStore:
    def __init__(self, path):
        self.path = str(path)
        if not self.is_postgres:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            schema = """
                CREATE TABLE IF NOT EXISTS feedback_events (
                    event_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                    set_id TEXT NOT NULL, action TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS current_feedback (
                    user_id TEXT NOT NULL, set_id TEXT NOT NULL,
                    action TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(user_id, set_id));
                CREATE INDEX IF NOT EXISTS feedback_user_time
                    ON feedback_events(user_id, created_at);
            """
            if self.is_postgres:
                for statement in schema.split(";"):
                    if statement.strip():
                        db.execute(statement)
            else:
                db.executescript(schema)
            self.exec(db, """CREATE TABLE IF NOT EXISTS app_users (
                user_id TEXT PRIMARY KEY, password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL)""")

    @property
    def is_postgres(self):
        return self.path.startswith(("postgres://", "postgresql://"))

    def connect(self):
        if self.is_postgres:
            import psycopg
            from psycopg.rows import dict_row
            return psycopg.connect(self.path, row_factory=dict_row)
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def exec(self, db, query, params=()):
        return db.execute(query.replace("?", "%s") if self.is_postgres else query, params)

    def record(self, user_id, set_id, action):
        if not isinstance(user_id, str) or not user_id.strip() or len(user_id) > 80:
            raise ValueError("Invalid user ID")
        if not isinstance(set_id, str) or not set_id.strip() or len(set_id) > 80:
            raise ValueError("Invalid set ID")
        if action not in {"like", "dislike", "skip", "undo"}:
            raise ValueError("Invalid feedback action")
        event = {"event_id": str(uuid.uuid4()), "user_id": user_id, "set_id": set_id,
                 "action": action, "created_at": datetime.now(UTC).isoformat()}
        with self.connect() as db:
            if self.is_postgres:
                self.exec(db, "INSERT INTO feedback_events VALUES (?,?,?,?,?)", tuple(event.values()))
            else:
                db.execute("INSERT INTO feedback_events VALUES (:event_id,:user_id,:set_id,:action,:created_at)", event)
            if action == "undo":
                self.exec(db, "DELETE FROM current_feedback WHERE user_id=? AND set_id=?", (user_id, set_id))
            else:
                self.exec(db, """INSERT INTO current_feedback VALUES (?,?,?,?)
                    ON CONFLICT(user_id,set_id) DO UPDATE SET action=excluded.action,
                    updated_at=excluded.updated_at""", (user_id, set_id, action, event["created_at"]))
        return event

    def current(self, user_id):
        with self.connect() as db:
            return [dict(row) for row in self.exec(db,
                "SELECT * FROM current_feedback WHERE user_id=? ORDER BY set_id", (user_id,))]

    def history(self, user_id):
        with self.connect() as db:
            return [dict(row) for row in self.exec(db,
                "SELECT * FROM feedback_events WHERE user_id=? ORDER BY created_at,event_id", (user_id,))]

    def users(self):
        with self.connect() as db:
            return [dict(row) for row in self.exec(db,
                """SELECT user_id, COUNT(*) AS ratings FROM current_feedback
                   GROUP BY user_id ORDER BY user_id""")]

    def create_user(self, user_id, password_hash, created_at):
        with self.connect() as db:
            result = self.exec(db, "INSERT INTO app_users VALUES (?,?,?) ON CONFLICT(user_id) DO NOTHING",
                               (user_id, password_hash, created_at))
            return result.rowcount == 1

    def get_user(self, user_id):
        with self.connect() as db:
            row = self.exec(db, "SELECT user_id, password_hash FROM app_users WHERE user_id=?",
                            (user_id,)).fetchone()
            return dict(row) if row else None
