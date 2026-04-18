from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

try:
    import libsql as libsql_driver

    HAS_LIBSQL = True
except ImportError:  # pragma: no cover - local fallback path
    import sqlite3 as libsql_driver

    HAS_LIBSQL = False

from app.config import settings


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS exams (
        id TEXT PRIMARY KEY,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        version INTEGER NOT NULL,
        content_hash TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS subjects (
        id TEXT PRIMARY KEY,
        exam_id TEXT NOT NULL,
        code TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        display_order INTEGER NOT NULL,
        version INTEGER NOT NULL,
        content_hash TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (exam_id) REFERENCES exams(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS topics (
        id TEXT PRIMARY KEY,
        exam_id TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        code TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        parent_topic_id TEXT,
        display_order INTEGER NOT NULL DEFAULT 0,
        learning_objectives_json TEXT NOT NULL,
        difficulty TEXT NOT NULL,
        estimated_minutes INTEGER NOT NULL,
        knowledge_json TEXT NOT NULL DEFAULT '{}',
        version INTEGER NOT NULL,
        content_hash TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        is_deleted INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (exam_id) REFERENCES exams(id),
        FOREIGN KEY (subject_id) REFERENCES subjects(id),
        FOREIGN KEY (parent_topic_id) REFERENCES topics(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS subtopics (
        id TEXT PRIMARY KEY,
        topic_id TEXT NOT NULL,
        name TEXT NOT NULL,
        display_order INTEGER NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS topic_notes (
        id TEXT PRIMARY KEY,
        topic_id TEXT NOT NULL UNIQUE,
        content_json TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS notes (
        id TEXT PRIMARY KEY,
        exam_id TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        topic_id TEXT NOT NULL UNIQUE,
        content_json TEXT NOT NULL,
        version INTEGER NOT NULL,
        content_hash TEXT NOT NULL,
        source_prompt_hash TEXT NOT NULL,
        ai_model TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        is_deleted INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (exam_id) REFERENCES exams(id),
        FOREIGN KEY (subject_id) REFERENCES subjects(id),
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS questions (
        id TEXT PRIMARY KEY,
        exam_id TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        topic_id TEXT NOT NULL,
        type TEXT NOT NULL,
        prompt TEXT NOT NULL,
        options_json TEXT,
        answer_key TEXT,
        explanation TEXT NOT NULL,
        explanation_hint TEXT NOT NULL,
        difficulty TEXT NOT NULL,
        metadata_json TEXT NOT NULL,
        version INTEGER NOT NULL,
        bundle_hash TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        is_deleted INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (exam_id) REFERENCES exams(id),
        FOREIGN KEY (subject_id) REFERENCES subjects(id),
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS model_answers (
        id TEXT PRIMARY KEY,
        topic_id TEXT NOT NULL,
        question_hash TEXT NOT NULL,
        question_text TEXT NOT NULL,
        content_json TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        ai_model TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(topic_id, question_hash),
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS text_embeddings (
        id TEXT PRIMARY KEY,
        text_hash TEXT NOT NULL UNIQUE,
        raw_text TEXT NOT NULL,
        vector_json TEXT NOT NULL,
        provider TEXT NOT NULL,
        model TEXT NOT NULL,
        dimension INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS answers (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        topic_id TEXT NOT NULL,
        question_text TEXT NOT NULL,
        raw_answer_text TEXT NOT NULL,
        cleaned_answer_text TEXT NOT NULL,
        sentence_list_json TEXT NOT NULL,
        input_mode TEXT NOT NULL,
        ocr_text TEXT,
        max_marks INTEGER NOT NULL,
        answer_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS calibration_weights (
        id TEXT PRIMARY KEY,
        must_weight REAL NOT NULL,
        good_weight REAL NOT NULL,
        similarity_weight REAL NOT NULL,
        coverage_weight REAL NOT NULL,
        depth_weight REAL NOT NULL,
        directive_weight REAL NOT NULL,
        extra_weight REAL NOT NULL,
        fact_weight REAL NOT NULL,
        maturity_weight REAL NOT NULL,
        impression_weight REAL NOT NULL DEFAULT 0.5,
        impression_score_correlation REAL NOT NULL DEFAULT 0.0,
        impression_score_mismatch REAL NOT NULL DEFAULT 0.0,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS evaluation_history (
        id TEXT PRIMARY KEY,
        answer_id TEXT NOT NULL UNIQUE,
        user_id TEXT NOT NULL,
        topic_id TEXT NOT NULL,
        question_hash TEXT NOT NULL,
        model_answer_id TEXT,
        score INTEGER NOT NULL,
        percentile REAL NOT NULL,
        performance_band TEXT NOT NULL,
        analysis_json TEXT NOT NULL,
        similarity_json TEXT NOT NULL,
        feature_json TEXT NOT NULL,
        scoring_json TEXT NOT NULL,
        mistakes_json TEXT NOT NULL,
        ideal_answer_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (answer_id) REFERENCES answers(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (topic_id) REFERENCES topics(id),
        FOREIGN KEY (model_answer_id) REFERENCES model_answers(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS calibration_samples (
        id TEXT PRIMARY KEY,
        evaluation_history_id TEXT NOT NULL UNIQUE,
        user_id TEXT NOT NULL,
        topic_id TEXT NOT NULL,
        features_json TEXT NOT NULL,
        predicted_score REAL NOT NULL,
        manual_score REAL,
        weights_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (evaluation_history_id) REFERENCES evaluation_history(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS flashcards (
        id TEXT PRIMARY KEY,
        topic_id TEXT NOT NULL,
        card_type TEXT NOT NULL,
        question_text TEXT NOT NULL,
        answer_text TEXT NOT NULL,
        explanation TEXT NOT NULL,
        difficulty TEXT NOT NULL,
        source_hash TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        is_deleted INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS revision_progress (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        flashcard_id TEXT NOT NULL,
        ease_factor REAL NOT NULL,
        interval_days REAL NOT NULL,
        next_review TEXT NOT NULL,
        correct_count INTEGER NOT NULL,
        incorrect_count INTEGER NOT NULL,
        last_result TEXT,
        last_reviewed_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(user_id, flashcard_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (flashcard_id) REFERENCES flashcards(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS attempts (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        exam_id TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        topic_id TEXT NOT NULL,
        question_id TEXT NOT NULL,
        answer_text TEXT,
        selected_option TEXT,
        answer_mode TEXT NOT NULL,
        answer_artifact_json TEXT NOT NULL,
        score REAL NOT NULL,
        is_correct INTEGER,
        review_due_at_day3 TEXT NOT NULL,
        review_due_at_day7 TEXT NOT NULL,
        submitted_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (question_id) REFERENCES questions(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS evaluations (
        id TEXT PRIMARY KEY,
        attempt_id TEXT NOT NULL UNIQUE,
        user_id TEXT NOT NULL,
        question_id TEXT NOT NULL,
        mode TEXT NOT NULL,
        score REAL NOT NULL,
        max_score REAL NOT NULL,
        verdict TEXT NOT NULL,
        rubric_json TEXT NOT NULL,
        strengths_json TEXT NOT NULL,
        improvements_json TEXT NOT NULL,
        extracted_text TEXT,
        reasoning_summary TEXT NOT NULL,
        ai_model TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (attempt_id) REFERENCES attempts(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (question_id) REFERENCES questions(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS revision_schedule (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        exam_id TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        topic_id TEXT NOT NULL,
        attempt_id TEXT NOT NULL,
        stage TEXT NOT NULL,
        due_at TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (attempt_id) REFERENCES attempts(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS performance (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        scope_type TEXT NOT NULL,
        exam_id TEXT,
        subject_id TEXT,
        topic_id TEXT,
        accuracy REAL NOT NULL,
        average_score REAL NOT NULL,
        trend_delta REAL NOT NULL DEFAULT 0.0,
        total_attempts INTEGER NOT NULL,
        correct_attempts INTEGER NOT NULL,
        revisions_due INTEGER NOT NULL,
        revisions_completed INTEGER NOT NULL,
        next_review_at TEXT,
        last_activity_at TEXT,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_continuity (
        user_id TEXT PRIMARY KEY,
        daily_answer_streak INTEGER NOT NULL DEFAULT 0,
        last_answer_date TEXT,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_topic_weakness (
        user_id TEXT NOT NULL,
        topic_id TEXT NOT NULL,
        structure_weak_count INTEGER NOT NULL DEFAULT 0,
        relevance_weak_count INTEGER NOT NULL DEFAULT 0,
        content_weak_count INTEGER NOT NULL DEFAULT 0,
        most_repeated_mistake TEXT NOT NULL DEFAULT '',
        most_repeated_mistake_count INTEGER NOT NULL DEFAULT 0,
        last_mistake TEXT NOT NULL DEFAULT '',
        consecutive_mistake_count INTEGER NOT NULL DEFAULT 0,
        last_weakest_dimension TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL,
        PRIMARY KEY (user_id, topic_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS subtopic_notes (
        id TEXT PRIMARY KEY,
        subtopic_id TEXT NOT NULL UNIQUE,
        topic_id TEXT NOT NULL,
        content_json TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (subtopic_id) REFERENCES subtopics(id),
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_subtopic_progress (
        user_id TEXT NOT NULL,
        subtopic_id TEXT NOT NULL,
        topic_id TEXT NOT NULL,
        status TEXT NOT NULL,
        weakness_flag INTEGER NOT NULL DEFAULT 0,
        last_attempted_at TEXT,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (user_id, subtopic_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (subtopic_id) REFERENCES subtopics(id),
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_subtopic_weakness (
        user_id TEXT NOT NULL,
        subtopic_id TEXT NOT NULL,
        topic_id TEXT NOT NULL,
        weakest_dimension TEXT NOT NULL,
        repeated_mistake TEXT NOT NULL DEFAULT '',
        repeated_mistake_count INTEGER NOT NULL DEFAULT 0,
        consecutive_mistake_count INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (user_id, subtopic_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (subtopic_id) REFERENCES subtopics(id),
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    )
    """,
]

MIGRATION_STATEMENTS = [
    "ALTER TABLE topics ADD COLUMN knowledge_json TEXT NOT NULL DEFAULT '{}'",
    "ALTER TABLE topics ADD COLUMN parent_topic_id TEXT",
    "ALTER TABLE topics ADD COLUMN display_order INTEGER NOT NULL DEFAULT 0",
    """
    CREATE TABLE IF NOT EXISTS subtopics (
        id TEXT PRIMARY KEY,
        topic_id TEXT NOT NULL,
        name TEXT NOT NULL,
        display_order INTEGER NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS topic_notes (
        id TEXT PRIMARY KEY,
        topic_id TEXT NOT NULL UNIQUE,
        content_json TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    )
    """,
    "ALTER TABLE calibration_weights ADD COLUMN impression_weight REAL NOT NULL DEFAULT 0.5",
    "ALTER TABLE calibration_weights ADD COLUMN impression_score_correlation REAL NOT NULL DEFAULT 0.0",
    "ALTER TABLE calibration_weights ADD COLUMN impression_score_mismatch REAL NOT NULL DEFAULT 0.0",
    "ALTER TABLE performance ADD COLUMN trend_delta REAL NOT NULL DEFAULT 0.0",
    """
    CREATE TABLE IF NOT EXISTS user_topic_weakness (
        user_id TEXT NOT NULL,
        topic_id TEXT NOT NULL,
        structure_weak_count INTEGER NOT NULL DEFAULT 0,
        relevance_weak_count INTEGER NOT NULL DEFAULT 0,
        content_weak_count INTEGER NOT NULL DEFAULT 0,
        most_repeated_mistake TEXT NOT NULL DEFAULT '',
        most_repeated_mistake_count INTEGER NOT NULL DEFAULT 0,
        last_mistake TEXT NOT NULL DEFAULT '',
        consecutive_mistake_count INTEGER NOT NULL DEFAULT 0,
        last_weakest_dimension TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL,
        PRIMARY KEY (user_id, topic_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS subtopic_notes (
        id TEXT PRIMARY KEY,
        subtopic_id TEXT NOT NULL UNIQUE,
        topic_id TEXT NOT NULL,
        content_json TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (subtopic_id) REFERENCES subtopics(id),
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_subtopic_progress (
        user_id TEXT NOT NULL,
        subtopic_id TEXT NOT NULL,
        topic_id TEXT NOT NULL,
        status TEXT NOT NULL,
        weakness_flag INTEGER NOT NULL DEFAULT 0,
        last_attempted_at TEXT,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (user_id, subtopic_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (subtopic_id) REFERENCES subtopics(id),
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_subtopic_weakness (
        user_id TEXT NOT NULL,
        subtopic_id TEXT NOT NULL,
        topic_id TEXT NOT NULL,
        weakest_dimension TEXT NOT NULL,
        repeated_mistake TEXT NOT NULL DEFAULT '',
        repeated_mistake_count INTEGER NOT NULL DEFAULT 0,
        consecutive_mistake_count INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (user_id, subtopic_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (subtopic_id) REFERENCES subtopics(id),
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    )
    """,
]


def _row_from_cursor(cursor: Any) -> dict[str, Any] | None:
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))


def _rows_from_cursor(cursor: Any) -> list[dict[str, Any]]:
    rows = cursor.fetchall()
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


class Database:
    def __init__(self) -> None:
        self._local_path = settings.db_path
        Path(self._local_path).parent.mkdir(parents=True, exist_ok=True)

    @property
    def storage_mode(self) -> str:
        return "turso" if settings.turso_enabled and HAS_LIBSQL else "local"

    def _connect(self):
        if settings.turso_enabled and HAS_LIBSQL:
            return libsql_driver.connect(str(self._local_path), sync_url=settings.turso_database_url, auth_token=settings.turso_auth_token)
        return libsql_driver.connect(str(self._local_path))

    @contextmanager
    def session(self, write: bool = False) -> Iterator[Any]:
        conn = self._connect()
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            if write:
                conn.commit()
                if settings.turso_enabled and HAS_LIBSQL and hasattr(conn, "sync"):
                    conn.sync()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.session(write=True) as conn:
            for statement in SCHEMA_STATEMENTS:
                conn.execute(statement)
            for statement in MIGRATION_STATEMENTS:
                try:
                    conn.execute(statement)
                except Exception:  # noqa: BLE001
                    continue

    def fetch_one(self, sql: str, args: list[Any] | tuple[Any, ...] | None = None) -> dict[str, Any] | None:
        with self.session() as conn:
            cursor = conn.execute(sql, args or [])
            return _row_from_cursor(cursor)

    def fetch_all(self, sql: str, args: list[Any] | tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        with self.session() as conn:
            cursor = conn.execute(sql, args or [])
            return _rows_from_cursor(cursor)

    def execute(self, sql: str, args: list[Any] | tuple[Any, ...] | None = None) -> None:
        with self.session(write=True) as conn:
            conn.execute(sql, args or [])


db = Database()
