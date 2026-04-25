import os
import json
import pathlib
from sqlalchemy import text
from app.database.connection import engine

BASE_DIR = pathlib.Path(__file__).resolve().parents[2]

EXERCISES_FOLDER = BASE_DIR / "exercises"


def insert_muscle_relation(conn, exercise_id, muscle_name, muscle_type):
    """Insert or update a muscle, then relate it to an exercise."""

    muscle_result = conn.execute(
        text("""
             INSERT INTO muscles (name, group_name)
             VALUES (:name, :group_name) ON CONFLICT (name) DO
             UPDATE SET name = EXCLUDED.name
                 RETURNING id;
             """),
        {"name": muscle_name, "group_name": muscle_name}
    )

    muscle_id = muscle_result.fetchone()[0]

    conn.execute(
        text("""
             INSERT INTO exercise_muscles (exercise_id, muscle_id, muscle_type)
             VALUES (:exercise_id, :muscle_id, :muscle_type) ON CONFLICT (exercise_id, muscle_id) DO NOTHING;
             """),
        {
            "exercise_id": exercise_id,
            "muscle_id": muscle_id,
            "muscle_type": muscle_type
        }
    )


def import_exercises():
    """Import exercises and muscle relationships from JSON files."""

    with engine.connect() as conn:
        for file in os.listdir(EXERCISES_FOLDER):
            if not file.endswith(".json"):
                continue

            path = os.path.join(EXERCISES_FOLDER, file)

            with open(path, "r") as f:
                data = json.load(f)

            result = conn.execute(
                text("""
                     INSERT INTO exercises
                         (name, force, level, mechanic, equipment, category, instructions)
                     VALUES (:name, :force, :level, :mechanic, :equipment, :category, :instructions) RETURNING id;
                     """),
                {
                    "name": data.get("name"),
                    "force": data.get("force"),
                    "level": data.get("level"),
                    "mechanic": data.get("mechanic"),
                    "equipment": data.get("equipment"),
                    "category": data.get("category"),
                    "instructions": " ".join(data.get("instructions", []))
                }
            )

            exercise_id = result.fetchone()[0]

            for muscle in data.get("primaryMuscles", []):
                insert_muscle_relation(conn, exercise_id, muscle, "primary")

            for muscle in data.get("secondaryMuscles", []):
                insert_muscle_relation(conn, exercise_id, muscle, "secondary")

        conn.commit()

if __name__ == "__main__":
    import_exercises()
