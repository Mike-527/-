-- 匿名演示样本；由已验证的原 SQLite 样例库导出。
-- 执行顺序：先运行 schema.sql，再运行本文件。
-- user_question_progress 由 answer_events 的触发器自动生成。
BEGIN TRANSACTION;

-- users: 5 rows
INSERT INTO users (user_id, display_name, created_at) VALUES ('u001', '学习者 A', '2026-09-25T08:00:00Z');
INSERT INTO users (user_id, display_name, created_at) VALUES ('u002', '学习者 B', '2026-09-25T08:00:00Z');
INSERT INTO users (user_id, display_name, created_at) VALUES ('u003', '学习者 C', '2026-09-25T08:00:00Z');
INSERT INTO users (user_id, display_name, created_at) VALUES ('u004', '学习者 D', '2026-09-25T08:00:00Z');
INSERT INTO users (user_id, display_name, created_at) VALUES ('u005', '学习者 E', '2026-09-25T08:00:00Z');

-- books: 2 rows
INSERT INTO books (book_id, title, catalog_version) VALUES ('660s1', '小红 · 数一660题', '2027');
INSERT INTO books (book_id, title, catalog_version) VALUES ('bluefriend27s1', '蓝朋友 · 数一1000题', '2027');

-- chapters: 3 rows
INSERT INTO chapters (book_id, chapter_no, title, first_question_no, last_question_no) VALUES ('660s1', 1, '填空题 - 函数、极限、连续', 1, 19);
INSERT INTO chapters (book_id, chapter_no, title, first_question_no, last_question_no) VALUES ('660s1', 2, '填空题 - 导数与微分', 20, 38);
INSERT INTO chapters (book_id, chapter_no, title, first_question_no, last_question_no) VALUES ('bluefriend27s1', 1, '高数 · 零基础', 1, 16);

-- questions: 54 rows
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_1_1', '660s1', 1, 1);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_1_2', '660s1', 1, 2);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_1_3', '660s1', 1, 3);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_1_4', '660s1', 1, 4);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_1_5', '660s1', 1, 5);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_1_6', '660s1', 1, 6);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_1_7', '660s1', 1, 7);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_1_8', '660s1', 1, 8);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_1_9', '660s1', 1, 9);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_1_10', '660s1', 1, 10);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_1_11', '660s1', 1, 11);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_1_12', '660s1', 1, 12);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_1_13', '660s1', 1, 13);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_1_14', '660s1', 1, 14);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_1_15', '660s1', 1, 15);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_1_16', '660s1', 1, 16);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_1_17', '660s1', 1, 17);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_1_18', '660s1', 1, 18);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_1_19', '660s1', 1, 19);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_2_20', '660s1', 2, 20);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_2_21', '660s1', 2, 21);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_2_22', '660s1', 2, 22);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_2_23', '660s1', 2, 23);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_2_24', '660s1', 2, 24);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_2_25', '660s1', 2, 25);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_2_26', '660s1', 2, 26);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_2_27', '660s1', 2, 27);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_2_28', '660s1', 2, 28);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_2_29', '660s1', 2, 29);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_2_30', '660s1', 2, 30);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_2_31', '660s1', 2, 31);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_2_32', '660s1', 2, 32);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_2_33', '660s1', 2, 33);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_2_34', '660s1', 2, 34);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_2_35', '660s1', 2, 35);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_2_36', '660s1', 2, 36);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_2_37', '660s1', 2, 37);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('660s1_2_38', '660s1', 2, 38);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('bluefriend27s1_1_1', 'bluefriend27s1', 1, 1);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('bluefriend27s1_1_2', 'bluefriend27s1', 1, 2);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('bluefriend27s1_1_3', 'bluefriend27s1', 1, 3);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('bluefriend27s1_1_4', 'bluefriend27s1', 1, 4);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('bluefriend27s1_1_5', 'bluefriend27s1', 1, 5);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('bluefriend27s1_1_6', 'bluefriend27s1', 1, 6);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('bluefriend27s1_1_7', 'bluefriend27s1', 1, 7);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('bluefriend27s1_1_8', 'bluefriend27s1', 1, 8);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('bluefriend27s1_1_9', 'bluefriend27s1', 1, 9);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('bluefriend27s1_1_10', 'bluefriend27s1', 1, 10);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('bluefriend27s1_1_11', 'bluefriend27s1', 1, 11);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('bluefriend27s1_1_12', 'bluefriend27s1', 1, 12);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('bluefriend27s1_1_13', 'bluefriend27s1', 1, 13);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('bluefriend27s1_1_14', 'bluefriend27s1', 1, 14);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('bluefriend27s1_1_15', 'bluefriend27s1', 1, 15);
INSERT INTO questions (question_id, book_id, chapter_no, question_no) VALUES ('bluefriend27s1_1_16', 'bluefriend27s1', 1, 16);

-- answer_events: 14 rows
INSERT INTO answer_events (event_id, user_id, question_id, event_type, result, answered_at, wrong_reason, recorded_at) VALUES ('e001', 'u001', '660s1_1_1', 'practice', 1, '2026-09-26T09:00:00Z', NULL, '2026-09-29T01:47:23Z');
INSERT INTO answer_events (event_id, user_id, question_id, event_type, result, answered_at, wrong_reason, recorded_at) VALUES ('e002', 'u002', '660s1_1_1', 'practice', 2, '2026-09-26T09:05:00Z', '概念混淆', '2026-09-29T01:47:23Z');
INSERT INTO answer_events (event_id, user_id, question_id, event_type, result, answered_at, wrong_reason, recorded_at) VALUES ('e003', 'u003', '660s1_1_1', 'practice', 2, '2026-09-26T09:10:00Z', '计算失误', '2026-09-29T01:47:23Z');
INSERT INTO answer_events (event_id, user_id, question_id, event_type, result, answered_at, wrong_reason, recorded_at) VALUES ('e004', 'u004', '660s1_1_1', 'practice', 2, '2026-09-26T09:15:00Z', NULL, '2026-09-29T01:47:23Z');
INSERT INTO answer_events (event_id, user_id, question_id, event_type, result, answered_at, wrong_reason, recorded_at) VALUES ('e005', 'u005', '660s1_1_1', 'practice', 2, '2026-09-26T09:20:00Z', '公式遗忘', '2026-09-29T01:47:23Z');
INSERT INTO answer_events (event_id, user_id, question_id, event_type, result, answered_at, wrong_reason, recorded_at) VALUES ('e006', 'u002', '660s1_1_1', 'review', 1, '2026-09-28T09:00:00Z', NULL, '2026-09-29T01:47:23Z');
INSERT INTO answer_events (event_id, user_id, question_id, event_type, result, answered_at, wrong_reason, recorded_at) VALUES ('e007', 'u001', '660s1_1_2', 'practice', 2, '2026-09-28T10:00:00Z', '粗心', '2026-09-29T01:47:23Z');
INSERT INTO answer_events (event_id, user_id, question_id, event_type, result, answered_at, wrong_reason, recorded_at) VALUES ('e008', 'u003', '660s1_1_2', 'practice', 1, '2026-09-28T10:05:00Z', NULL, '2026-09-29T01:47:23Z');
INSERT INTO answer_events (event_id, user_id, question_id, event_type, result, answered_at, wrong_reason, recorded_at) VALUES ('e009', 'u004', '660s1_1_2', 'practice', 2, '2026-09-28T10:10:00Z', NULL, '2026-09-29T01:47:23Z');
INSERT INTO answer_events (event_id, user_id, question_id, event_type, result, answered_at, wrong_reason, recorded_at) VALUES ('e010', 'u001', '660s1_2_20', 'practice', 2, '2026-09-28T11:00:00Z', NULL, '2026-09-29T01:47:23Z');
INSERT INTO answer_events (event_id, user_id, question_id, event_type, result, answered_at, wrong_reason, recorded_at) VALUES ('e011', 'u002', '660s1_2_20', 'practice', 2, '2026-09-28T11:05:00Z', NULL, '2026-09-29T01:47:23Z');
INSERT INTO answer_events (event_id, user_id, question_id, event_type, result, answered_at, wrong_reason, recorded_at) VALUES ('e012', 'u005', 'bluefriend27s1_1_1', 'practice', 1, '2026-09-28T12:00:00Z', NULL, '2026-09-29T01:47:23Z');
INSERT INTO answer_events (event_id, user_id, question_id, event_type, result, answered_at, wrong_reason, recorded_at) VALUES ('e013', 'u001', '660s1_1_2', 'legacy_practice', 1, '2026-09-27T10:00:00Z', NULL, '2026-09-29T01:47:23Z');
INSERT INTO answer_events (event_id, user_id, question_id, event_type, result, answered_at, wrong_reason, recorded_at) VALUES ('race-u002-q1', 'u002', '660s1_1_1', 'review', 1, '2026-09-29T09:00:00Z', NULL, '2026-09-29T01:47:24Z');

COMMIT;
