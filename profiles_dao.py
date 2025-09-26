# filename: profiles_dao.py
from __future__ import annotations

import os
from contextlib import closing
from datetime import datetime
from typing import Any, Iterable, List, Optional, Sequence, Tuple, TypedDict

import psycopg2
from psycopg2.extras import RealDictCursor

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAZIONE DI BASE
# ─────────────────────────────────────────────────────────────────────────────
# Prende la connessione da DATABASE_URL (es. postgresql://user:pass@host/dbname)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL non impostata. Configurala nelle Environment Variables su Render.")

# Render in genere richiede SSL; se la tua URL non lo specifica già, abilitalo così:
if "sslmode=" not in DATABASE_URL:
    if "?" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL + "&sslmode=require"
    else:
        DATABASE_URL = DATABASE_URL + "?sslmode=require"

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
    weight_kg: int
    marital_status: str
    zodiac_sign: str    

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
def _conn():
    """
    Crea una connessione a PostgreSQL con RealDictCursor così le righe sono dict.
    Usa context manager (closing) nei punti d’uso.
    """
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def _rows_to_dicts(rows: Iterable[dict]) -> List[dict]:
    return [dict(r) for r in rows]

def _row_to_dict(row: Optional[dict]) -> Optional[dict]:
    return dict(row) if row is not None else None

# ─────────────────────────────────────────────────────────────────────────────
# CRUD: PROFILES
# ─────────────────────────────────────────────────────────────────────────────
def get_all_profiles() -> List[Profile]:
    """
    Ritorna tutti i profili ordinati per created_at desc (NULL/'' in coda), poi id desc.
    La CASE di SQLite è stata adattata per Postgres.
    """
    sql = """
        SELECT *
        FROM profiles
        ORDER BY
          CASE WHEN (created_at IS NULL OR created_at = '') THEN 1 ELSE 0 END,
          created_at DESC NULLS LAST,
          id DESC
    """
    with closing(_conn()) as conn, closing(conn.cursor()) as cur:
        cur.execute(sql)
        return _rows_to_dicts(cur.fetchall())  # type: ignore[return-value]

def get_profile_by_id(profile_id: int) -> Optional[Profile]:
    sql = "SELECT * FROM profiles WHERE id = %s"
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
    zodiac_sign: Optional[str] = None,     # <-- NUOVO
    created_at: Optional[str] = None,      # <-- resta ultimo in SQL
) -> int:
    """
    Crea un profilo e ritorna l'id creato.
    - created_at: se None → now UTC.
    """
    created_at = created_at or _utc_now_str()
    sql = """
        INSERT INTO profiles (
          first_name, last_name, gender, birth_year, city, occupation,
          eyes_color, hair_color, height_cm, smoker, bio, is_active,
          weight_kg, marital_status, zodiac_sign, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    params: Tuple[Any, ...] = (
        first_name, last_name, gender, birth_year, city, occupation,
        eyes_color, hair_color, height_cm, smoker, bio, is_active,
        weight_kg, marital_status, zodiac_sign, created_at
    )
    with closing(_conn()) as conn, closing(conn.cursor()) as cur:
        cur.execute(sql, params)
        new_id = cur.fetchone()["id"]  # type: ignore[index]
        conn.commit()
        return int(new_id)

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
    zodiac_sign: Optional[str] = None,   # <-- NUOVO
) -> None:
    sql = """
        UPDATE profiles SET
          first_name = %s, last_name = %s, gender = %s, birth_year = %s, city = %s, occupation = %s,
          eyes_color = %s, hair_color = %s, height_cm = %s, smoker = %s, bio = %s, is_active = %s,
          weight_kg = %s, marital_status = %s, zodiac_sign = %s
        WHERE id = %s
    """
    params: Tuple[Any, ...] = (
        first_name, last_name, gender, birth_year, city, occupation,
        eyes_color, hair_color, height_cm, smoker, bio, is_active,
        weight_kg, marital_status, zodiac_sign, profile_id
    )
    with closing(_conn()) as conn, closing(conn.cursor()) as cur:
        cur.execute(sql, params)
        conn.commit()

def delete_profile(profile_id: int) -> None:
    with closing(_conn()) as conn, closing(conn.cursor()) as cur:
        # stacca i messaggi dal profilo, così non blocca la FK
        cur.execute("UPDATE messages SET profile_id = NULL WHERE profile_id = %s", (profile_id,))
        # poi elimina il profilo
        cur.execute("DELETE FROM profiles WHERE id = %s", (profile_id,))
        conn.commit()

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
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
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
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        params = (
            sender_name, sender_phone, sender_email, sender_job,
            sender_age, sender_city, sender_message, created_at
        )

    with closing(_conn()) as conn, closing(conn.cursor()) as cur:
        cur.execute(sql, params)
        new_id = cur.fetchone()["id"]  # type: ignore[index]
        conn.commit()
        print(f">>> Inserito messaggio: {sender_name} <{sender_email}> ({sender_city})")
        return int(new_id)
