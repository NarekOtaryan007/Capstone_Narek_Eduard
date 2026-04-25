from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import random
import json
import bcrypt

from app.database.connection import get_db

router = APIRouter()


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify(password: str, stored: str) -> bool:
    if stored.startswith("$2b$") or stored.startswith("$2a$"):
        return bcrypt.checkpw(password.encode(), stored.encode())
    return password == stored


@router.post("/register")
def register(user: dict, db: Session = Depends(get_db)):
    username = user.get("username")

    existing = db.execute(
        text("SELECT id FROM users WHERE username = :username"),
        {"username": username}
    ).fetchone()

    if existing:
        return {"error": "User already exists"}

    db.execute(
        text("""
            INSERT INTO users (username, password, email, gym_id, phone, workouts)
            VALUES (:username, :password, :email, :gym_id, :phone, '[]'::jsonb)
        """),
        {
            "username": username,
            "password": _hash(user.get("password", "")),
            "email": user.get("email"),
            "gym_id": user.get("gymId"),
            "phone": user.get("phone"),
        }
    )
    db.commit()

    return {"message": "User registered successfully"}


@router.post("/login")
def login(data: dict, db: Session = Depends(get_db)):
    result = db.execute(
        text("SELECT id, password FROM users WHERE username = :username"),
        {"username": data.get("username")}
    ).fetchone()

    if result and _verify(data.get("password", ""), result[1]):
        return {"message": "Login successful"}

    return {"error": "Invalid username or password"}


@router.post("/forgot-password")
def forgot_password(data: dict, db: Session = Depends(get_db)):
    result = db.execute(
        text("SELECT id FROM users WHERE username = :username AND email = :email"),
        {"username": data.get("username"), "email": data.get("email")}
    ).fetchone()

    if not result:
        return {"error": "User not found"}

    code = str(random.randint(100000, 999999))

    db.execute(
        text("UPDATE users SET reset_code = :code WHERE username = :username"),
        {"code": code, "username": data.get("username")}
    )
    db.commit()

    return {"message": "Code sent", "code": code}


@router.post("/verify-code")
def verify_code(data: dict, db: Session = Depends(get_db)):
    result = db.execute(
        text("SELECT id FROM users WHERE username = :username AND reset_code = :code"),
        {"username": data.get("username"), "code": data.get("code")}
    ).fetchone()

    if result:
        return {"message": "Code verified"}

    return {"error": "Invalid code"}


@router.post("/reset-password")
def reset_password(data: dict, db: Session = Depends(get_db)):
    username = data.get("username")

    existing = db.execute(
        text("SELECT id FROM users WHERE username = :username"),
        {"username": username}
    ).fetchone()

    if not existing:
        return {"error": "User not found"}

    db.execute(
        text("UPDATE users SET password = :password, reset_code = NULL WHERE username = :username"),
        {"password": _hash(data.get("password", "")), "username": username}
    )
    db.commit()

    return {"message": "Password updated"}


@router.get("/profile")
def get_profile(username: str, db: Session = Depends(get_db)):
    result = db.execute(
        text("SELECT * FROM users WHERE username = :username"),
        {"username": username}
    ).fetchone()

    if not result:
        return {"error": "User not found"}

    user = dict(result._mapping)

    user["gymId"] = user.pop("gym_id", None)

    user.pop("id", None)
    user.pop("password", None)
    user.pop("reset_code", None)

    if user.get("workouts") is None:
        user["workouts"] = []

    return {"profile": user}


@router.post("/update-profile")
def update_profile(data: dict, db: Session = Depends(get_db)):
    username = data.get("username")

    existing = db.execute(
        text("SELECT id FROM users WHERE username = :username"),
        {"username": username}
    ).fetchone()

    if not existing:
        return {"error": "User not found"}

    set_parts = []
    params = {"username": username}

    simple_fields = ["email", "phone", "dob", "height", "weight", "level", "level_other", "injuries_other"]
    for field in simple_fields:
        if field in data:
            set_parts.append(f"{field} = :{field}")
            params[field] = str(data[field]) if data[field] is not None else None

    if "password" in data and data["password"]:
        set_parts.append("password = :password")
        params["password"] = _hash(data["password"])

    if "plan" in data:
        set_parts.append("plan = CAST(:plan AS JSONB)")
        params["plan"] = json.dumps(data["plan"])

    if "workouts" in data:
        set_parts.append("workouts = CAST(:workouts AS JSONB)")
        params["workouts"] = json.dumps(data["workouts"])

    if not set_parts:
        return {"message": "Nothing to update"}

    db.execute(
        text(f"UPDATE users SET {', '.join(set_parts)} WHERE username = :username"),
        params
    )
    db.commit()

    return {"message": "Profile updated"}
