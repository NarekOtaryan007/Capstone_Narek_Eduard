from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import json

from app.database.connection import get_db

router = APIRouter()


@router.post("/save-workout")
def save_workout(data: dict, db: Session = Depends(get_db)):
    username = data.get("username")
    workout = data.get("workout")

    if not username or not workout:
        return {"error": "username and workout are required"}

    result = db.execute(
        text("SELECT workouts FROM users WHERE username = :username"),
        {"username": username}
    ).fetchone()

    if not result:
        return {"error": "User not found"}

    current = result[0] or []
    current.append(workout)

    db.execute(
        text("UPDATE users SET workouts = CAST(:workouts AS JSONB) WHERE username = :username"),
        {"workouts": json.dumps(current), "username": username}
    )
    db.commit()

    return {"message": "Workout saved", "total": len(current)}


@router.get("/saved-workouts")
def get_saved_workouts(username: str, db: Session = Depends(get_db)):
    result = db.execute(
        text("SELECT workouts FROM users WHERE username = :username"),
        {"username": username}
    ).fetchone()

    if not result:
        return {"error": "User not found"}

    return {"saved_workouts": result[0] or []}
