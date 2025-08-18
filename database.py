import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


LOGGER = logging.getLogger(__name__)


DB_PATH = os.environ.get("MLBB_DB_PATH", os.path.join(os.getcwd(), "mlbb.db"))


def _get_connection() -> sqlite3.Connection:
    # Increase timeout to reduce 'database is locked' errors under concurrent access
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    try:
        # Enable WAL journal for better concurrent read/write behavior
        conn.execute("PRAGMA journal_mode=WAL")
        # Ensure SQLite waits if the database is busy
        conn.execute("PRAGMA busy_timeout=5000")
        # Reasonable durability while reducing writer stalls
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        # Best-effort pragmas; ignore if not supported in the environment
        pass
    conn.row_factory = sqlite3.Row
    return conn


def check_database() -> None:
    """Ensure all required tables and indexes exist."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        # users table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                telegram_username TEXT,
                nickname TEXT,
                winrate INTEGER,
                line TEXT,
                rank TEXT,
                mythic_rank TEXT,
                goal TEXT,
                about TEXT,
                photo_ids TEXT, -- JSON array of file_ids
                last_active_timestamp INTEGER
            )
            """
        )

        # likes table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS likes (
                liker_id INTEGER NOT NULL,
                liked_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                UNIQUE(liker_id, liked_id)
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_likes_liked ON likes(liked_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_likes_liker ON likes(liker_id)")

        # views table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS views (
                viewer_id INTEGER NOT NULL,
                viewed_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_views_viewed ON views(viewed_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_views_viewer ON views(viewer_id)")

        # Performance indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active_timestamp)")

        conn.commit()
    finally:
        conn.close()


@dataclass
class UserProfile:
    user_id: int
    telegram_username: Optional[str]
    nickname: str
    winrate: int
    line: str
    rank: str
    mythic_rank: Optional[str]
    goal: str
    about: str
    photo_ids: List[str]
    last_active_timestamp: int

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return data


def _row_to_profile(row: sqlite3.Row) -> UserProfile:
    photo_ids: List[str]
    try:
        photo_ids = json.loads(row["photo_ids"]) if row["photo_ids"] else []
    except Exception:
        photo_ids = []
    return UserProfile(
        user_id=row["user_id"],
        telegram_username=row["telegram_username"],
        nickname=row["nickname"] or "",
        winrate=int(row["winrate"]) if row["winrate"] is not None else 0,
        line=row["line"] or "",
        rank=row["rank"] or "",
        mythic_rank=row["mythic_rank"],
        goal=row["goal"] or "",
        about=row["about"] or "",
        photo_ids=photo_ids,
        last_active_timestamp=int(row["last_active_timestamp"]) if row["last_active_timestamp"] else 0,
    )


def get_user_by_id(user_id: int) -> Optional[UserProfile]:
    check_database()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return None
        return _row_to_profile(row)
    finally:
        conn.close()


def create_user_profile(data: Dict[str, Any]) -> bool:
    """
    Create or update a user profile.
    Expects keys: user_id (required). Others are optional and will preserve existing values if missing.
    """
    if "user_id" not in data:
        return False

    check_database()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE user_id = ?", (data["user_id"],))
        row = cur.fetchone()

        if row:
            # Merge with existing
            existing = _row_to_profile(row).to_dict()
            merged: Dict[str, Any] = {**existing, **data}
        else:
            # Defaults for new profile
            merged = {
                "user_id": data["user_id"],
                "telegram_username": data.get("telegram_username"),
                "nickname": data.get("nickname", ""),
                "winrate": int(data.get("winrate", 0)),
                "line": data.get("line", "Везде"),
                "rank": data.get("rank", ""),
                "mythic_rank": data.get("mythic_rank"),
                "goal": data.get("goal", ""),
                "about": data.get("about", ""),
                "photo_ids": data.get("photo_ids", []),
                "last_active_timestamp": int(data.get("last_active_timestamp", int(time.time()))),
            }

        # Normalize types
        merged["winrate"] = int(merged.get("winrate") or 0)
        merged["last_active_timestamp"] = int(merged.get("last_active_timestamp") or int(time.time()))
        # Store photo_ids as JSON
        photo_json = json.dumps(merged.get("photo_ids") or [])

        cur.execute(
            """
            INSERT INTO users (
                user_id, telegram_username, nickname, winrate, line, rank, mythic_rank,
                goal, about, photo_ids, last_active_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                telegram_username=excluded.telegram_username,
                nickname=excluded.nickname,
                winrate=excluded.winrate,
                line=excluded.line,
                rank=excluded.rank,
                mythic_rank=excluded.mythic_rank,
                goal=excluded.goal,
                about=excluded.about,
                photo_ids=excluded.photo_ids,
                last_active_timestamp=excluded.last_active_timestamp
            """,
            (
                merged["user_id"],
                merged.get("telegram_username"),
                merged.get("nickname", ""),
                int(merged.get("winrate", 0)),
                merged.get("line", ""),
                merged.get("rank", ""),
                merged.get("mythic_rank"),
                merged.get("goal", ""),
                merged.get("about", ""),
                photo_json,
                int(merged.get("last_active_timestamp", int(time.time()))),
            ),
        )
        conn.commit()
        return True
    except Exception:
        LOGGER.exception("create_user_profile failed")
        return False
    finally:
        conn.close()


def update_user_activity(user_id: int) -> None:
    check_database()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET last_active_timestamp = ? WHERE user_id = ?",
            (int(time.time()), user_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_active_users(exclude_user_id: Optional[int] = None, max_age_seconds: Optional[int] = None) -> List[UserProfile]:
    check_database()
    conn = _get_connection()
    now_ts = int(time.time())
    try:
        cur = conn.cursor()
        params: List[Any] = []
        where_clauses: List[str] = []
        if exclude_user_id is not None:
            where_clauses.append("user_id <> ?")
            params.append(exclude_user_id)
        if max_age_seconds is not None:
            where_clauses.append("last_active_timestamp >= ?")
            params.append(now_ts - max_age_seconds)
        where = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        cur.execute(f"SELECT * FROM users{where} ORDER BY last_active_timestamp DESC", params)
        rows = cur.fetchall()
        return [_row_to_profile(r) for r in rows]
    finally:
        conn.close()


def add_profile_view(viewer_id: int, viewed_id: int) -> None:
    if viewer_id == viewed_id:
        return
    check_database()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO views (viewer_id, viewed_id, created_at) VALUES (?, ?, ?)",
            (viewer_id, viewed_id, int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def add_like(liker_id: int, liked_id: int) -> None:
    if liker_id == liked_id:
        return
    check_database()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO likes (liker_id, liked_id, created_at) VALUES (?, ?, ?)",
            (liker_id, liked_id, int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def has_like(from_user_id: int, to_user_id: int) -> bool:
    check_database()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM likes WHERE liker_id = ? AND liked_id = ?",
            (from_user_id, to_user_id),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def get_users_who_liked_me(user_id: int) -> List[Dict[str, Any]]:
    check_database()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT u.* FROM likes l
            JOIN users u ON u.user_id = l.liker_id
            WHERE l.liked_id = ?
            ORDER BY l.created_at DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()
        return [_row_to_profile(r).to_dict() for r in rows]
    finally:
        conn.close()


def get_user_stats(user_id: int) -> Dict[str, int]:
    check_database()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        # Views of my profile
        cur.execute("SELECT COUNT(*) FROM views WHERE viewed_id = ?", (user_id,))
        views = int(cur.fetchone()[0])

        # Likes received
        cur.execute("SELECT COUNT(*) FROM likes WHERE liked_id = ?", (user_id,))
        likes_received = int(cur.fetchone()[0])

        # Likes given
        cur.execute("SELECT COUNT(*) FROM likes WHERE liker_id = ?", (user_id,))
        likes_given = int(cur.fetchone()[0])

        # Mutual likes (distinct partners)
        cur.execute(
            """
            SELECT COUNT(DISTINCT l1.liked_id)
            FROM likes l1
            JOIN likes l2 ON l1.liked_id = l2.liker_id AND l2.liked_id = l1.liker_id
            WHERE l1.liker_id = ?
            """,
            (user_id,),
        )
        mutual_likes = int(cur.fetchone()[0])

        return {
            "views": views,
            "likes_received": likes_received,
            "likes_given": likes_given,
            "mutual_likes": mutual_likes,
        }
    finally:
        conn.close()


def delete_user(user_id: int) -> None:
    check_database()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM likes WHERE liker_id = ? OR liked_id = ?", (user_id, user_id))
        cur.execute("DELETE FROM views WHERE viewer_id = ? OR viewed_id = ?", (user_id, user_id))
        conn.commit()
    finally:
        conn.close()

