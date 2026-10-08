-- QUERY 1 | 单表查询：按章节查题号
SELECT question_id, question_no
FROM questions
WHERE book_id = '660s1' AND chapter_no = 1
ORDER BY question_no;

-- QUERY 2 | 多表连接：第 1 题的匿名作答时间线
SELECT e.event_id, u.display_name, b.title AS book_title,
       c.title AS chapter_title, e.event_type,
       CASE e.result WHEN 1 THEN '会' ELSE '不会' END AS self_marked_result,
       e.answered_at
FROM answer_events AS e
JOIN users AS u ON u.user_id = e.user_id
JOIN questions AS q ON q.question_id = e.question_id
JOIN chapters AS c ON c.book_id = q.book_id AND c.chapter_no = q.chapter_no
JOIN books AS b ON b.book_id = q.book_id
WHERE e.question_id = '660s1_1_1'
ORDER BY e.answered_at, e.event_id;

-- QUERY 3 | 分组统计与排序：样本不少于 2 人的难题排名
SELECT q.question_id, c.title AS chapter_title,
       d.distinct_user_count, d.first_correct_count,
       d.difficulty_coefficient
FROM v_question_difficulty AS d
JOIN questions AS q ON q.question_id = d.question_id
JOIN chapters AS c ON c.book_id = q.book_id AND c.chapter_no = q.chapter_no
WHERE d.distinct_user_count >= 2
ORDER BY d.difficulty_coefficient ASC, d.distinct_user_count DESC, q.question_id;

-- QUERY 4 | 分组统计：每名用户完成题数及全部作答的自评正确率
WITH attempts AS (
    SELECT user_id, COUNT(*) AS attempt_count,
           SUM(CASE WHEN result = 1 THEN 1 ELSE 0 END) AS correct_attempt_count
    FROM answer_events GROUP BY user_id
), completed AS (
    SELECT user_id, COUNT(*) AS completed_question_count
    FROM user_question_progress WHERE status IN (1, 2) GROUP BY user_id
)
SELECT u.user_id, u.display_name,
       COALESCE(c.completed_question_count, 0) AS completed_question_count,
       COALESCE(a.attempt_count, 0) AS attempt_count,
       COALESCE(a.correct_attempt_count, 0) AS correct_attempt_count,
       ROUND(1.0 * a.correct_attempt_count / NULLIF(a.attempt_count, 0), 3) AS personal_accuracy
FROM users AS u
LEFT JOIN attempts AS a ON a.user_id = u.user_id
LEFT JOIN completed AS c ON c.user_id = u.user_id
ORDER BY completed_question_count DESC, u.user_id;

-- QUERY 5 | 多表分组：各章节按首答人数加权的难度系数
SELECT b.title AS book_title, c.chapter_no, c.title AS chapter_title,
       COUNT(q.question_id) AS chapter_question_count,
       SUM(d.distinct_user_count) AS first_answer_count,
       SUM(d.first_correct_count) AS first_correct_count,
       ROUND(1.0 * SUM(d.first_correct_count)
             / NULLIF(SUM(d.distinct_user_count), 0), 3) AS chapter_difficulty_coefficient
FROM chapters AS c
JOIN books AS b ON b.book_id = c.book_id
JOIN questions AS q ON q.book_id = c.book_id AND q.chapter_no = c.chapter_no
JOIN v_question_difficulty AS d ON d.question_id = q.question_id
GROUP BY c.book_id, c.chapter_no
HAVING SUM(d.distinct_user_count) > 0
ORDER BY chapter_difficulty_coefficient ASC, b.title, c.chapter_no;

-- QUERY 6 | 条件筛选：结合个人状态和群体难度给学习者 A 推荐题目
SELECT q.question_id, c.title AS chapter_title,
       COALESCE(p.status, 0) AS personal_status,
       d.distinct_user_count, d.difficulty_coefficient,
       CASE
           WHEN p.status = 2 THEN '先复习错题'
           WHEN p.status IS NULL AND d.distinct_user_count >= 2
                AND d.difficulty_coefficient <= 0.4 THEN '再挑战高难新题'
           WHEN p.status IS NULL THEN '尚未作答'
           ELSE '已经掌握，按计划巩固'
       END AS guidance
FROM questions AS q
JOIN chapters AS c ON c.book_id = q.book_id AND c.chapter_no = q.chapter_no
JOIN v_question_difficulty AS d ON d.question_id = q.question_id
LEFT JOIN user_question_progress AS p
       ON p.question_id = q.question_id AND p.user_id = 'u001'
WHERE q.book_id = '660s1'
ORDER BY CASE WHEN p.status = 2 THEN 0 WHEN p.status IS NULL THEN 1 ELSE 2 END,
         d.difficulty_coefficient ASC, q.question_id
LIMIT 5;
