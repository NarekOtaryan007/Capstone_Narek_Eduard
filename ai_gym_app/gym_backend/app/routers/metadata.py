from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database.connection import get_db

router = APIRouter()


@router.get("/muscles")
def get_muscles(db: Session = Depends(get_db)):

    query = """
    SELECT DISTINCT name
    FROM muscles
    ORDER BY name
    """

    result = db.execute(text(query))

    muscles = [row[0] for row in result.fetchall()]

    return {"muscles": muscles}


@router.get("/equipment")
def get_equipment(db: Session = Depends(get_db)):

    query = """
    SELECT DISTINCT equipment
    FROM exercises
    WHERE equipment IS NOT NULL
    ORDER BY equipment
    """

    result = db.execute(text(query))

    equipment = [row[0] for row in result.fetchall()]

    return {"equipment": equipment}


@router.get("/levels")
def get_levels(db: Session = Depends(get_db)):

    query = """
    SELECT DISTINCT level
    FROM exercises
    WHERE level IS NOT NULL
    ORDER BY level
    """

    result = db.execute(text(query))

    levels = [row[0] for row in result.fetchall()]

    return {"levels": levels}