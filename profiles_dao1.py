# filename: profiles_dao1.py
# ─────────────────────────────────────────────────────────────────────────────
# DAO per SQLite con supporto a 'zodiac_sign' su profiles e profile_id su messages
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import datetime
from typing import Any, Iterable, List, Optional, Sequence, Tuple, TypedDict

DB_PATH = os.getenv("DATABASE_PATH", "db/GrandaIncontri.db")

def _utc_now_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

class Profile(TypedDict, total=False):
    id: int
    first_name: str
    last_name: str
    gender: str
    birth_year: int
    city: str
    occupation: str
    eyes_color: str
    hair_color: str
    height_cm: int
    smoker: int
    bio: str
    is_active: int
    created_at: str
    weight_kg: int
    marital_status: str
    zodiac_sign: str            # <<< aggiunto

class Message(TypedDict, total=False):
    id: int
    sender_name: str
    sender_phone: str
    sender_email: str
    sender_job: str
    sender_age: int
    sender_city: str
    sender_message: str
    profile_id: Optional[int]
    created_at: str

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    with closing(conn.cursor()) as cur:
        cur.execute("PRAGMA foreign_keys = ON;")
    return conn

def _rows_to_dicts(rows: Iterable[sqlite3.Row]) -> List[dict]:
    return [dict(r) for r in rows]

def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    return dict(row) if row is not None else None

# ───────────── PROFILES ─────────────
def get_all_profiles() -> List[Profile]:
    sql = """
        SELECT *
        FROM profiles
        ORDER BY
          CASE WHEN created_at IS NULL OR created_at = '' THEN 1 ELSE 0 END,
          created_at DESC,
          id DESC
    """
    with closing(_conn()) as conn, closing(conn.cursor()) as cur:
        cur.execute(sql)
        return _rows_to_dicts(cur.fetchall())  # type: ignore[return-value]

def get_profile_by_id(profile_id: int) -> Optional[Profile]:
    sql = "SELECT * FROM profiles WHERE id = ?"
    with closing(_conn()) as conn, closing(conn.cursor()) as cur:
        cur.execute(sql, (profile_id,))
        return _row_to_dict(cur.fetchone())  # type: ignore[return-value]

def insert_profile(
    first_name: str,
    last_name: str,
    gender: str,
    birth_year: Optional[int],
    city: str,
    occupation: str,
    eyes_color: str,
    hair_color: str,
    height_cm: Optional[int],
    smoker: Optional[int],
    bio: str,
    is_active: int,
    weight_kg: Optional[int] = None,
    marital_status: Optional[str] = None,
    zodiac_sign: Optional[str] = None,      # <<< aggiunto
    created_at: Optional[str] = None,
) -> int:
    created_at = created_at or _utc_now_str()
    sql = """
        INSERT INTO profiles (
          first_name, last_name, gender, birth_year, city, occupation,
          eyes_color, hair_color, height_cm, smoker, bio, is_active,
          created_at, weight_kg, marital_status, zodiac_sign
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params: Tuple[Any, ...] = (
        first_name, last_name, gender, birth_year, city, occupation,
        eyes_color, hair_color, height_cm, smoker, bio, is_active,
        created_at, weight_kg, marital_status, zodiac_sign
    )
    with closing(_conn()) as conn, closing(conn.cursor()) as cur:
        try:
            cur.execute(sql, params)
            conn.commit()
            return int(cur.lastrowid)
        except Exception:
            conn.rollback()
            raise

def update_profile(
    profile_id: int,
    first_name: str,
    last_name: str,
    gender: str,
    birth_year: Optional[int],
    city: str,
    occupation: str,
    eyes_color: str,
    hair_color: str,
    height_cm: Optional[int],
    smoker: Optional[int],
    bio: str,
    is_active: int,
    weight_kg: Optional[int] = None,
    marital_status: Optional[str] = None,
    zodiac_sign: Optional[str] = None,      # <<< aggiunto
) -> None:
    sql = """
        UPDATE profiles SET
          first_name = ?, last_name = ?, gender = ?, birth_year = ?, city = ?, occupation = ?,
          eyes_color = ?, hair_color = ?, height_cm = ?, smoker = ?, bio = ?, is_active = ?,
          weight_kg = ?, marital_status = ?, zodiac_sign = ?
        WHERE id = ?
    """
    params: Tuple[Any, ...] = (
        first_name, last_name, gender, birth_year, city, occupation,
        eyes_color, hair_color, height_cm, smoker, bio, is_active,
        weight_kg, marital_status, zodiac_sign, profile_id
    )
    with closing(_conn()) as conn, closing(conn.cursor()) as cur:
        try:
            cur.execute(sql, params)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

def delete_profile(profile_id: int) -> None:
    sql = "DELETE FROM profiles WHERE id = ?"
    with closing(_conn()) as conn, closing(conn.cursor()) as cur:
        try:
            cur.execute(sql, (profile_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise

# ───────────── MESSAGES ─────────────
def insert_message(
    sender_name: str,
    sender_phone: str,
    sender_email: str,
    sender_job: str,
    sender_age: Optional[int],
    sender_city: str,
    sender_message: str,
    profile_id: Optional[int] = None,
) -> int:
    created_at = _utc_now_str()

    if profile_id is not None:
        sql = """
            INSERT INTO messages (
              sender_name, sender_phone, sender_email, sender_job,
              sender_age, sender_city, sender_message, profile_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params: Sequence[Any] = (
            sender_name, sender_phone, sender_email, sender_job,
            sender_age, sender_city, sender_message, profile_id, created_at
        )
    else:
        sql = """
            INSERT INTO messages (
              sender_name, sender_phone, sender_email, sender_job,
              sender_age, sender_city, sender_message, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            sender_name, sender_phone, sender_email, sender_job,
            sender_age, sender_city, sender_message, created_at
        )

    with closing(_conn()) as conn, closing(conn.cursor()) as cur:
        try:
            cur.execute(sql, params)
            conn.commit()
            print(f">>> Inserito messaggio: {sender_name} <{sender_email}> ({sender_city})")
            return int(cur.lastrowid)
        except Exception:
            conn.rollback()
            raise
