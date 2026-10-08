PRAGMA foreign_keys = ON;

-- 课程演示使用 SQLite；正式微信小程序仍使用 CloudBase 文档数据库。
-- 用户 ID 为脱敏演示编号，不保存微信 OpenID。
CREATE TABLE users (
    user_id TEXT PRIMARY KEY CHECK (length(user_id) BETWEEN 1 AND 80),
    display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
    created_at TEXT NOT NULL CHECK (created_at GLOB '????-??-??T??:??:??Z')
);

CREATE TABLE books (
    book_id TEXT PRIMARY KEY CHECK (length(book_id) BETWEEN 1 AND 80),
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    catalog_version TEXT NOT NULL
);

CREATE TABLE chapters (
    book_id TEXT NOT NULL,
    chapter_no INTEGER NOT NULL CHECK (chapter_no > 0),
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    first_question_no INTEGER NOT NULL CHECK (first_question_no > 0),
    last_question_no INTEGER NOT NULL CHECK (last_question_no >= first_question_no),
    PRIMARY KEY (book_id, chapter_no),
    FOREIGN KEY (book_id) REFERENCES books(book_id) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE questions (
    question_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    chapter_no INTEGER NOT NULL,
    question_no INTEGER NOT NULL CHECK (question_no > 0),
    UNIQUE (book_id, chapter_no, question_no),
    CHECK (question_id = book_id || '_' || chapter_no || '_' || question_no),
    FOREIGN KEY (book_id, chapter_no) REFERENCES chapters(book_id, chapter_no)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

-- 1/2 对应小程序的“会/不会”自评。事件不覆盖旧事件，保留重做与复习轨迹。
CREATE TABLE answer_events (
    event_id TEXT PRIMARY KEY CHECK (length(event_id) BETWEEN 1 AND 128),
    user_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('practice', 'review', 'legacy_practice')),
    result INTEGER NOT NULL CHECK (result IN (1, 2)),
    answered_at TEXT NOT NULL CHECK (answered_at GLOB '????-??-??T??:??:??Z'),
    wrong_reason TEXT CHECK (wrong_reason IS NULL OR length(wrong_reason) <= 200),
    recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (question_id) REFERENCES questions(question_id) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- 完成状态随最新发生时间更新；较晚导入的历史事件不能覆盖当前状态。
CREATE TABLE user_question_progress (
    user_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    status INTEGER NOT NULL DEFAULT 0 CHECK (status IN (0, 1, 2)),
    last_answered_at TEXT,
    last_event_id TEXT,
    PRIMARY KEY (user_id, question_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (question_id) REFERENCES questions(question_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (last_event_id) REFERENCES answer_events(event_id) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TRIGGER trg_answer_updates_progress
AFTER INSERT ON answer_events
BEGIN
    INSERT INTO user_question_progress (user_id, question_id, status, last_answered_at, last_event_id)
    VALUES (NEW.user_id, NEW.question_id, NEW.result, NEW.answered_at, NEW.event_id)
    ON CONFLICT (user_id, question_id) DO UPDATE SET
        status = excluded.status,
        last_answered_at = excluded.last_answered_at,
        last_event_id = excluded.last_event_id
    WHERE excluded.last_answered_at > user_question_progress.last_answered_at
       OR (excluded.last_answered_at = user_question_progress.last_answered_at
           AND excluded.last_event_id > user_question_progress.last_event_id);
END;

CREATE INDEX idx_questions_chapter ON questions(book_id, chapter_no, question_no);
CREATE INDEX idx_events_user_question_time ON answer_events(user_id, question_id, answered_at, event_id);
CREATE INDEX idx_events_question_time ON answer_events(question_id, answered_at, event_id);
CREATE INDEX idx_progress_user_status ON user_question_progress(user_id, status, question_id);

-- 窗口函数确保每人每题只保留最早一次有效作答；同时间用事件 ID 稳定排序。
CREATE VIEW v_first_answers AS
SELECT event_id, user_id, question_id, result, answered_at
FROM (
    SELECT e.event_id, e.user_id, e.question_id, e.result, e.answered_at,
           ROW_NUMBER() OVER (
               PARTITION BY e.user_id, e.question_id
               ORDER BY e.answered_at ASC, e.event_id ASC
           ) AS row_no
    FROM answer_events AS e
) AS ranked
WHERE row_no = 1;

-- 系数是“首答正确比例”，越小代表样本中的题目越难；零样本显示 NULL。
CREATE VIEW v_question_difficulty AS
SELECT q.question_id, q.book_id, q.chapter_no, q.question_no,
       COUNT(f.event_id) AS distinct_user_count,
       COALESCE(SUM(CASE WHEN f.result = 1 THEN 1 ELSE 0 END), 0) AS first_correct_count,
       CASE WHEN COUNT(f.event_id) = 0 THEN NULL
            ELSE ROUND(1.0 * SUM(CASE WHEN f.result = 1 THEN 1 ELSE 0 END)
                       / COUNT(f.event_id), 4)
       END AS difficulty_coefficient
FROM questions AS q
LEFT JOIN v_first_answers AS f ON f.question_id = q.question_id
GROUP BY q.question_id, q.book_id, q.chapter_no, q.question_no;
