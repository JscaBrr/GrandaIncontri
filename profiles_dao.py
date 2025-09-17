# filename: profiles_dao.py

# ─────────────────────────────────────────────────────────────────────────────
# Data Access Object (DAO) per profiles e messages su SQLite.
# - Connessioni sicure con context manager
# - Tipi e docstring
# - Utility per conversione Row → dict
# - Timestamp in UTC ISO-like
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import datetime
from typing import Any, Iterable, List, Optional, Sequence, Tuple, TypedDict

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAZIONE DI BASE
# ─────────────────────────────────────────────────────────────────────────────
DB_PATH = os.getenv("DATABASE_PATH", "db/GrandaIncontri.db")

def _utc_now_str() -> str:
    """Ritorna l'orario UTC in formato 'YYYY-MM-DD HH:MM:SS'."""
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

# ─────────────────────────────────────────────────────────────────────────────
# TIPI
# ─────────────────────────────────────────────────────────────────────────────
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
    smoker: int            # 0/1
    bio: str
    is_active: int         # 0/1
    created_at: str        # "YYYY-MM-DD HH:MM:SS"
    weight_kg: int         # opzionale
    marital_status: str    # es. "Celibe/Nubile", "Sposato/a", ...

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

# ─────────────────────────────────────────────────────────────────────────────
# CONNESSIONE E UTILITY
# ─────────────────────────────────────────────────────────────────────────────
def _conn() -> sqlite3.Connection:
    """Crea una connessione a SQLite con row_factory e FK ON."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    with closing(conn.cursor()) as cur:
        cur.execute("PRAGMA foreign_keys = ON;")
    return conn

def _rows_to_dicts(rows: Iterable[sqlite3.Row]) -> List[dict]:
    return [dict(r) for r in rows]

def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    return dict(row) if row is not None else None

# ─────────────────────────────────────────────────────────────────────────────
# CRUD: PROFILES
# ─────────────────────────────────────────────────────────────────────────────
def get_all_profiles() -> List[Profile]:
    """
    Ritorna tutti i profili ordinati per created_at desc (NULL/'' in coda), poi id desc.
    """
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
    created_at: Optional[str] = None,
) -> int:
    """
    Crea un profilo e ritorna l'id creato.
    - created_at: se None → now UTC.
    - marital_status può essere testo in italiano (es. 'Sposato/a').
    """
    created_at = created_at or _utc_now_str()
    sql = """
        INSERT INTO profiles (
          first_name, last_name, gender, birth_year, city, occupation,
          eyes_color, hair_color, height_cm, smoker, bio, is_active,
          created_at, weight_kg, marital_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params: Tuple[Any, ...] = (
        first_name, last_name, gender, birth_year, city, occupation,
        eyes_color, hair_color, height_cm, smoker, bio, is_active,
        created_at, weight_kg, marital_status
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
) -> None:
    """
    Aggiorna un profilo esistente.
    """
    sql = """
        UPDATE profiles SET
          first_name = ?, last_name = ?, gender = ?, birth_year = ?, city = ?, occupation = ?,
          eyes_color = ?, hair_color = ?, height_cm = ?, smoker = ?, bio = ?, is_active = ?,
          weight_kg = ?, marital_status = ?
        WHERE id = ?
    """
    params: Tuple[Any, ...] = (
        first_name, last_name, gender, birth_year, city, occupation,
        eyes_color, hair_color, height_cm, smoker, bio, is_active,
        weight_kg, marital_status, profile_id
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

# ─────────────────────────────────────────────────────────────────────────────
# INSERT: MESSAGES
# ─────────────────────────────────────────────────────────────────────────────
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
    """
    Salva un messaggio nella tabella 'messages'.
    Ritorna l'id del messaggio creato.
    """
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
