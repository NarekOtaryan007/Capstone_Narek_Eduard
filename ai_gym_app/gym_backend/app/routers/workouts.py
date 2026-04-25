from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
import os
import json
import random

import openpyxl

from app.database.connection import get_db

router = APIRouter()

# ── Load recommendation lookup table once at import time ──────────────────────
_REC_LOOKUP: dict = {}

def _load_recommendations() -> None:
    data_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "data", "gym_recommendation.xlsx"
    )
    if not os.path.exists(data_path):
        return
    wb = openpyxl.load_workbook(data_path, read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(min_row=2, values_only=True)
    for r in rows:
        key = (r[8], r[5], r[6])   # (Level, Hypertension, Diabetes)
        if key not in _REC_LOOKUP:
            _REC_LOOKUP[key] = {
                "goal":           r[9],
                "fitness_type":   r[10],
                "exercises":      r[11],
                "equipment":      r[12],
                "diet":           r[13],
                "recommendation": r[14],
            }
    wb.close()

_load_recommendations()


def _profile_recommendation(height_str, weight_str, injuries_str) -> Optional[dict]:
    """Return the dataset row that matches this user's computed BMI + health flags."""
    try:
        height = float(height_str)
        if height > 3:          # stored in cm → convert to metres
            height /= 100
        weight = float(weight_str)
        bmi = weight / (height ** 2)

        if bmi < 18.5:
            level = "Underweight"
        elif bmi < 25:
            level = "Normal"
        elif bmi < 30:
            level = "Overweight"
        else:
            level = "Obuse"     # dataset uses this spelling

        injuries_lower = (injuries_str or "").lower()
        hypertension = "Yes" if any(w in injuries_lower for w in ("hypertension", "blood pressure", "hypertensive")) else "No"
        diabetes = "Yes" if any(w in injuries_lower for w in ("diabetes", "diabetic")) else "No"

        return _REC_LOOKUP.get((level, hypertension, diabetes))
    except Exception:
        return None


@router.get("/generate-ai-workout")
def generate_ai_workout(
    days: int = 3,
    level: Optional[str] = None,
    username: Optional[str] = None,
    db: Session = Depends(get_db),
):
    # ── Fetch exercise pool from DB ──
    query = "SELECT id, name, level, equipment, category FROM exercises"
    params: dict = {}
    if level:
        query += " WHERE level = :level"
        params["level"] = level
    query += " ORDER BY RANDOM() LIMIT 80"

    rows = db.execute(text(query), params).fetchall()
    exercises = [
        {"id": row[0], "name": row[1], "level": row[2], "equipment": row[3], "category": row[4]}
        for row in rows
    ]

    # ── Fetch user profile ──
    user_context = ""
    rec = None
    if username:
        row = db.execute(
            text("SELECT level, injuries_other, height, weight FROM users WHERE username = :username"),
            {"username": username},
        ).fetchone()
        if row:
            parts = []
            if row[0]: parts.append(f"fitness experience level: {row[0]}")
            if row[1]: parts.append(f"injuries/limitations: {row[1]}")
            if row[2]: parts.append(f"height: {row[2]}")
            if row[3]: parts.append(f"weight: {row[3]}")
            if parts:
                user_context = "User profile — " + ", ".join(parts) + "."

            # Look up dataset recommendation using BMI + health flags
            rec = _profile_recommendation(row[2], row[3], row[1])

    # ── Call Claude API ──
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return _random_fallback(days, level, exercises, rec)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        exercise_names = json.dumps([e["name"] for e in exercises])

        rec_block = ""
        if rec:
            rec_block = (
                f"\nEvidence-based context for this user (from clinical dataset):\n"
                f"- Recommended fitness goal: {rec['goal']}\n"
                f"- Fitness type: {rec['fitness_type']}\n"
                f"- Suggested exercises (for reference): {rec['exercises']}\n"
                f"- Diet guidance: {rec['diet']}\n"
                f"- General recommendation: {rec['recommendation'][:400]}\n"
            )

        prompt = (
            f"You are a certified personal trainer. Create a {days}-day workout plan.\n"
            + (f"{user_context}\n" if user_context else "")
            + rec_block
            + f"\nChoose exercises ONLY from this list (use the exact names provided):\n{exercise_names}\n\n"
            "Respond with ONLY a valid JSON object — no extra text, no markdown fences — like:\n"
            '{"Day 1": ["Exercise A", "Exercise B", "Exercise C", "Exercise D", "Exercise E"], "Day 2": [...]}\n'
            "Each day must have exactly 5 exercises. Balance muscle groups across days."
        )

        message = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        plan_names: dict = json.loads(raw)
        name_map = {e["name"]: e for e in exercises}
        workout_plan = {
            day: [name_map[n] for n in names if n in name_map]
            for day, names in plan_names.items()
        }
        workout_plan = {d: ex for d, ex in workout_plan.items() if ex}

        if not workout_plan:
            return _random_fallback(days, level, exercises, rec)

        result = {"days": days, "level": level, "workout": workout_plan}
        if rec:
            result["diet_tip"] = rec["diet"]
            result["recommendation"] = rec["recommendation"]
        return result

    except Exception:
        return _random_fallback(days, level, exercises, rec)


def _random_fallback(days: int, level: Optional[str], exercises: list, rec: Optional[dict]) -> dict:
    workout_plan = {}
    for i in range(days):
        sample = random.sample(exercises, min(5, len(exercises)))
        workout_plan[f"Day {i + 1}"] = sample
    result = {"days": days, "level": level, "workout": workout_plan}
    if rec:
        result["diet_tip"] = rec["diet"]
        result["recommendation"] = rec["recommendation"]
    return result
