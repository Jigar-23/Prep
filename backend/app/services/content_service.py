from __future__ import annotations

import json
import threading
from typing import Any

from app.database import db
from app.errors import ApiError
from app.services.ai_service import ai_service
from app.utils.common import new_id, sha256_json, stable_json_dumps, utc_now_iso


_topic_locks: dict[str, threading.Lock] = {}
DEFAULT_QUESTION_COUNTS = {"mcq": 5, "mains": 1}


def _parse_topic(record: dict | None) -> dict:
    if not record:
        raise ApiError(404, "TOPIC_NOT_FOUND", "Requested topic does not exist.")
    topic = dict(record)
    topic["learning_objectives"] = json.loads(topic["learning_objectives_json"])
    return topic


def _get_lock(topic_id: str) -> threading.Lock:
    if topic_id not in _topic_locks:
        _topic_locks[topic_id] = threading.Lock()
    return _topic_locks[topic_id]


def _get_catalog_records(exam_id: str, subject_id: str, topic_id: str) -> tuple[dict, dict, dict]:
    exam = db.fetch_one("SELECT * FROM exams WHERE id = ?", [exam_id])
    subject = db.fetch_one("SELECT * FROM subjects WHERE id = ? AND exam_id = ?", [subject_id, exam_id])
    topic = db.fetch_one("SELECT * FROM topics WHERE id = ? AND subject_id = ? AND exam_id = ?", [topic_id, subject_id, exam_id])
    if not exam or not subject or not topic:
        raise ApiError(404, "TOPIC_NOT_FOUND", "Exam, subject, or topic could not be found.")
    return exam, subject, _parse_topic(topic)


def _question_public(record: dict) -> dict:
    return {
        "id": record["id"],
        "topic_id": record["topic_id"],
        "type": record["type"],
        "prompt": record["prompt"],
        "options": json.loads(record["options_json"]) if record["options_json"] else None,
        "difficulty": record["difficulty"],
        "explanation_hint": record["explanation_hint"],
        "metadata": json.loads(record["metadata_json"]),
    }


def ensure_content_bundle(exam_id: str, subject_id: str, topic_id: str) -> tuple[dict, list[dict], str]:
    notes = db.fetch_one("SELECT * FROM notes WHERE topic_id = ? AND is_deleted = 0", [topic_id])
    questions = db.fetch_all("SELECT * FROM questions WHERE topic_id = ? AND is_deleted = 0 ORDER BY type ASC, id ASC", [topic_id])
    if notes and questions:
        return notes, questions, "database"

    exam, subject, topic = _get_catalog_records(exam_id, subject_id, topic_id)
    lock = _get_lock(topic_id)
    with lock:
        notes = db.fetch_one("SELECT * FROM notes WHERE topic_id = ? AND is_deleted = 0", [topic_id])
        questions = db.fetch_all("SELECT * FROM questions WHERE topic_id = ? AND is_deleted = 0 ORDER BY type ASC, id ASC", [topic_id])
        if notes and questions:
            return notes, questions, "database"

        generated, source = ai_service.generate_bundle(exam, subject, topic)
        now = utc_now_iso()
        note_content = generated["notes"]
        note_hash = sha256_json(note_content)
        note_record = {
            "id": new_id("note"),
            "exam_id": exam_id,
            "subject_id": subject_id,
            "topic_id": topic_id,
            "content_json": stable_json_dumps(note_content),
            "version": 1,
            "content_hash": note_hash,
            "source_prompt_hash": sha256_json(
                {
                    "exam": exam["name"],
                    "subject": subject["name"],
                    "topic": topic["name"],
                    "objectives": topic["learning_objectives"],
                }
            ),
            "ai_model": "demo" if source == "demo" else "gemini-1.5-pro",
            "updated_at": now,
        }
        question_payload = generated["questions"]
        bundle_hash = sha256_json(question_payload)

        with db.session(write=True) as conn:
            conn.execute("DELETE FROM questions WHERE topic_id = ?", [topic_id])
            conn.execute(
                """
                INSERT OR REPLACE INTO notes
                (id, exam_id, subject_id, topic_id, content_json, version, content_hash,
                 source_prompt_hash, ai_model, updated_at, is_deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                [
                    note_record["id"],
                    note_record["exam_id"],
                    note_record["subject_id"],
                    note_record["topic_id"],
                    note_record["content_json"],
                    note_record["version"],
                    note_record["content_hash"],
                    note_record["source_prompt_hash"],
                    note_record["ai_model"],
                    note_record["updated_at"],
                ],
            )
            for question in question_payload:
                options = question.get("options")
                question_hash = sha256_json(question)
                conn.execute(
                    """
                    INSERT INTO questions
                    (id, exam_id, subject_id, topic_id, type, prompt, options_json, answer_key,
                     explanation, explanation_hint, difficulty, metadata_json, version, bundle_hash,
                     content_hash, updated_at, is_deleted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    [
                        new_id("q"),
                        exam_id,
                        subject_id,
                        topic_id,
                        question["type"],
                        question["prompt"],
                        stable_json_dumps(options) if options else None,
                        question.get("correct_option_id"),
                        question["explanation"],
                        question["explanation_hint"],
                        question["difficulty"],
                        stable_json_dumps(question.get("metadata", {})),
                        1,
                        bundle_hash,
                        question_hash,
                        now,
                    ],
                )

        saved_notes = db.fetch_one("SELECT * FROM notes WHERE topic_id = ?", [topic_id])
        saved_questions = db.fetch_all("SELECT * FROM questions WHERE topic_id = ? ORDER BY type ASC, id ASC", [topic_id])
        return saved_notes, saved_questions, source


def get_note_response(exam_id: str, subject_id: str, topic_id: str, client_version: int | None, client_hash: str | None) -> dict:
    note_row, questions, source = ensure_content_bundle(exam_id, subject_id, topic_id)
    if client_version == note_row["version"] and client_hash == note_row["content_hash"]:
        return {
            "sync_status": "not_modified",
            "source": source if source in {"ai", "demo"} else "database",
            "note": None,
            "question_counts": {
                "mcq": sum(1 for item in questions if item["type"] == "mcq"),
                "mains": sum(1 for item in questions if item["type"] == "mains"),
            },
        }

    payload = {
        "id": note_row["id"],
        "exam_id": note_row["exam_id"],
        "subject_id": note_row["subject_id"],
        "topic_id": note_row["topic_id"],
        "version": note_row["version"],
        "content_hash": note_row["content_hash"],
        "updated_at": note_row["updated_at"],
        "content": json.loads(note_row["content_json"]),
    }
    return {
        "sync_status": "generated" if source in {"ai", "demo"} else "updated",
        "source": source if source in {"ai", "demo"} else "database",
        "note": payload,
        "question_counts": {
            "mcq": sum(1 for item in questions if item["type"] == "mcq"),
            "mains": sum(1 for item in questions if item["type"] == "mains"),
        },
    }


def get_question_response(
    exam_id: str,
    subject_id: str,
    topic_id: str,
    include_types: list[str],
    client_version: int | None,
    client_hash: str | None,
) -> dict:
    _, questions, source = ensure_content_bundle(exam_id, subject_id, topic_id)
    if not questions:
        raise ApiError(500, "CONTENT_MISSING", "Question bundle is unavailable.")

    bundle_version = questions[0]["version"]
    bundle_hash = questions[0]["bundle_hash"]
    filtered = [_question_public(question) for question in questions if question["type"] in include_types]

    if client_version == bundle_version and client_hash == bundle_hash:
        return {
            "sync_status": "not_modified",
            "source": source if source in {"ai", "demo"} else "database",
            "bundle": {"version": bundle_version, "content_hash": bundle_hash},
            "questions": [],
        }

    return {
        "sync_status": "generated" if source in {"ai", "demo"} else "updated",
        "source": source if source in {"ai", "demo"} else "database",
        "bundle": {"version": bundle_version, "content_hash": bundle_hash},
        "questions": filtered,
    }


def get_question_by_id(question_id: str) -> dict:
    question = db.fetch_one("SELECT * FROM questions WHERE id = ? AND is_deleted = 0", [question_id])
    if not question:
        raise ApiError(404, "QUESTION_NOT_FOUND", "Question does not exist.")
    return question
