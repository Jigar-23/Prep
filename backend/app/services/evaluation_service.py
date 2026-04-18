from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.database import db
from app.errors import ApiError
from app.services.ai_service import ai_service
from app.services.content_service import get_question_by_id
from app.services.continuity_service import update_answer_streak
from app.services.performance_service import get_performance_snapshot, refresh_user_performance
from app.utils.common import new_id, stable_json_dumps, utc_now_iso


def _revision_due(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _complete_due_revisions(user_id: str, topic_id: str) -> None:
    now = utc_now_iso()
    with db.session(write=True) as conn:
        conn.execute(
            """
            UPDATE revision_schedule
            SET status = 'completed', updated_at = ?
            WHERE user_id = ? AND topic_id = ? AND status = 'pending' AND due_at <= ?
            """,
            [now, user_id, topic_id, now],
        )


def _schedule_revisions(user_id: str, attempt: dict) -> None:
    now = utc_now_iso()
    with db.session(write=True) as conn:
        for stage, due_at in [("d3", attempt["review_due_at_day3"]), ("d7", attempt["review_due_at_day7"])]:
            conn.execute(
                """
                INSERT INTO revision_schedule
                (id, user_id, exam_id, subject_id, topic_id, attempt_id, stage, due_at, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                [
                    new_id("rev"),
                    user_id,
                    attempt["exam_id"],
                    attempt["subject_id"],
                    attempt["topic_id"],
                    attempt["id"],
                    stage,
                    due_at,
                    now,
                    now,
                ],
            )


def evaluate_submission(user_id: str, payload: dict) -> dict:
    question = get_question_by_id(payload["question_id"])
    if question["topic_id"] != payload["topic_id"]:
        raise ApiError(400, "INVALID_ANSWER", "Question does not belong to the supplied topic.")

    answer_mode = "text"
    if payload.get("selected_option"):
        answer_mode = "mcq"
    if payload.get("handwritten_image_base64"):
        answer_mode = "text+image" if payload.get("answer_text") else "image"

    if question["type"] == "mcq" and not payload.get("selected_option"):
        raise ApiError(400, "INVALID_ANSWER", "Selected option is required for MCQ evaluation.")
    if question["type"] == "mains" and not payload.get("answer_text") and not payload.get("handwritten_image_base64"):
        raise ApiError(400, "INVALID_ANSWER", "Answer text or handwritten image is required.")

    if question["type"] == "mcq":
        is_correct = payload["selected_option"] == question["answer_key"]
        score = 10.0 if is_correct else 0.0
        evaluation = {
            "score": score,
            "max_score": 10,
            "verdict": "excellent" if is_correct else "incorrect",
            "rubric": {"accuracy": score, "structure": 0.0, "depth": 0.0},
            "strengths": ["Correct option selected."] if is_correct else [],
            "improvements": [] if is_correct else ["Revise the concept and compare each option before choosing."],
            "extracted_text": None,
            "reasoning_summary": question["explanation"],
        }
        provider = "database"
    else:
        evaluation, provider = ai_service.evaluate_answer(
            question=question,
            answer_text=payload.get("answer_text"),
            image_base64=payload.get("handwritten_image_base64"),
            image_mime_type=payload.get("handwritten_image_mime_type"),
        )
        is_correct = 1 if evaluation["score"] >= 6 else 0

    submitted_at = utc_now_iso()
    attempt = {
        "id": new_id("att"),
        "user_id": user_id,
        "exam_id": payload["exam_id"],
        "subject_id": payload["subject_id"],
        "topic_id": payload["topic_id"],
        "question_id": payload["question_id"],
        "answer_text": payload.get("answer_text"),
        "selected_option": payload.get("selected_option"),
        "answer_mode": answer_mode,
        "answer_artifact_json": stable_json_dumps(
            {
                "has_image": bool(payload.get("handwritten_image_base64")),
                "image_mime_type": payload.get("handwritten_image_mime_type"),
                "answer_text_length": len(payload.get("answer_text") or ""),
            }
        ),
        "score": float(evaluation["score"]),
        "is_correct": is_correct,
        "review_due_at_day3": _revision_due(3),
        "review_due_at_day7": _revision_due(7),
        "submitted_at": submitted_at,
    }
    evaluation_row = {
        "id": new_id("eval"),
        "attempt_id": attempt["id"],
        "user_id": user_id,
        "question_id": payload["question_id"],
        "mode": answer_mode,
        "score": float(evaluation["score"]),
        "max_score": float(evaluation["max_score"]),
        "verdict": evaluation["verdict"],
        "rubric_json": evaluation["rubric"],
        "strengths_json": evaluation["strengths"],
        "improvements_json": evaluation["improvements"],
        "extracted_text": evaluation.get("extracted_text"),
        "reasoning_summary": evaluation["reasoning_summary"],
        "ai_model": provider,
        "updated_at": submitted_at,
    }

    with db.session(write=True) as conn:
        conn.execute(
            """
            INSERT INTO attempts
            (id, user_id, exam_id, subject_id, topic_id, question_id, answer_text, selected_option,
             answer_mode, answer_artifact_json, score, is_correct, review_due_at_day3, review_due_at_day7, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                attempt["id"],
                attempt["user_id"],
                attempt["exam_id"],
                attempt["subject_id"],
                attempt["topic_id"],
                attempt["question_id"],
                attempt["answer_text"],
                attempt["selected_option"],
                attempt["answer_mode"],
                attempt["answer_artifact_json"],
                attempt["score"],
                attempt["is_correct"],
                attempt["review_due_at_day3"],
                attempt["review_due_at_day7"],
                attempt["submitted_at"],
            ],
        )
        conn.execute(
            """
            INSERT INTO evaluations
            (id, attempt_id, user_id, question_id, mode, score, max_score, verdict, rubric_json,
             strengths_json, improvements_json, extracted_text, reasoning_summary, ai_model, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                evaluation_row["id"],
                evaluation_row["attempt_id"],
                evaluation_row["user_id"],
                evaluation_row["question_id"],
                evaluation_row["mode"],
                evaluation_row["score"],
                evaluation_row["max_score"],
                evaluation_row["verdict"],
                stable_json_dumps(evaluation_row["rubric_json"]),
                stable_json_dumps(evaluation_row["strengths_json"]),
                stable_json_dumps(evaluation_row["improvements_json"]),
                evaluation_row["extracted_text"],
                evaluation_row["reasoning_summary"],
                evaluation_row["ai_model"],
                evaluation_row["updated_at"],
            ],
        )

    _complete_due_revisions(user_id, payload["topic_id"])
    _schedule_revisions(user_id, attempt)
    update_answer_streak(user_id, submitted_at)
    refresh_user_performance(user_id)
    snapshot = get_performance_snapshot(user_id)

    topic_row = next((row for row in snapshot["topic_breakdown"] if row["topic_id"] == payload["topic_id"]), None)
    subject_row = next((row for row in snapshot["subject_breakdown"] if row["subject_id"] == payload["subject_id"]), None)
    exam_row = next((row for row in snapshot["exam_breakdown"] if row["exam_id"] == payload["exam_id"]), None)

    return {
        "attempt": {
            "id": attempt["id"],
            "question_id": attempt["question_id"],
            "score": attempt["score"],
            "submitted_at": attempt["submitted_at"],
        },
        "evaluation": {
            "id": evaluation_row["id"],
            "mode": evaluation_row["mode"],
            "score": evaluation_row["score"],
            "max_score": evaluation_row["max_score"],
            "verdict": evaluation_row["verdict"],
            "strengths": evaluation["strengths"],
            "improvements": evaluation["improvements"],
            "rubric": evaluation["rubric"],
            "extracted_text": evaluation.get("extracted_text"),
            "reasoning_summary": evaluation["reasoning_summary"],
        },
        "performance": {
            "overall_accuracy": snapshot["summary"]["overall_accuracy"],
            "topic_accuracy": topic_row["accuracy"] if topic_row else 0.0,
            "subject_accuracy": subject_row["accuracy"] if subject_row else 0.0,
            "exam_accuracy": exam_row["accuracy"] if exam_row else 0.0,
        },
    }
