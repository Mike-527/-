"""Focused checks for the offline desktop demonstration data layer."""

import hashlib
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from model import DemoStore


class DemoStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = DemoStore(data_dir=Path(self.temp.name))
        self.reference_hash = hashlib.sha256(self.store.reference_db.read_bytes()).hexdigest()

    def tearDown(self):
        self.assertEqual(
            hashlib.sha256(self.store.reference_db.read_bytes()).hexdigest(),
            self.reference_hash,
        )
        self.temp.cleanup()

    def test_first_answer_and_repeat_have_different_roles(self):
        original = self.store.question_detail("660s1_1_1")
        self.assertEqual((original["first_answer_count"], original["first_correct_count"],
                          original["difficulty_coefficient"]), (5, 1, 0.2))
        self.assertIsNone(self.store.question_detail("660s1_1_3")["difficulty_coefficient"])

        repeat = self.store.record_answer("u002", "660s1_1_1", 1, "review")
        self.assertEqual(repeat["difficulty_coefficient"], 0.2)
        self.assertEqual(repeat["first_answer_count"], 5)

        learner = self.store.add_user("临时学习者")
        first = self.store.record_answer(learner["user_id"], "660s1_1_1", 1)
        self.assertEqual((first["first_answer_count"], first["first_correct_count"],
                          first["difficulty_coefficient"]), (6, 2, 0.3333))
        retry = self.store.record_answer(learner["user_id"], "660s1_1_1", 2, "review")
        self.assertEqual(retry["difficulty_coefficient"], 0.3333)
        progress = next(item for item in self.store.user_progress(learner["user_id"])
                        if item["question_id"] == "660s1_1_1")
        self.assertEqual((progress["first_result"], progress["status"]), (1, 2))

    def test_predefined_queries_and_copy_only_demos(self):
        self.assertEqual(len(self.store.query_examples()), 6)
        for example in self.store.query_examples():
            output = self.store.run_query(example["id"])
            self.assertTrue(output["columns"])
            self.assertIsInstance(output["rows"], list)
        before = self.store.overview()["counts"]
        self.assertTrue(self.store.concurrency_demo()["passed"])
        self.assertTrue(self.store.recovery_demo()["passed"])
        self.assertEqual(self.store.overview()["counts"], before)

    def test_reset_restores_only_local_copy(self):
        self.store.add_user("重置验证")
        self.assertEqual(self.store.overview()["user_count"], 6)
        self.store.reset()
        self.assertEqual(self.store.overview()["user_count"], 5)
        self.assertEqual(self.store.overview()["sample_question"]["difficulty_coefficient"], 0.2)

    def test_answer_matrix_includes_every_pair_and_filters_questions(self):
        rows = self.store.answer_matrix()
        self.assertEqual(len(rows), 5 * self.store.overview()["question_count"])
        answered = next(row for row in rows if row["user_id"] == "u001"
                        and row["question_id"] == "660s1_1_2")
        self.assertEqual((answered["first_result"], answered["status"],
                          answered["attempt_count"], answered["last_answered_at"]),
                         (1, 2, 2, "2026-09-28T10:00:00Z"))
        unanswered = next(row for row in rows if row["user_id"] == "u001"
                          and row["question_id"] == "660s1_1_3")
        self.assertEqual((unanswered["first_result"], unanswered["status"],
                          unanswered["attempt_count"], unanswered["last_answered_at"]),
                         (None, 0, 0, None))
        filtered = self.store.answer_matrix("660s1", 1)
        self.assertEqual(len(filtered), 5 * len(self.store.questions("660s1", 1)))
        self.assertTrue(all(row["book_id"] == "660s1" and row["chapter_no"] == 1
                            for row in filtered))

    def test_add_user_with_initial_answer_and_delete_existing_learner(self):
        before = self.store.overview()["counts"]
        learner = self.store.add_user("新学习者", "660s1_1_1", 1)
        own_row = next(row for row in self.store.answer_matrix("660s1", 1)
                       if row["user_id"] == learner["user_id"]
                       and row["question_id"] == "660s1_1_1")
        self.assertEqual((own_row["status"], own_row["first_result"],
                          own_row["attempt_count"]), (1, 1, 1))
        self.assertEqual(self.store.overview()["counts"]["answer_events"],
                         before["answer_events"] + 1)
        deleted = self.store.delete_user("u002")
        self.assertEqual(deleted["user_id"], "u002")
        self.assertFalse(any(row["user_id"] == "u002" for row in self.store.answer_matrix()))
        self.assertEqual(self.store.overview()["counts"]["answer_events"],
                         before["answer_events"] + 1 - 4)
        self.assertEqual(self.store.overview()["counts"]["questions"], before["questions"])
        self.assertEqual(self.store.overview()["counts"]["books"], before["books"])
        self.assertEqual(self.store.overview()["counts"]["chapters"], before["chapters"])
        self.assertEqual(self.store.question_detail("660s1_1_1")["first_answer_count"], 5)
        self.assertEqual(self.store.user_progress(learner["user_id"])[0]["status"], 1)

    def test_add_user_failure_is_atomic(self):
        before = self.store.overview()["counts"]
        with self.assertRaises(ValueError):
            self.store.add_user("题目不存在", "missing", 1)
        with self.assertRaises(ValueError):
            self.store.add_user("缺结果", "660s1_1_1")
        with closing(sqlite3.connect(self.store.db_path)) as conn:
            conn.execute("CREATE TRIGGER abort_new_answer BEFORE INSERT ON answer_events "
                         "WHEN NEW.user_id LIKE 'local-%' BEGIN "
                         "SELECT RAISE(ABORT, 'injected failure'); END")
            conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.add_user("事务回滚", "660s1_1_1", 1)
        self.assertEqual(self.store.overview()["counts"], before)
        self.assertFalse(any(user["display_name"] == "事务回滚"
                             for user in self.store.users()))
        with self.assertRaises(KeyError):
            self.store.delete_user("missing")
        self.assertEqual(self.store.overview()["counts"], before)

    def test_delete_user_failure_restores_answers_and_progress(self):
        before = self.store.overview()["counts"]
        prior = next(row for row in self.store.answer_matrix()
                     if row["user_id"] == "u002" and row["question_id"] == "660s1_1_1")
        with closing(sqlite3.connect(self.store.db_path)) as conn:
            conn.execute("CREATE TRIGGER abort_user_delete BEFORE DELETE ON users "
                         "WHEN OLD.user_id='u002' BEGIN "
                         "SELECT RAISE(ABORT, 'injected failure'); END")
            conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.delete_user("u002")
        self.assertEqual(self.store.overview()["counts"], before)
        restored = next(row for row in self.store.answer_matrix()
                        if row["user_id"] == "u002" and row["question_id"] == "660s1_1_1")
        self.assertEqual(restored, prior)

    def test_concurrency_demo_selects_remaining_answered_learner(self):
        self.store.delete_user("u002")
        before = self.store.overview()["counts"]
        result = self.store.concurrency_demo()
        self.assertTrue(result["passed"])
        self.assertFalse(result["created_synthetic_learner"])
        self.assertNotEqual(result["selected_user_id"], "u002")
        self.assertGreater(result["repeat_answered_at"], result["first_answered_at"])
        self.assertEqual(result["before_global"], result["after_global"])
        self.assertEqual(self.store.overview()["counts"], before)

    def test_concurrency_demo_seeds_scratch_after_all_learners_deleted(self):
        for user in self.store.users():
            self.store.delete_user(user["user_id"])
        before = self.store.overview()["counts"]
        result = self.store.concurrency_demo()
        self.assertTrue(result["passed"])
        self.assertTrue(result["created_synthetic_learner"])
        self.assertEqual(result["before_global"]["distinct_user_count"], 1)
        self.assertEqual(result["before_global"], result["after_global"])
        self.assertGreater(result["repeat_answered_at"], result["first_answered_at"])
        self.assertEqual(self.store.overview()["counts"], before)

    def test_concurrency_demo_repeat_is_later_even_when_clock_matches_first_answer(self):
        with patch("model._utc_now", return_value="2026-09-26T09:00:00Z"):
            result = self.store.concurrency_demo()
        self.assertTrue(result["passed"])
        self.assertEqual(result["first_answered_at"], "2026-09-26T09:00:00Z")
        self.assertEqual(result["repeat_answered_at"], "2026-09-26T09:00:01Z")

    def test_startup_sync_adds_catalog_without_changing_existing_work(self):
        full_count = self.store.overview()["question_count"]
        self.assertGreater(full_count, 6)
        learner = self.store.add_user("保留的学习者", "660s1_1_1", 2)
        before_events = self.store.overview()["answer_event_count"]
        with closing(sqlite3.connect(self.store.db_path)) as conn:
            referenced = {row[0] for row in conn.execute(
                "SELECT DISTINCT question_id FROM answer_events")}
            all_ids = [row[0] for row in conn.execute(
                "SELECT question_id FROM questions ORDER BY question_id")]
            keep = set(referenced)
            keep.update(question_id for question_id in all_ids
                        if question_id not in referenced and len(keep) < 6)
            self.assertEqual(len(keep), 6)
            conn.executemany("DELETE FROM questions WHERE question_id=?",
                             [(question_id,) for question_id in all_ids
                              if question_id not in keep])
            conn.commit()
        reopened = DemoStore(data_dir=Path(self.temp.name))
        self.assertEqual(reopened.overview()["question_count"], full_count)
        self.assertEqual(reopened.overview()["answer_event_count"], before_events)
        self.assertTrue(any(user["user_id"] == learner["user_id"]
                            for user in reopened.users()))
        self.assertEqual(next(row for row in reopened.answer_matrix()
                              if row["user_id"] == learner["user_id"]
                              and row["question_id"] == "660s1_1_1")["status"], 2)

    def test_simulated_batch_is_atomic_and_types_follow_prior_answers(self):
        for user in self.store.users():
            self.store.delete_user(user["user_id"])
        before = self.store.overview()["counts"]
        result = self.store.generate_simulated_events(30, seed=5)
        self.assertEqual((result["requested_count"], result["inserted_count"],
                          result["synthetic_user_count"]), (30, 30, 3))
        self.assertEqual(result["practice_count"] + result["review_count"], 30)
        self.assertEqual(result["correct_count"] + result["incorrect_count"], 30)
        self.assertEqual(self.store.overview()["answer_event_count"],
                         before["answer_events"] + 30)
        with closing(sqlite3.connect(self.store.db_path)) as conn:
            rows = conn.execute(
                "SELECT user_id,question_id,event_type FROM answer_events "
                "ORDER BY answered_at,event_id").fetchall()
        seen = set()
        for user_id, question_id, event_type in rows:
            pair = (user_id, question_id)
            self.assertEqual(event_type, "review" if pair in seen else "practice")
            seen.add(pair)

    def test_simulated_batch_failure_rolls_back_synthetic_learners(self):
        for user in self.store.users():
            self.store.delete_user(user["user_id"])
        before = self.store.overview()["counts"]
        with closing(sqlite3.connect(self.store.db_path)) as conn:
            conn.execute("CREATE TRIGGER abort_sim BEFORE INSERT ON answer_events "
                         "WHEN NEW.event_id LIKE 'sim-%' BEGIN "
                         "SELECT RAISE(ABORT, 'injected failure'); END")
            conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.generate_simulated_events(3, seed=1)
        self.assertEqual(self.store.overview()["counts"], before)

    def test_distinct_concurrent_events_both_save_despite_reversed_commit_order(self):
        before = self.store.overview()["counts"]
        result = self.store.concurrent_distinct_demo()
        self.assertTrue(result["passed"])
        self.assertEqual(result["commit_order"],
                         ["later_review", "earlier_practice"])
        self.assertEqual(result["row_count"], 2)
        self.assertEqual((result["first_result"], result["latest_status"]), (1, 2))
        self.assertGreater(result["outcomes"][0]["lock_wait_ms"], 50)
        self.assertEqual(self.store.overview()["counts"]["answer_events"],
                         before["answer_events"] + 2)

    def test_distinct_concurrent_failure_cleans_up_partial_test_learner(self):
        before = self.store.overview()["counts"]
        with closing(sqlite3.connect(self.store.db_path)) as conn:
            conn.execute("CREATE TRIGGER abort_earlier_concurrent "
                         "BEFORE INSERT ON answer_events "
                         "WHEN NEW.event_id LIKE 'concurrent-%' "
                         "AND NEW.event_type='practice' BEGIN "
                         "SELECT RAISE(ABORT, 'injected failure'); END")
            conn.commit()
        result = self.store.concurrent_distinct_demo()
        self.assertFalse(result["passed"])
        self.assertTrue(result["cleanup_performed"])
        self.assertTrue(any(item["status"] == "error" for item in result["outcomes"]))
        self.assertEqual(self.store.overview()["counts"], before)

    def test_recovery_deleting_latest_event_recomputes_progress_and_restores(self):
        event = next(row for row in self.store.recovery_candidates()
                     if row["user_id"] == "u001" and row["question_id"] == "660s1_1_2"
                     and row["is_latest"])
        original = next(row for row in self.store.answer_matrix()
                        if row["user_id"] == "u001" and row["question_id"] == "660s1_1_2")
        deleted = self.store.delete_event_for_recovery(event["event_id"])
        self.assertTrue(deleted["passed"])
        self.assertTrue(self.store.has_recovery_backup())
        self.assertEqual(deleted["before_counts"]["answer_events"] - 1,
                         deleted["after_counts"]["answer_events"])
        self.assertEqual((deleted["progress_before"]["status"],
                          deleted["progress_after"]["status"]), (2, 1))
        changed = next(row for row in self.store.answer_matrix()
                       if row["user_id"] == "u001" and row["question_id"] == "660s1_1_2")
        self.assertEqual((changed["first_result"], changed["status"],
                          changed["attempt_count"]), (1, 1, 1))
        reopened = DemoStore(data_dir=Path(self.temp.name))
        self.assertTrue(reopened.has_recovery_backup())
        restored = reopened.restore_recovery_backup()
        self.assertTrue(restored["passed"])
        self.assertEqual(restored["event"]["event_id"], event["event_id"])
        self.assertFalse(reopened.has_recovery_backup())
        self.assertEqual(next(row for row in reopened.answer_matrix()
                              if row["user_id"] == "u001"
                              and row["question_id"] == "660s1_1_2"), original)

    def test_recovery_deleting_nonlatest_event_changes_first_only(self):
        event = next(row for row in self.store.recovery_candidates()
                     if row["user_id"] == "u002" and row["question_id"] == "660s1_1_1"
                     and row["is_first_answer"])
        self.assertFalse(event["is_latest"])
        deleted = self.store.delete_event_for_recovery(event["event_id"])
        self.assertEqual((deleted["progress_before"]["status"],
                          deleted["progress_after"]["status"]), (1, 1))
        changed = next(row for row in self.store.answer_matrix()
                       if row["user_id"] == "u002" and row["question_id"] == "660s1_1_1")
        self.assertEqual((changed["first_result"], changed["status"],
                          changed["attempt_count"]), (1, 1, 2))
        self.assertTrue(self.store.restore_recovery_backup()["passed"])
        restored = next(row for row in self.store.answer_matrix()
                        if row["user_id"] == "u002" and row["question_id"] == "660s1_1_1")
        self.assertEqual((restored["first_result"], restored["status"],
                          restored["attempt_count"]), (2, 1, 3))

    def test_reset_invalidates_pending_recovery_backup(self):
        event_id = self.store.recovery_candidates()[0]["event_id"]
        self.store.delete_event_for_recovery(event_id)
        self.assertTrue(self.store.has_recovery_backup())
        self.store.reset()
        self.assertFalse(self.store.has_recovery_backup())
        with self.assertRaises(FileNotFoundError):
            self.store.restore_recovery_backup()

    def test_recovery_delete_failure_rolls_back_and_cleans_backup(self):
        event_id = self.store.recovery_candidates()[0]["event_id"]
        before = self.store.overview()["counts"]
        with closing(sqlite3.connect(self.store.db_path)) as conn:
            conn.execute("CREATE TRIGGER abort_recovery_delete "
                         "BEFORE DELETE ON answer_events BEGIN "
                         "SELECT RAISE(ABORT, 'injected failure'); END")
            conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.delete_event_for_recovery(event_id)
        self.assertFalse(self.store.has_recovery_backup())
        self.assertFalse(self.store.recovery_manifest_path.exists())
        self.assertEqual(self.store.overview()["counts"], before)

    def test_restore_replaces_changes_made_after_deletion(self):
        event_id = self.store.recovery_candidates()[0]["event_id"]
        before = self.store.overview()["counts"]
        self.store.delete_event_for_recovery(event_id)
        later_user = self.store.add_user("备份之后添加", "660s1_1_1", 1)
        self.assertGreater(self.store.overview()["counts"]["users"], before["users"])
        restored = self.store.restore_recovery_backup()
        self.assertTrue(restored["passed"])
        self.assertEqual(restored["after_counts"], before)
        self.assertFalse(any(user["user_id"] == later_user["user_id"]
                             for user in self.store.users()))


if __name__ == "__main__":
    unittest.main()
