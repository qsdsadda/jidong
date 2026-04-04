# database.py - 数据库初始化与操作函数

import sqlite3
import json
import uuid
from datetime import datetime, date, timedelta
from contextlib import contextmanager

DB_PATH = "jidong.db"


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            nickname TEXT,
            age_range TEXT,
            gender TEXT,
            height REAL,
            weight REAL,
            work_type TEXT,
            sitting_hours TEXT,
            body_issues TEXT,
            exercise_history TEXT,
            goals TEXT,
            available_times TEXT,
            time_per_session TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS prescriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            version INTEGER DEFAULT 1,
            trigger_type TEXT,
            prescription_json TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            checkin_date DATE,
            completion_rate REAL,
            feeling_score INTEGER,
            mood_score INTEGER,
            completed_count INTEGER,
            total_count INTEGER,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS symptom_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            symptom TEXT,
            prescription_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)


def create_user(data: dict) -> str:
    user_id = str(uuid.uuid4())
    try:
        with get_db() as conn:
            conn.execute("""
                INSERT INTO users (user_id, nickname, age_range, gender, height, weight,
                    work_type, sitting_hours, body_issues, exercise_history,
                    goals, available_times, time_per_session)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                user_id,
                data.get("nickname", "用户"),
                data.get("age_range", ""),
                data.get("gender", ""),
                float(data.get("height", 0) or 0),
                float(data.get("weight", 0) or 0),
                data.get("work_type", ""),
                data.get("sitting_hours", ""),
                json.dumps(data.get("body_issues", []), ensure_ascii=False),
                data.get("exercise_history", ""),
                json.dumps(data.get("goals", []), ensure_ascii=False),
                json.dumps(data.get("available_times", []), ensure_ascii=False),
                data.get("time_per_session", ""),
            ))
        return user_id
    except Exception as e:
        print(f"[DB] create_user error: {e}")
        return None


def get_user(user_id: str) -> dict:
    try:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
            if row:
                d = dict(row)
                for f in ["body_issues", "goals", "available_times"]:
                    try:
                        d[f] = json.loads(d[f] or "[]")
                    except Exception:
                        d[f] = []
                return d
    except Exception as e:
        print(f"[DB] get_user error: {e}")
    return None


def save_prescription(user_id: str, prescription: dict, trigger_type: str = "initial") -> int:
    try:
        with get_db() as conn:
            # deactivate old
            conn.execute("UPDATE prescriptions SET is_active=0 WHERE user_id=?", (user_id,))
            version_row = conn.execute(
                "SELECT COALESCE(MAX(version),0)+1 as v FROM prescriptions WHERE user_id=?", (user_id,)
            ).fetchone()
            version = version_row["v"] if version_row else 1
            cur = conn.execute("""
                INSERT INTO prescriptions (user_id, version, trigger_type, prescription_json, is_active)
                VALUES (?,?,?,?,1)
            """, (user_id, version, trigger_type, json.dumps(prescription, ensure_ascii=False)))
            return cur.lastrowid
    except Exception as e:
        print(f"[DB] save_prescription error: {e}")
        return None


def get_active_prescription(user_id: str) -> dict:
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM prescriptions WHERE user_id=? AND is_active=1 ORDER BY created_at DESC LIMIT 1",
                (user_id,)
            ).fetchone()
            if row:
                d = dict(row)
                d["prescription"] = json.loads(d["prescription_json"] or "{}")
                return d
    except Exception as e:
        print(f"[DB] get_active_prescription error: {e}")
    return None


def get_prescription_history(user_id: str) -> list:
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT id, version, trigger_type, created_at FROM prescriptions WHERE user_id=? ORDER BY version DESC",
                (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        print(f"[DB] get_prescription_history error: {e}")
    return []


def save_checkin(user_id: str, data: dict) -> bool:
    try:
        today = date.today().isoformat()
        with get_db() as conn:
            existing = conn.execute(
                "SELECT id FROM checkins WHERE user_id=? AND checkin_date=?", (user_id, today)
            ).fetchone()
            if existing:
                conn.execute("""
                    UPDATE checkins SET completion_rate=?, feeling_score=?, mood_score=?,
                        completed_count=?, total_count=?, note=?
                    WHERE user_id=? AND checkin_date=?
                """, (
                    data.get("completion_rate", 0),
                    data.get("feeling_score", 3),
                    data.get("mood_score", 2),
                    data.get("completed_count", 0),
                    data.get("total_count", 0),
                    data.get("note", ""),
                    user_id, today
                ))
            else:
                conn.execute("""
                    INSERT INTO checkins (user_id, checkin_date, completion_rate, feeling_score,
                        mood_score, completed_count, total_count, note)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (
                    user_id, today,
                    data.get("completion_rate", 0),
                    data.get("feeling_score", 3),
                    data.get("mood_score", 2),
                    data.get("completed_count", 0),
                    data.get("total_count", 0),
                    data.get("note", ""),
                ))
        return True
    except Exception as e:
        print(f"[DB] save_checkin error: {e}")
        return False


def get_today_checkin(user_id: str) -> dict:
    try:
        today = date.today().isoformat()
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM checkins WHERE user_id=? AND checkin_date=?", (user_id, today)
            ).fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"[DB] get_today_checkin error: {e}")
    return None


def get_checkin_stats(user_id: str, days: int = 14) -> dict:
    try:
        start = (date.today() - timedelta(days=days)).isoformat()
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM checkins WHERE user_id=? AND checkin_date>=? ORDER BY checkin_date",
                (user_id, start)
            ).fetchall()
            records = [dict(r) for r in rows]

        # streak
        streak = 0
        d = date.today()
        dates_set = {r["checkin_date"] for r in records}
        while d.isoformat() in dates_set:
            streak += 1
            d -= timedelta(days=1)

        # this week
        week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
        week_records = [r for r in records if r["checkin_date"] >= week_start]
        week_rate = (sum(r["completion_rate"] for r in week_records) / len(week_records)
                     if week_records else 0)

        return {
            "records": records,
            "streak": streak,
            "week_days": len(week_records),
            "week_rate": round(week_rate * 100, 1),
            "avg_feeling": round(
                sum(r["feeling_score"] for r in week_records) / len(week_records), 1
            ) if week_records else 0,
        }
    except Exception as e:
        print(f"[DB] get_checkin_stats error: {e}")
        return {"records": [], "streak": 0, "week_days": 0, "week_rate": 0, "avg_feeling": 0}


def save_symptom_log(user_id: str, symptom: str, prescription: dict) -> bool:
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO symptom_logs (user_id, symptom, prescription_json) VALUES (?,?,?)",
                (user_id, symptom, json.dumps(prescription, ensure_ascii=False))
            )
        return True
    except Exception as e:
        print(f"[DB] save_symptom_log error: {e}")
        return False


def get_all_active_users() -> list:
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT DISTINCT user_id FROM checkins WHERE checkin_date >= ?",
                ((date.today() - timedelta(days=30)).isoformat(),)
            ).fetchall()
            return [r["user_id"] for r in rows]
    except Exception as e:
        print(f"[DB] get_all_active_users error: {e}")
    return []
