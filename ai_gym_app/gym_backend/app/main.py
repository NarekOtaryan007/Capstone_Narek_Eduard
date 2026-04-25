from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
import os

from app.routers import exercises, workouts, metadata, saved_workouts, auth
from app.database.connection import engine

app = FastAPI(title="AI Gym App API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def create_tables():
    with engine.connect() as conn:
        # If the table exists with wrong schema (missing 'password' column), drop and recreate
        has_password_col = conn.execute(text("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'password'
        """)).fetchone()[0]

        if not has_password_col:
            conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
            conn.execute(text("""
                CREATE TABLE users (
                    id             SERIAL PRIMARY KEY,
                    username       TEXT UNIQUE NOT NULL,
                    password       TEXT NOT NULL,
                    email          TEXT NOT NULL,
                    gym_id         TEXT,
                    phone          TEXT,
                    dob            TEXT,
                    height         TEXT,
                    weight         TEXT,
                    level          TEXT,
                    level_other    TEXT,
                    injuries_other TEXT,
                    plan           JSONB DEFAULT NULL,
                    workouts       JSONB DEFAULT '[]',
                    reset_code     TEXT
                )
            """))
            conn.commit()


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES_PATH = os.path.join(BASE_DIR, "images")

if os.path.isdir(IMAGES_PATH):
    app.mount("/images", StaticFiles(directory=IMAGES_PATH), name="images")


@app.get("/")
def root():
    return {"message": "AI Gym API is running"}


app.include_router(auth.router)
app.include_router(exercises.router)
app.include_router(workouts.router)
app.include_router(metadata.router)
app.include_router(saved_workouts.router)
