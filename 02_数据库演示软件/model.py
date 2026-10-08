"""Local SQLite model for the database coursework desktop demonstration.

The shipped database is an anonymous, synthetic example.  All writes go to a
separate per-user copy; this module never contacts the WeChat CloudBase app.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import re
import sqlite3
import sys
import tempfile
import threading
import time
import uuid


TABLES = (
    "users", "books", "chapters", "questions", "answer_events",
    "user_question_progress",
)
SAMPLE_QUESTION_ID = "660s1_1_1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rows(cursor: sqlite3.Cursor) -> list[dict]:
    return [dict(row) for row in cursor.fetchall()]


@contextmanager
def _connect(path: Path):
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _resource_location(resource_dir: str | Path | None) -> Path:
    if resource_dir is not None:
        candidates = [Path(resource_dir)]
    else:
        candidates = []
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS))
        candidates.extend((Path(__file__).resolve().parent,
                           Path(__file__).resolve().parent.parent))
    for base in candidates:
        for candidate in (base, base / "数据库演示"):
            if ((candidate / "math_learning_demo.db").is_file()
                    and (candidate / "queries.sql").is_file()):
                return candidate.resolve()
    raise FileNotFoundError("找不到随软件附带的数据库演示文件：math_learning_demo.db、queries.sql")


def _insert_event(conn: sqlite3.Connection, event: tuple) -> str:
    """Insert one event atomically; an identical event ID is an idempotent retry."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        prior = conn.execute(
            "SELECT event_id,user_id,question_id,event_type,result,answered_at,wrong_reason "
            "FROM answer_events WHERE event_id=?", (event[0],)
        ).fetchone()
        if prior is not None:
            if tuple(prior) != event:
                raise ValueError("同一事件编号不能对应不同作答")
            conn.commit()
            return "duplicate"
        conn.execute(
            "INSERT INTO answer_events "
            "(event_id,user_id,question_id,event_type,result,answered_at,wrong_reason) "
            "VALUES (?,?,?,?,?,?,?)", event
        )
        conn.commit()
        return "inserted"
    except Exception:
        conn.rollback()
        raise


class DemoStore:
    """Read the bundled sample and maintain a writable local practice copy."""

    def __init__(self, resource_dir: str | Path | None = None,
                 data_dir: str | Path | None = None):
        self.resource_dir = _resource_location(resource_dir)
        self.reference_db = self.resource_dir / "math_learning_demo.db"
        if data_dir is None:
            local = os.getenv("LOCALAPPDATA")
            data_dir = Path(local) if local else Path.home() / "AppData" / "Local"
            data_dir = Path(data_dir) / "MathDifficultyDemo"
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "math_learning_demo.db"
        self.recovery_backup_path = self.data_dir / "math_learning_demo.recovery.db"
        self.recovery_manifest_path = self.data_dir / "math_learning_demo.recovery.json"
        if self.db_path.resolve() == self.reference_db.resolve():
            raise ValueError("演示数据副本不能覆盖附带的原始数据库")
        if not self.db_path.exists():
            self._copy_reference()
        with _connect(self.db_path) as conn:
            if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("本地演示数据库校验失败，请备份数据后重置样例")
        self._sync_catalog()

    def _copy_reference(self) -> None:
        """Build the app copy via SQLite backup, then replace it atomically."""
        fd, temp_name = tempfile.mkstemp(prefix="math_demo_", suffix=".db",
                                          dir=self.data_dir)
        os.close(fd)
        temporary = Path(temp_name)
        try:
            with _connect(self.reference_db) as source, _connect(temporary) as target:
                source.backup(target)
                if target.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise ValueError("附带的演示数据库校验失败")
            os.replace(temporary, self.db_path)
        finally:
            temporary.unlink(missing_ok=True)

    def reset(self) -> None:
        """Reset only the per-user practice copy, never the bundled reference."""
        if self.db_path.resolve() == self.reference_db.resolve():
            raise ValueError("拒绝覆盖原始演示数据库")
        self._copy_reference()
        self.recovery_backup_path.unlink(missing_ok=True)
        self.recovery_manifest_path.unlink(missing_ok=True)

    def _sync_catalog(self) -> None:
        """Add newly bundled catalog rows to old writable copies without touching answers."""
        catalog = (
            ("books", ("book_id", "title", "catalog_version")),
            ("chapters", ("book_id", "chapter_no", "title",
                          "first_question_no", "last_question_no")),
            ("questions", ("question_id", "book_id", "chapter_no", "question_no")),
        )
        with _connect(self.reference_db) as source:
            rows = {
                table: [tuple(row) for row in source.execute(
                    f"SELECT {','.join(columns)} FROM {table}")]
                for table, columns in catalog
            }
        with _connect(self.db_path) as target:
            target.execute("BEGIN IMMEDIATE")
            for table, columns in catalog:
                placeholders = ",".join("?" for _ in columns)
                target.executemany(
                    f"INSERT OR IGNORE INTO {table} ({','.join(columns)}) "
                    f"VALUES ({placeholders})",
                    rows[table],
                )

    def overview(self) -> dict:
        with _connect(self.db_path) as conn:
            counts = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                      for table in TABLES}
            first_answer_count = conn.execute(
                "SELECT COUNT(*) FROM v_first_answers"
            ).fetchone()[0]
            answered_question_count = conn.execute(
                "SELECT COUNT(*) FROM v_question_difficulty WHERE distinct_user_count>0"
            ).fetchone()[0]
            avg = conn.execute(
                "SELECT ROUND(AVG(difficulty_coefficient),3) "
                "FROM v_question_difficulty WHERE distinct_user_count>0"
            ).fetchone()[0]
            sample = conn.execute(
                "SELECT question_id,distinct_user_count AS first_answer_count, "
                "distinct_user_count,first_correct_count,difficulty_coefficient "
                "FROM v_question_difficulty WHERE question_id=?",
                (SAMPLE_QUESTION_ID,),
            ).fetchone()
            hardest = _rows(conn.execute(
                "SELECT q.question_id,b.title AS book_title,c.title AS chapter_title,"
                "d.distinct_user_count,d.distinct_user_count AS first_answer_count,"
                "d.first_correct_count,d.difficulty_coefficient "
                "FROM v_question_difficulty d "
                "JOIN questions q ON q.question_id=d.question_id "
                "JOIN books b ON b.book_id=q.book_id "
                "JOIN chapters c ON c.book_id=q.book_id AND c.chapter_no=q.chapter_no "
                "WHERE d.distinct_user_count>=2 "
                "ORDER BY d.difficulty_coefficient ASC,d.distinct_user_count DESC,q.question_id "
                "LIMIT 5"
            ))
            return {
                "counts": counts,
                "user_count": counts["users"],
                "book_count": counts["books"],
                "chapter_count": counts["chapters"],
                "question_count": counts["questions"],
                "answer_event_count": counts["answer_events"],
                "first_answer_count": first_answer_count,
                "answered_question_count": answered_question_count,
                "unanswered_question_count": counts["questions"] - answered_question_count,
                "average_difficulty_coefficient": avg,
                "sample_question": dict(sample) if sample else None,
                "hardest_questions": hardest,
            }

    def books(self) -> list[dict]:
        with _connect(self.db_path) as conn:
            return _rows(conn.execute(
                "SELECT b.book_id,b.title,b.catalog_version,"
                "COUNT(DISTINCT c.chapter_no) AS chapter_count,"
                "COUNT(DISTINCT q.question_id) AS question_count "
                "FROM books b LEFT JOIN chapters c ON c.book_id=b.book_id "
                "LEFT JOIN questions q ON q.book_id=b.book_id "
                "GROUP BY b.book_id ORDER BY b.book_id"
            ))

    def chapters(self, book_id: str | None = None) -> list[dict]:
        with _connect(self.db_path) as conn:
            return _rows(conn.execute(
                "SELECT c.book_id,b.title AS book_title,c.chapter_no,c.title,"
                "c.first_question_no,c.last_question_no,"
                "COUNT(q.question_id) AS question_count "
                "FROM chapters c JOIN books b ON b.book_id=c.book_id "
                "LEFT JOIN questions q ON q.book_id=c.book_id AND q.chapter_no=c.chapter_no "
                "WHERE (? IS NULL OR c.book_id=?) "
                "GROUP BY c.book_id,c.chapter_no "
                "ORDER BY c.book_id,c.chapter_no", (book_id, book_id)
            ))

    def questions(self, book_id: str | None = None,
                  chapter_no: int | None = None, search: str = "",
                  min_sample: int = 0) -> list[dict]:
        if int(min_sample) < 0:
            raise ValueError("最少首答人数不能小于 0")
        search_pattern = "%" + (search or "").strip() + "%"
        with _connect(self.db_path) as conn:
            return _rows(conn.execute(
                "SELECT q.question_id,q.book_id,b.title AS book_title,"
                "q.chapter_no,c.title AS chapter_title,q.question_no,"
                "d.distinct_user_count,d.distinct_user_count AS first_answer_count,"
                "d.first_correct_count,d.difficulty_coefficient "
                "FROM questions q JOIN books b ON b.book_id=q.book_id "
                "JOIN chapters c ON c.book_id=q.book_id AND c.chapter_no=q.chapter_no "
                "JOIN v_question_difficulty d ON d.question_id=q.question_id "
                "WHERE (? IS NULL OR q.book_id=?) "
                "AND (? IS NULL OR q.chapter_no=?) "
                "AND (q.question_id LIKE ? OR b.title LIKE ? OR c.title LIKE ?) "
                "AND d.distinct_user_count>=? "
                "ORDER BY q.book_id,q.chapter_no,q.question_no",
                (book_id, book_id, chapter_no, chapter_no,
                 search_pattern, search_pattern, search_pattern, int(min_sample)),
            ))

    def question_detail(self, question_id: str) -> dict:
        with _connect(self.db_path) as conn:
            item = conn.execute(
                "SELECT q.question_id,q.book_id,b.title AS book_title,"
                "q.chapter_no,c.title AS chapter_title,q.question_no,"
                "d.distinct_user_count,d.distinct_user_count AS first_answer_count,"
                "d.first_correct_count,d.difficulty_coefficient "
                "FROM questions q JOIN books b ON b.book_id=q.book_id "
                "JOIN chapters c ON c.book_id=q.book_id AND c.chapter_no=q.chapter_no "
                "JOIN v_question_difficulty d ON d.question_id=q.question_id "
                "WHERE q.question_id=?", (question_id,)
            ).fetchone()
            if item is None:
                raise KeyError(f"题目不存在：{question_id}")
            events = _rows(conn.execute(
                "SELECT e.event_id,e.user_id,u.display_name,e.question_id,e.event_type,"
                "e.result,e.answered_at,e.wrong_reason,"
                "CASE WHEN f.event_id IS NULL THEN 0 ELSE 1 END AS is_first_answer "
                "FROM answer_events e JOIN users u ON u.user_id=e.user_id "
                "LEFT JOIN v_first_answers f ON f.event_id=e.event_id "
                "WHERE e.question_id=? ORDER BY e.answered_at,e.event_id",
                (question_id,),
            ))
            first_answers = _rows(conn.execute(
                "SELECT f.event_id,f.user_id,u.display_name,f.question_id,f.result,"
                "f.answered_at FROM v_first_answers f "
                "JOIN users u ON u.user_id=f.user_id "
                "WHERE f.question_id=? ORDER BY f.answered_at,f.event_id",
                (question_id,),
            ))
            return {**dict(item), "events": events, "first_answers": first_answers}

    def users(self) -> list[dict]:
        with _connect(self.db_path) as conn:
            return _rows(conn.execute(
                "WITH attempts AS ("
                " SELECT user_id,COUNT(*) AS attempt_count,"
                " SUM(CASE WHEN result=1 THEN 1 ELSE 0 END) AS correct_attempt_count"
                " FROM answer_events GROUP BY user_id),"
                "completed AS ("
                " SELECT user_id,COUNT(*) AS completed_question_count"
                " FROM user_question_progress WHERE status IN (1,2) GROUP BY user_id)"
                "SELECT u.user_id,u.display_name,u.created_at,"
                "COALESCE(c.completed_question_count,0) AS completed_question_count,"
                "COALESCE(a.attempt_count,0) AS attempt_count,"
                "COALESCE(a.correct_attempt_count,0) AS correct_attempt_count,"
                "ROUND(1.0*a.correct_attempt_count/NULLIF(a.attempt_count,0),3) "
                "AS personal_accuracy "
                "FROM users u LEFT JOIN attempts a ON a.user_id=u.user_id "
                "LEFT JOIN completed c ON c.user_id=u.user_id "
                "ORDER BY u.user_id"
            ))

    def user_progress(self, user_id: str) -> list[dict]:
        with _connect(self.db_path) as conn:
            if not conn.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,)).fetchone():
                raise KeyError(f"用户不存在：{user_id}")
            return _rows(conn.execute(
                "SELECT q.question_id,q.book_id,b.title AS book_title,"
                "q.chapter_no,c.title AS chapter_title,q.question_no,"
                "COALESCE(p.status,0) AS status,COALESCE(p.status,0) AS personal_status,"
                "p.last_answered_at,p.last_event_id,f.result AS first_result,"
                "f.answered_at AS first_answered_at,"
                "d.distinct_user_count,d.distinct_user_count AS first_answer_count,"
                "d.first_correct_count,d.difficulty_coefficient "
                "FROM questions q JOIN books b ON b.book_id=q.book_id "
                "JOIN chapters c ON c.book_id=q.book_id AND c.chapter_no=q.chapter_no "
                "JOIN v_question_difficulty d ON d.question_id=q.question_id "
                "LEFT JOIN user_question_progress p "
                "ON p.question_id=q.question_id AND p.user_id=? "
                "LEFT JOIN v_first_answers f "
                "ON f.question_id=q.question_id AND f.user_id=? "
                "ORDER BY q.book_id,q.chapter_no,q.question_no", (user_id, user_id)
            ))

    def answer_matrix(self, book_id: str | None = None,
                      chapter_no: int | None = None) -> list[dict]:
        """One row per learner and selected question, including unanswered pairs."""
        with _connect(self.db_path) as conn:
            return _rows(conn.execute(
                "WITH attempt_counts AS ("
                " SELECT user_id,question_id,COUNT(*) AS attempt_count"
                " FROM answer_events GROUP BY user_id,question_id)"
                "SELECT u.user_id,u.display_name,q.question_id,q.book_id,"
                "b.title AS book_title,q.chapter_no,c.title AS chapter_title,"
                "q.question_no,COALESCE(p.status,0) AS status,"
                "f.result AS first_result,p.last_answered_at,"
                "COALESCE(a.attempt_count,0) AS attempt_count "
                "FROM users u CROSS JOIN questions q "
                "JOIN books b ON b.book_id=q.book_id "
                "JOIN chapters c ON c.book_id=q.book_id AND c.chapter_no=q.chapter_no "
                "LEFT JOIN user_question_progress p "
                "ON p.user_id=u.user_id AND p.question_id=q.question_id "
                "LEFT JOIN v_first_answers f "
                "ON f.user_id=u.user_id AND f.question_id=q.question_id "
                "LEFT JOIN attempt_counts a "
                "ON a.user_id=u.user_id AND a.question_id=q.question_id "
                "WHERE (? IS NULL OR q.book_id=?) "
                "AND (? IS NULL OR q.chapter_no=?) "
                "ORDER BY u.user_id,q.book_id,q.chapter_no,q.question_no",
                (book_id, book_id, chapter_no, chapter_no),
            ))

    def add_user(self, display_name: str,
                 initial_question_id: str | None = None,
                 initial_result: int | None = None) -> dict:
        name = str(display_name).strip()
        if not name:
            raise ValueError("请输入用户名称")
        if len(name) > 80:
            raise ValueError("用户名称不能超过 80 个字符")
        if (initial_question_id is None) != (initial_result is None):
            raise ValueError("首次作答须同时选择题目和结果")
        if initial_result is not None and (initial_result not in (1, 2)
                                           or isinstance(initial_result, bool)):
            raise ValueError("作答结果只能是 1（会）或 2（不会）")
        user_id = "local-" + uuid.uuid4().hex[:16]
        created_at = _utc_now()
        with _connect(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            if initial_question_id is not None and not conn.execute(
                "SELECT 1 FROM questions WHERE question_id=?",
                (initial_question_id,),
            ).fetchone():
                raise ValueError(f"题目不存在：{initial_question_id}")
            conn.execute(
                "INSERT INTO users(user_id,display_name,created_at) VALUES (?,?,?)",
                (user_id, name, created_at),
            )
            if initial_question_id is not None:
                event_id = f"app-{time.time_ns():020d}-{uuid.uuid4().hex[:8]}"
                conn.execute(
                    "INSERT INTO answer_events "
                    "(event_id,user_id,question_id,event_type,result,answered_at,wrong_reason) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (event_id, user_id, initial_question_id, "practice",
                     initial_result, created_at, None),
                )
        return {"user_id": user_id, "display_name": name, "created_at": created_at}

    def delete_user(self, user_id: str) -> dict:
        """Remove a learner and their answers as one transaction."""
        with _connect(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            user = conn.execute(
                "SELECT user_id,display_name,created_at FROM users WHERE user_id=?",
                (user_id,),
            ).fetchone()
            if user is None:
                raise KeyError(f"用户不存在：{user_id}")
            conn.execute("DELETE FROM user_question_progress WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM answer_events WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM users WHERE user_id=?", (user_id,))
            return dict(user)

    def record_answer(self, user_id: str, question_id: str, result: int,
                      event_type: str = "practice",
                      wrong_reason: str | None = None) -> dict:
        if result not in (1, 2) or isinstance(result, bool):
            raise ValueError("作答结果只能是 1（会）或 2（不会）")
        if event_type not in ("practice", "review", "legacy_practice"):
            raise ValueError("作答类型无效")
        reason = str(wrong_reason).strip() if wrong_reason is not None else None
        if not reason:
            reason = None
        if reason is not None and len(reason) > 200:
            raise ValueError("错因不能超过 200 个字符")
        answered_at = _utc_now()
        event_id = f"app-{time.time_ns():020d}-{uuid.uuid4().hex[:8]}"
        event = (event_id, user_id, question_id, event_type,
                 result, answered_at, reason)
        with _connect(self.db_path) as conn:
            try:
                _insert_event(conn, event)
            except sqlite3.IntegrityError as exc:
                raise ValueError("无法记录作答，请确认用户和题号存在") from exc
        detail = self.question_detail(question_id)
        return {
            "event_id": event_id, "user_id": user_id, "question_id": question_id,
            "event_type": event_type, "result": result, "answered_at": answered_at,
            "wrong_reason": reason,
            "first_answer_count": detail["first_answer_count"],
            "first_correct_count": detail["first_correct_count"],
            "difficulty_coefficient": detail["difficulty_coefficient"],
            "question": detail,
        }

    def generate_simulated_events(self, count: int, seed=None) -> dict:
        """Append a repeatable batch to the writable copy as one transaction."""
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("模拟作答数量必须是非负整数")
        rng = random.Random(seed)
        summary = {
            "requested_count": count,
            "inserted_count": 0,
            "synthetic_user_count": 0,
            "practice_count": 0,
            "review_count": 0,
            "correct_count": 0,
            "incorrect_count": 0,
        }
        with _connect(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            before = conn.execute("SELECT COUNT(*) FROM answer_events").fetchone()[0]
            if count:
                users = [row[0] for row in conn.execute("SELECT user_id FROM users ORDER BY user_id")]
                questions = [row[0] for row in conn.execute(
                    "SELECT question_id FROM questions ORDER BY book_id,chapter_no,question_no")]
                if not questions:
                    raise ValueError("题库为空，无法生成模拟作答")
                if not users:
                    for index in range(3):
                        user_id = "sim-" + uuid.uuid4().hex[:16]
                        conn.execute(
                            "INSERT INTO users(user_id,display_name,created_at) "
                            "VALUES (?,?,?)",
                            (user_id, f"模拟学习者 {index + 1}", _utc_now()),
                        )
                        users.append(user_id)
                    summary["synthetic_user_count"] = len(users)
                latest = {
                    (row["user_id"], row["question_id"]): row["last_answered_at"]
                    for row in conn.execute(
                        "SELECT user_id,question_id,MAX(answered_at) AS last_answered_at "
                        "FROM answer_events GROUP BY user_id,question_id")
                }
                now = datetime.fromisoformat(_utc_now().replace("Z", "+00:00"))
                for _ in range(count):
                    user_id = rng.choice(users)
                    question_id = rng.choice(questions)
                    pair = (user_id, question_id)
                    prior_at = latest.get(pair)
                    event_type = "review" if prior_at is not None else "practice"
                    result = rng.choice((1, 2))
                    answered_time = now
                    if prior_at is not None:
                        answered_time = max(
                            now, datetime.fromisoformat(
                                prior_at.replace("Z", "+00:00")) + timedelta(seconds=1))
                    answered_at = answered_time.strftime("%Y-%m-%dT%H:%M:%SZ")
                    event_id = f"sim-{time.time_ns():020d}-{uuid.uuid4().hex[:8]}"
                    conn.execute(
                        "INSERT INTO answer_events "
                        "(event_id,user_id,question_id,event_type,result,answered_at,wrong_reason) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (event_id, user_id, question_id, event_type,
                         result, answered_at, None),
                    )
                    latest[pair] = answered_at
                    summary["inserted_count"] += 1
                    summary["review_count" if event_type == "review" else "practice_count"] += 1
                    summary["correct_count" if result == 1 else "incorrect_count"] += 1
            after = conn.execute("SELECT COUNT(*) FROM answer_events").fetchone()[0]
            summary["before_event_count"] = before
            summary["after_event_count"] = after
        return summary

    def concurrent_distinct_demo(self) -> dict:
        """Save distinct out-of-order events on the writable copy with visible lock wait."""
        with _connect(self.db_path) as conn:
            if not conn.execute(
                "SELECT 1 FROM questions WHERE question_id=?", (SAMPLE_QUESTION_ID,)
            ).fetchone():
                raise KeyError(f"题目不存在：{SAMPLE_QUESTION_ID}")
            before_event_count = conn.execute(
                "SELECT COUNT(*) FROM answer_events").fetchone()[0]
        learner = self.add_user("并发演示学习者")
        user_id = learner["user_id"]
        now = datetime.fromisoformat(_utc_now().replace("Z", "+00:00"))
        requests = [
            {"label": "earlier_practice", "event_id": "concurrent-" + uuid.uuid4().hex,
             "event_type": "practice", "result": 1,
             "answered_at": (now - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")},
            {"label": "later_review", "event_id": "concurrent-" + uuid.uuid4().hex,
             "event_type": "review", "result": 2,
             "answered_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")},
        ]
        barrier = threading.Barrier(2)
        later_acquired = threading.Event()
        earlier_attempting = threading.Event()
        commit_order_lock = threading.Lock()
        demo_started_ns = time.perf_counter_ns()

        def write_request(request: dict) -> dict:
            try:
                with _connect(self.db_path) as conn:
                    barrier.wait(timeout=10)
                    if request["label"] == "earlier_practice":
                        if not later_acquired.wait(timeout=10):
                            raise TimeoutError("较晚事件未取得写锁")
                        earlier_attempting.set()
                    begin_at = time.perf_counter()
                    conn.execute("BEGIN IMMEDIATE")
                    acquired_at = time.perf_counter()
                    if request["label"] == "later_review":
                        later_acquired.set()
                        if not earlier_attempting.wait(timeout=10):
                            raise TimeoutError("较早事件未开始等待写锁")
                        time.sleep(0.15)
                    conn.execute(
                        "INSERT INTO answer_events "
                        "(event_id,user_id,question_id,event_type,result,answered_at,wrong_reason) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (request["event_id"], user_id, SAMPLE_QUESTION_ID,
                         request["event_type"], request["result"],
                         request["answered_at"], None),
                    )
                    with commit_order_lock:
                        conn.commit()
                        committed_ns = time.perf_counter_ns()
                    committed_at = time.perf_counter()
                return {
                    "label": request["label"], "event_id": request["event_id"],
                    "status": "inserted",
                    "lock_wait_ms": round((acquired_at - begin_at) * 1000, 1),
                    "transaction_ms": round((committed_at - begin_at) * 1000, 1),
                    "committed_at_ms": round((committed_ns - demo_started_ns) / 1_000_000, 1),
                    "_committed_ns": committed_ns,
                }
            except Exception as exc:
                return {"label": request["label"], "event_id": request["event_id"],
                        "status": "error", "error": str(exc),
                        "lock_wait_ms": None, "transaction_ms": None,
                        "committed_at_ms": None}

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(write_request, request) for request in requests]
            outcomes = [future.result(timeout=30) for future in futures]
        commit_order = [item["label"] for item in sorted(
            (item for item in outcomes if item["status"] == "inserted"),
            key=lambda item: item["_committed_ns"])]
        for item in outcomes:
            item.pop("_committed_ns", None)
        with _connect(self.db_path) as conn:
            row_count = conn.execute(
                "SELECT COUNT(*) FROM answer_events WHERE user_id=? AND question_id=?",
                (user_id, SAMPLE_QUESTION_ID),
            ).fetchone()[0]
            first = conn.execute(
                "SELECT result,answered_at FROM v_first_answers "
                "WHERE user_id=? AND question_id=?", (user_id, SAMPLE_QUESTION_ID)
            ).fetchone()
            latest = conn.execute(
                "SELECT status,last_answered_at FROM user_question_progress "
                "WHERE user_id=? AND question_id=?", (user_id, SAMPLE_QUESTION_ID)
            ).fetchone()
            after_event_count = conn.execute(
                "SELECT COUNT(*) FROM answer_events").fetchone()[0]
        first_result = first["result"] if first else None
        latest_status = latest["status"] if latest else None
        passed = (
            all(item["status"] == "inserted" for item in outcomes)
            and commit_order == ["later_review", "earlier_practice"]
            and row_count == 2 and after_event_count == before_event_count + 2
            and first_result == 1 and latest_status == 2
        )
        cleanup_performed = False
        cleanup_error = None
        if not passed:
            try:
                self.delete_user(user_id)
                cleanup_performed = True
            except Exception as exc:
                cleanup_error = str(exc)
        return {
            "user_id": user_id,
            "question_id": SAMPLE_QUESTION_ID,
            "requests": requests,
            "outcomes": outcomes,
            "commit_order": commit_order,
            "row_count": row_count,
            "first_result": first_result,
            "latest_status": latest_status,
            "first_answered_at": first["answered_at"] if first else None,
            "last_answered_at": latest["last_answered_at"] if latest else None,
            "before_event_count": before_event_count,
            "after_event_count": after_event_count,
            "cleanup_performed": cleanup_performed,
            "cleanup_error": cleanup_error,
            "passed": passed,
        }

    def query_examples(self) -> list[dict]:
        source = (self.resource_dir / "queries.sql").read_text(encoding="utf-8")
        pieces = re.split(r"(?m)^-- QUERY (\d+) \| (.+)\r?\n", source)
        if pieces[0].strip():
            raise ValueError("预设查询文件格式错误")
        examples = []
        for i in range(1, len(pieces), 3):
            query_id = int(pieces[i])
            title = pieces[i + 1].strip()
            sql = pieces[i + 2].strip()
            if not sql.endswith(";") or sql.count(";") != 1:
                raise ValueError(f"预设查询 {query_id} 格式错误")
            sql = sql[:-1].strip()
            if not sql.upper().startswith(("SELECT", "WITH")):
                raise ValueError(f"预设查询 {query_id} 不是只读查询")
            examples.append({"id": query_id, "title": title, "sql": sql})
        return examples

    def run_query(self, query_id: int) -> dict:
        example = next((item for item in self.query_examples()
                        if item["id"] == int(query_id)), None)
        if example is None:
            raise KeyError(f"没有预设查询：{query_id}")
        with _connect(self.db_path) as conn:
            cursor = conn.execute(example["sql"])
            return {
                **example,
                "columns": [column[0] for column in cursor.description],
                "rows": _rows(cursor),
            }

    def _scratch_copy(self, path: Path) -> None:
        with _connect(self.db_path) as source, _connect(path) as target:
            source.backup(target)

    def concurrency_demo(self) -> dict:
        """Race identical writes against a scratch copy, never the user's data."""
        with tempfile.TemporaryDirectory(prefix="math_concurrency_") as temp:
            scratch = Path(temp) / "scratch.db"
            self._scratch_copy(scratch)
            with _connect(scratch) as conn:
                first = conn.execute(
                    "SELECT user_id,answered_at FROM v_first_answers "
                    "WHERE question_id=? ORDER BY answered_at,user_id LIMIT 1",
                    (SAMPLE_QUESTION_ID,),
                ).fetchone()
                now = datetime.fromisoformat(_utc_now().replace("Z", "+00:00"))
                created_synthetic_learner = first is None
                if first is None:
                    user_id = "race-user-" + uuid.uuid4().hex[:16]
                    first_answered_at = (now - timedelta(seconds=1)).strftime(
                        "%Y-%m-%dT%H:%M:%SZ")
                    conn.execute(
                        "INSERT INTO users(user_id,display_name,created_at) "
                        "VALUES (?,?,?)",
                        (user_id, "并发演示学习者", _utc_now()),
                    )
                    conn.execute(
                        "INSERT INTO answer_events "
                        "(event_id,user_id,question_id,event_type,result,answered_at,wrong_reason) "
                        "VALUES (?,?,?,?,?,?,?)",
                        ("race-seed-" + uuid.uuid4().hex, user_id,
                         SAMPLE_QUESTION_ID, "practice", 2, first_answered_at, None),
                    )
                else:
                    user_id = first["user_id"]
                    first_answered_at = first["answered_at"]
                first_time = datetime.fromisoformat(
                    first_answered_at.replace("Z", "+00:00"))
                repeat_answered_at = max(now, first_time + timedelta(seconds=1)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
                before = dict(conn.execute(
                    "SELECT distinct_user_count,first_correct_count,"
                    "difficulty_coefficient FROM v_question_difficulty "
                    "WHERE question_id=?", (SAMPLE_QUESTION_ID,),
                ).fetchone())
            event = ("race-" + uuid.uuid4().hex, user_id, SAMPLE_QUESTION_ID,
                     "review", 1, repeat_answered_at, None)
            barrier = threading.Barrier(2)

            def write_once() -> str:
                with _connect(scratch) as conn:
                    barrier.wait(timeout=10)
                    return _insert_event(conn, event)

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(write_once) for _ in range(2)]
                outcomes = sorted(f.result(timeout=30) for f in futures)
            with _connect(scratch) as conn:
                after = dict(conn.execute(
                    "SELECT distinct_user_count,first_correct_count,"
                    "difficulty_coefficient FROM v_question_difficulty "
                    "WHERE question_id=?", (SAMPLE_QUESTION_ID,),
                ).fetchone())
                row_count = conn.execute(
                    "SELECT COUNT(*) FROM answer_events WHERE event_id=?", (event[0],)
                ).fetchone()[0]
            passed = (outcomes == ["duplicate", "inserted"]
                      and row_count == 1 and before == after
                      and repeat_answered_at > first_answered_at)
            return {
                "selected_user_id": user_id,
                "created_synthetic_learner": created_synthetic_learner,
                "first_answered_at": first_answered_at,
                "repeat_answered_at": repeat_answered_at,
                "worker_outcomes": outcomes,
                "rows_for_same_event_id": row_count,
                "before_global": before,
                "after_global": after,
                "passed": passed,
            }

    @staticmethod
    def _snapshot(conn: sqlite3.Connection) -> dict:
        counts = {}
        hashes = {}
        for table in TABLES:
            values = _rows(conn.execute(f"SELECT * FROM {table} ORDER BY rowid"))
            counts[table] = len(values)
            payload = json.dumps(values, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")).encode("utf-8")
            hashes[table] = hashlib.sha256(payload).hexdigest()
        return {"row_counts": counts, "table_sha256": hashes}

    def has_recovery_backup(self) -> bool:
        return self.recovery_backup_path.is_file()

    def _write_recovery_manifest(self, manifest: dict) -> None:
        fd, temp_name = tempfile.mkstemp(prefix="recovery_manifest_", suffix=".json",
                                          dir=self.data_dir)
        temporary = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(manifest, output, ensure_ascii=False, sort_keys=True)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.recovery_manifest_path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _recovery_event(conn: sqlite3.Connection, event_id: str) -> dict | None:
        row = conn.execute(
            "SELECT e.event_id,e.user_id,u.display_name,e.question_id,"
            "q.book_id,b.title AS book_title,q.chapter_no,"
            "c.title AS chapter_title,q.question_no,e.event_type,e.result,"
            "e.answered_at,e.wrong_reason,e.recorded_at,"
            "CASE WHEN f.event_id IS NULL THEN 0 ELSE 1 END AS is_first_answer,"
            "CASE WHEN p.last_event_id=e.event_id THEN 1 ELSE 0 END AS is_latest "
            "FROM answer_events e JOIN users u ON u.user_id=e.user_id "
            "JOIN questions q ON q.question_id=e.question_id "
            "JOIN books b ON b.book_id=q.book_id "
            "JOIN chapters c ON c.book_id=q.book_id AND c.chapter_no=q.chapter_no "
            "LEFT JOIN v_first_answers f ON f.event_id=e.event_id "
            "LEFT JOIN user_question_progress p "
            "ON p.user_id=e.user_id AND p.question_id=e.question_id "
            "WHERE e.event_id=?", (event_id,),
        ).fetchone()
        return dict(row) if row else None

    def recovery_candidates(self, limit: int = 200) -> list[dict]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("记录数量必须是正整数")
        with _connect(self.db_path) as conn:
            ids = [row[0] for row in conn.execute(
                "SELECT event_id FROM answer_events "
                "ORDER BY answered_at DESC,event_id DESC LIMIT ?", (limit,)
            )]
            return [event for event_id in ids
                    if (event := self._recovery_event(conn, event_id)) is not None]

    def delete_event_for_recovery(self, event_id: str) -> dict:
        """Save a durable local backup, then remove one event and repair progress."""
        if self.recovery_manifest_path.exists() and not self.recovery_backup_path.exists():
            self.recovery_manifest_path.unlink()
        if self.recovery_backup_path.exists() or self.recovery_manifest_path.exists():
            raise RuntimeError("已有待恢复备份，请先完成恢复或重置样例")
        fd, temp_name = tempfile.mkstemp(prefix="recovery_backup_", suffix=".db",
                                          dir=self.data_dir)
        os.close(fd)
        temporary = Path(temp_name)
        committed = False
        try:
            with _connect(self.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                event = self._recovery_event(conn, event_id)
                if event is None:
                    raise KeyError(f"作答事件不存在：{event_id}")
                progress_row = conn.execute(
                    "SELECT user_id,question_id,status,last_answered_at,last_event_id "
                    "FROM user_question_progress WHERE user_id=? AND question_id=?",
                    (event["user_id"], event["question_id"]),
                ).fetchone()
                progress_before = dict(progress_row) if progress_row else None
                before = self._snapshot(conn)
                # The reserved write lock blocks other writers while a second
                # read connection copies the committed database image.
                with _connect(self.db_path) as source, _connect(temporary) as backup:
                    source.backup(backup)
                    if backup.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                        raise ValueError("恢复备份校验失败，未删除作答")
                    if self._snapshot(backup) != before:
                        raise ValueError("备份与待删除数据不一致，未删除作答")
                os.replace(temporary, self.recovery_backup_path)
                manifest = {"event": event, "before_snapshot": before,
                            "status": "prepared"}
                self._write_recovery_manifest(manifest)
                conn.execute(
                    "DELETE FROM user_question_progress WHERE user_id=? AND question_id=?",
                    (event["user_id"], event["question_id"]),
                )
                conn.execute("DELETE FROM answer_events WHERE event_id=?", (event_id,))
                newest = conn.execute(
                    "SELECT event_id,result,answered_at FROM answer_events "
                    "WHERE user_id=? AND question_id=? "
                    "ORDER BY answered_at DESC,event_id DESC LIMIT 1",
                    (event["user_id"], event["question_id"]),
                ).fetchone()
                if newest is not None:
                    conn.execute(
                        "INSERT INTO user_question_progress "
                        "(user_id,question_id,status,last_answered_at,last_event_id) "
                        "VALUES (?,?,?,?,?)",
                        (event["user_id"], event["question_id"], newest["result"],
                         newest["answered_at"], newest["event_id"]),
                    )
                after = self._snapshot(conn)
                progress_row = conn.execute(
                    "SELECT user_id,question_id,status,last_answered_at,last_event_id "
                    "FROM user_question_progress WHERE user_id=? AND question_id=?",
                    (event["user_id"], event["question_id"]),
                ).fetchone()
                progress_after = dict(progress_row) if progress_row else None
                quick_check = conn.execute("PRAGMA quick_check").fetchone()[0]
                foreign_key_errors = len(conn.execute(
                    "PRAGMA foreign_key_check").fetchall())
                if (after["row_counts"]["answer_events"]
                        != before["row_counts"]["answer_events"] - 1
                        or quick_check != "ok" or foreign_key_errors):
                    raise ValueError("删除后数据库校验失败，已撤销删除")
                conn.commit()
                committed = True
            manifest["status"] = "deleted"
            manifest["after_snapshot"] = after
            self._write_recovery_manifest(manifest)
            return {
                "event": event,
                "backup_path": str(self.recovery_backup_path),
                "before_counts": before["row_counts"],
                "after_counts": after["row_counts"],
                "progress_before": progress_before,
                "progress_after": progress_after,
                "quick_check": quick_check,
                "foreign_key_errors": foreign_key_errors,
                "passed": True,
            }
        except Exception:
            if not committed:
                self.recovery_backup_path.unlink(missing_ok=True)
                self.recovery_manifest_path.unlink(missing_ok=True)
            raise
        finally:
            temporary.unlink(missing_ok=True)

    def restore_recovery_backup(self) -> dict:
        """Restore the pre-deletion snapshot without touching the bundled DB."""
        if not self.has_recovery_backup():
            raise FileNotFoundError("没有可恢复的本地备份")
        manifest = (json.loads(self.recovery_manifest_path.read_text(encoding="utf-8"))
                    if self.recovery_manifest_path.is_file() else None)
        with _connect(self.db_path) as current:
            before = self._snapshot(current)
        with _connect(self.recovery_backup_path) as backup:
            backup_snapshot = self._snapshot(backup)
            if manifest is not None and backup_snapshot != manifest["before_snapshot"]:
                raise ValueError("恢复备份与清单不一致")
            if backup.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("恢复备份校验失败")
            if backup.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("恢复备份外键校验失败")
            fd, temp_name = tempfile.mkstemp(prefix="restore_recovery_", suffix=".db",
                                              dir=self.data_dir)
            os.close(fd)
            temporary = Path(temp_name)
            try:
                with _connect(temporary) as target:
                    backup.backup(target)
                os.replace(temporary, self.db_path)
            finally:
                temporary.unlink(missing_ok=True)
        with _connect(self.db_path) as restored:
            after = self._snapshot(restored)
            quick_check = restored.execute("PRAGMA quick_check").fetchone()[0]
            foreign_key_errors = len(restored.execute("PRAGMA foreign_key_check").fetchall())
        hashes_match = after["table_sha256"] == backup_snapshot["table_sha256"]
        passed = (after == backup_snapshot and quick_check == "ok"
                  and foreign_key_errors == 0)
        if passed:
            self.recovery_backup_path.unlink()
            self.recovery_manifest_path.unlink(missing_ok=True)
        return {
            "event": manifest["event"] if manifest else None,
            "before_counts": before["row_counts"],
            "after_counts": after["row_counts"],
            "backup_counts": backup_snapshot["row_counts"],
            "quick_check": quick_check,
            "foreign_key_errors": foreign_key_errors,
            "hashes_match": hashes_match,
            "passed": passed,
        }

    def recovery_demo(self) -> dict:
        """Simulate loss and restore using two temporary copies only."""
        with tempfile.TemporaryDirectory(prefix="math_recovery_") as temp:
            work_path = Path(temp) / "work.db"
            backup_path = Path(temp) / "backup.db"
            self._scratch_copy(work_path)
            with _connect(work_path) as work, _connect(backup_path) as backup:
                before = self._snapshot(work)
                work.backup(backup)
            with _connect(work_path) as work:
                work.execute("BEGIN IMMEDIATE")
                try:
                    work.execute("DELETE FROM user_question_progress")
                    work.execute("DELETE FROM answer_events")
                    work.commit()
                except Exception:
                    work.rollback()
                    raise
                after_loss = self._snapshot(work)
            with _connect(backup_path) as backup, _connect(work_path) as work:
                backup.backup(work)
                restored = self._snapshot(work)
                foreign_key_errors = len(work.execute("PRAGMA foreign_key_check").fetchall())
                quick_check = work.execute("PRAGMA quick_check").fetchone()[0]
            passed = (before == restored and foreign_key_errors == 0
                      and quick_check == "ok"
                      and after_loss["row_counts"]["answer_events"] == 0)
            return {
                "before_backup": before,
                "after_simulated_loss": after_loss,
                "after_restore": restored,
                "foreign_key_errors_after_restore": foreign_key_errors,
                "quick_check_after_restore": quick_check,
                "passed": passed,
            }
