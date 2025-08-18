import sqlite3
from typing import List, Dict, Any, Optional


class Database:
    """A lightweight wrapper around SQLite for storing and retrieving MLBB Team Finder profiles."""

    def __init__(self, db_path: str = "mlbb_team_finder.db") -> None:
        # Using check_same_thread=False so that we can share the connection across telegram handler threads
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # access columns by name
        self._create_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------
    def _create_tables(self) -> None:
        # Simple one-table schema for MVP. Feel free to extend later.
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                telegram_id     INTEGER PRIMARY KEY,
                username        TEXT,
                rank            TEXT,
                role            TEXT,
                play_time       TEXT,
                updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # CRUD helpers
    # ------------------------------------------------------------------
    def upsert_profile(
        self,
        telegram_id: int,
        username: str,
        rank: str,
        role: str,
        play_time: str,
    ) -> None:
        """Insert or update a player profile."""
        self.conn.execute(
            """
            INSERT INTO profiles (telegram_id, username, rank, role, play_time)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username  = excluded.username,
                rank      = excluded.rank,
                role      = excluded.role,
                play_time = excluded.play_time,
                updated_at = CURRENT_TIMESTAMP;
            """,
            (telegram_id, username, rank, role, play_time),
        )
        self.conn.commit()

    def get_profile(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        cur = self.conn.execute(
            "SELECT * FROM profiles WHERE telegram_id = ?;", (telegram_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def find_matches(
        self,
        *,
        exclude_telegram_id: int,
        rank: Optional[str] = None,
        role: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return a list of player profiles matching the provided filters."""
        sql = "SELECT * FROM profiles WHERE telegram_id != ?"
        params: List[Any] = [exclude_telegram_id]
        if rank:
            sql += " AND rank = ?"
            params.append(rank)
        if role:
            sql += " AND role = ?"
            params.append(role)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        cur = self.conn.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


# Convenience singleton -------------------------------------------------------
_db_instance: Optional[Database] = None


def get_db(db_path: str = "mlbb_team_finder.db") -> Database:
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(db_path)
    return _db_instance