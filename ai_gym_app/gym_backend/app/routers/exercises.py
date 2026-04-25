from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional

from app.database.connection import get_db

router = APIRouter()


@router.get("/exercises")
def get_exercises(
    muscle: Optional[str] = Query(None),
    equipment: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    limit: int = Query(20),
    offset: int = Query(0),
    db: Session = Depends(get_db)
):

    query = """
    SELECT DISTINCT e.*
    FROM exercises e
    LEFT JOIN exercise_muscles em ON e.id = em.exercise_id
    LEFT JOIN muscles m ON em.muscle_id = m.id
    WHERE 1=1
    """

    params = {}

    if muscle:
        query += " AND m.name = :muscle"
        params["muscle"] = muscle

    if equipment:
        query += " AND e.equipment = :equipment"
        params["equipment"] = equipment

    if level:
        query += " AND e.level = :level"
        params["level"] = level

    query += " LIMIT :limit OFFSET :offset"

    params["limit"] = limit
    params["offset"] = offset

    result = db.execute(text(query), params)
    rows = result.fetchall()

    exercises = [dict(row._mapping) for row in rows]

    return {"exercises": exercises}


@router.get("/exercises/{exercise_id}")
def get_exercise(
    exercise_id: int,
    db: Session = Depends(get_db)
):

    query = """
    SELECT *
    FROM exercises
    WHERE id = :exercise_id
    """

    result = db.execute(text(query), {"exercise_id": exercise_id})
    row = result.fetchone()

    if not row:
        return {"error": "Exercise not found"}

    return dict(row._mapping)


@router.get("/exercises/search")
def search_exercises(
    name: str,
    db: Session = Depends(get_db)
):

    query = """
    SELECT *
    FROM exercises
    WHERE LOWER(name) LIKE LOWER(:name)
    LIMIT 20
    """

    result = db.execute(
        text(query),
        {"name": f"%{name}%"}
    )

    rows = result.fetchall()

    exercises = [dict(row._mapping) for row in rows]

    return {"exercises": exercises}