from __future__ import annotations

import json
import re

from app.database import db
from app.errors import ApiError
from app.utils.common import new_id, sha256_json, stable_json_dumps, utc_now_iso


def _guess_key_facts(subtopic_title: str) -> list[str]:
    title = subtopic_title.strip()
    lowered = title.lower()
    year = re.search(r"\b(16|17|18|19|20)\d{2}\b", title)
    facts: list[str] = []
    if "regulating act" in lowered:
        facts = ["Regulating Act, 1773: first step to control Company", "Governor-General of Bengal created", "Supreme Court at Calcutta (1774)"]
    elif "pitts india act" in lowered or "pitt" in lowered:
        facts = ["Pitt’s India Act, 1784: dual control", "Board of Control + Court of Directors", "Company reduced to subordinate role"]
    elif "charter act" in lowered:
        facts = ["Charter Acts renewed Company’s charter", "Shift from trade to administration", "Legislative/administrative centralisation expanded"]
    elif "goi act" in lowered or "government of india act" in lowered or (year and year.group(0) == "1935"):
        facts = ["GOI Act, 1935: provincial autonomy", "Federal scheme proposed (not fully operational)", "Bicameralism introduced in some provinces"]
    elif "east india company" in lowered or "company" in lowered:
        facts = ["Company begins as trading entity", "Territorial expansion through wars and treaties", "Revenue administration shapes colonial state"]
    elif year:
        facts = [f"{title}: key provision snapshot ({year.group(0)})."]
    else:
        facts = [f"{title}: one concrete anchor (term/committee/act)."]
    return facts[:4]


def _diagram_flow(subtopic_title: str) -> list[str]:
    return [
        f"{subtopic_title}",
        "→ Trigger/Context",
        "→ Core change",
        "→ Impact on governance",
        "→ UPSC linkage",
    ]


class SubtopicNotesService:
    def ensure_notes(self, *, subtopic_id: str) -> dict:
        subtopic = db.fetch_one("SELECT * FROM subtopics WHERE id = ?", [subtopic_id])
        if not subtopic:
            raise ApiError(404, "SUBTOPIC_NOT_FOUND", "Subtopic not found.")
        topic = db.fetch_one("SELECT * FROM topics WHERE id = ? AND is_deleted = 0", [subtopic["topic_id"]])
        if not topic:
            raise ApiError(404, "TOPIC_NOT_FOUND", "Chapter not found.")

        row = db.fetch_one("SELECT * FROM subtopic_notes WHERE subtopic_id = ?", [subtopic_id])
        if row:
            payload = json.loads(row["content_json"])
            return {
                "subtopic_id": subtopic_id,
                "topic_id": subtopic["topic_id"],
                "content_hash": row["content_hash"],
                "updated_at": row["updated_at"],
                **payload,
            }

        title = subtopic["name"]
        facts = _guess_key_facts(title)
        quick_recall = [
            facts[0],
            facts[1] if len(facts) > 1 else f"{title}: define and locate in chronology.",
            "Exam demand: write in cause → change → impact order.",
        ][:4]

        framework = {
            "intro": [f"Context: {title} as a step in colonial constitutional evolution."],
            "body": [
                "Provision/feature: what changed",
                "Control mechanism: who gained power",
                "Impact: governance/administration consequence",
            ],
            "conclusion": ["Link: how it shaped later constitutional development."],
        }

        ready_answer = (
            f"{title} marked an important stage in British administrative control over India. "
            f"It created mechanisms to supervise Company governance and reduce arbitrary decision-making. "
            f"Key features included institutional changes that strengthened oversight and centralised authority. "
            f"This altered how revenues, administration, and law were managed, influencing later reforms. "
            f"In UPSC answers, present it as context, core provisions, impact, and linkage to later Acts."
        )

        payload = {
            "quick_recall": quick_recall,
            "structured_answer_framework": framework,
            "ready_answer_150": ready_answer[:950],
            "key_facts_examples": facts,
            "value_addition": [
                "Keywords: dual control, centralisation, oversight, constitutional evolution",
                "Linkage: modern governance institutions and accountability",
            ],
            "diagram_flow": _diagram_flow(title),
        }

        now = utc_now_iso()
        db.execute(
            """
            INSERT OR REPLACE INTO subtopic_notes
            (id, subtopic_id, topic_id, content_json, content_hash, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                new_id("snote"),
                subtopic_id,
                subtopic["topic_id"],
                stable_json_dumps(payload),
                sha256_json(payload),
                now,
            ],
        )

        return {
            "subtopic_id": subtopic_id,
            "topic_id": subtopic["topic_id"],
            "content_hash": sha256_json(payload),
            "updated_at": now,
            **payload,
        }


subtopic_notes_service = SubtopicNotesService()

