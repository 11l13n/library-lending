-- ==========================================
-- Учёт выдачи книг: SQL-запросы проекта
-- ==========================================
-- Знак ? - параметр: значение передаётся из Python отдельно от текста
-- запроса (conn.execute(query, [value])). Для проверки в SQLite CLI
-- задайте параметр командой .param set ?1 'значение' или подставьте
-- значение вручную.
-- Срок выдачи - 14 дней, штраф - 10 руб. за день просрочки
-- (константы LOAN_PERIOD_DAYS и FINE_PER_DAY в models/loans.py).


-- ------------------------------------------
-- Выборка списков
-- ------------------------------------------

-- 1. Каталог книг по алфавиту.
SELECT
    id,
    title,
    author
FROM books
ORDER BY title, id;

-- 2. Список читателей.
SELECT
    id,
    name,
    ticket
FROM readers
ORDER BY name;


-- ------------------------------------------
-- Фильтрация (WHERE)
-- ------------------------------------------

-- 3. Карточка книги по идентификатору (страница /books/<id>/).
SELECT
    id,
    title,
    author
FROM books
WHERE id = ?;

-- 4. Поиск книг по части названия или автора без учёта регистра
--    (страница /books/search/). casefold() - функция Python,
--    её регистрирует db.database.get_connection(); в SQLite CLI для
--    латиницы можно использовать LOWER().
SELECT
    id,
    title,
    author
FROM books
WHERE casefold(title) LIKE '%' || casefold(?) || '%'
   OR casefold(author) LIKE '%' || casefold(?) || '%'
ORDER BY title;

-- 5. Книги, доступные на выбранную дату (страница /books/available/).
--    Два параметра - одна дата ГГГГ-ММ-ДД. В день фактического возврата
--    экземпляр уже доступен; будущая выдача не занимает его раньше времени.
SELECT
    id,
    title,
    author
FROM books
WHERE id NOT IN (
    SELECT book_id
    FROM loans
    WHERE issue_date <= ?
      AND (return_date IS NULL OR return_date > ?)
)
ORDER BY title;


-- ------------------------------------------
-- Соединение таблиц (JOIN)
-- ------------------------------------------

-- 6. Каталог с отметкой о текущей выдаче (страница /books/).
--    LEFT JOIN сохраняет книги без активной выдачи: для них
--    active_loan_id = NULL.
SELECT
    books.id,
    books.title,
    books.author,
    loans.id AS active_loan_id
FROM books
LEFT JOIN loans
    ON loans.book_id = books.id
    AND loans.return_date IS NULL
ORDER BY books.title, books.id;

-- 7. Текущие выдачи: книга, читатель, даты (страница /loans/).
SELECT
    loans.id,
    books.title AS book_title,
    readers.name AS reader_name,
    readers.ticket,
    strftime('%d.%m.%Y', loans.issue_date) AS issue_date,
    strftime('%d.%m.%Y', date(loans.issue_date, '+14 days')) AS due_date
FROM loans
JOIN books ON loans.book_id = books.id
JOIN readers ON loans.reader_id = readers.id
WHERE loans.return_date IS NULL
ORDER BY loans.issue_date;

-- 8. Просроченные на выбранную дату выдачи и сумма штрафа
--    (страница /loans/overdue/?date=ГГГГ-ММ-ДД); все четыре параметра -
--    одна и та же дата.
SELECT
    loans.id,
    books.title AS book_title,
    readers.name AS reader_name,
    readers.ticket,
    strftime('%d.%m.%Y', date(loans.issue_date, '+14 days')) AS due_date,
    CAST(julianday(?) - julianday(loans.issue_date, '+14 days')
         AS INTEGER) AS overdue_days,
    CAST(julianday(?) - julianday(loans.issue_date, '+14 days')
         AS INTEGER) * 10 AS fine
FROM loans
JOIN books ON loans.book_id = books.id
JOIN readers ON loans.reader_id = readers.id
WHERE (loans.return_date IS NULL OR loans.return_date > ?)
  AND date(loans.issue_date, '+14 days') < ?
ORDER BY overdue_days DESC;

-- 9. Полная информация о выдаче и дни просрочки на сегодня
--    (страница /loans/<id>/; параметры: сегодняшняя дата, номер выдачи).
SELECT
    loans.id,
    loans.book_id,
    books.title AS book_title,
    books.author,
    readers.name AS reader_name,
    readers.ticket,
    strftime('%d.%m.%Y', loans.issue_date) AS issue_date,
    strftime('%d.%m.%Y', date(loans.issue_date, '+14 days')) AS due_date,
    strftime('%d.%m.%Y', loans.return_date) AS return_date,
    MAX(
        CAST(julianday(COALESCE(loans.return_date, ?))
             - julianday(loans.issue_date, '+14 days') AS INTEGER),
        0
    ) AS overdue_days
FROM loans
JOIN books ON loans.book_id = books.id
JOIN readers ON loans.reader_id = readers.id
WHERE loans.id = ?;

-- 10. История выдач книги: кто и когда брал (страница /books/<id>/).
SELECT
    loans.id,
    readers.name AS reader_name,
    strftime('%d.%m.%Y', loans.issue_date) AS issue_date,
    strftime('%d.%m.%Y', date(loans.issue_date, '+14 days')) AS due_date,
    strftime('%d.%m.%Y', loans.return_date) AS return_date
FROM loans
JOIN readers ON loans.reader_id = readers.id
WHERE loans.book_id = ?
ORDER BY loans.issue_date DESC;


-- ------------------------------------------
-- Агрегатные функции
-- ------------------------------------------

-- 11. Сводка библиотеки: книги, выдачи, сколько книг сейчас у читателей
--     (страница /loans/statistics/).
SELECT
    (SELECT COUNT(*) FROM books) AS books_count,
    (SELECT COUNT(*) FROM readers) AS readers_count,
    COUNT(*) AS loans_count,
    COUNT(*) - COUNT(return_date) AS issued_count
FROM loans;

-- 12. Средний срок пользования книгой и самый долгий возврат
--     (по завершённым выдачам).
SELECT
    ROUND(AVG(julianday(return_date) - julianday(issue_date)), 1)
        AS avg_days,
    MAX(julianday(return_date) - julianday(issue_date)) AS max_days
FROM loans
WHERE return_date IS NOT NULL;


-- ------------------------------------------
-- Группировка (GROUP BY) и фильтрация групп (HAVING)
-- ------------------------------------------

-- 13. Популярность книг: сколько раз выдавали каждый экземпляр.
--     LEFT JOIN оставляет книги, которые ни разу не выдавали (0).
SELECT
    books.id,
    books.title,
    books.author,
    COUNT(loans.id) AS loans_count
FROM books
LEFT JOIN loans ON loans.book_id = books.id
GROUP BY books.id, books.title, books.author
ORDER BY loans_count DESC, books.title;

-- 14. Читатели: всего выдач, книг на руках, штраф за просрочки
--     на выбранную дату (страница /loans/readers/).
SELECT
    readers.id,
    readers.name,
    readers.ticket,
    COUNT(loans.id) AS loans_count,
    COUNT(loans.id) - COUNT(loans.return_date) AS on_hands,
    COALESCE(SUM(
        MAX(
            CAST(julianday(COALESCE(loans.return_date, ?))
                 - julianday(loans.issue_date, '+14 days') AS INTEGER),
            0
        )
    ), 0) * 10 AS fine
FROM readers
LEFT JOIN loans ON loans.reader_id = readers.id
GROUP BY readers.id, readers.name, readers.ticket
ORDER BY loans_count DESC, readers.name;

-- 15. Выдачи по месяцам.
SELECT
    strftime('%Y-%m', issue_date) AS month,
    COUNT(*) AS loans_count
FROM loans
GROUP BY month
ORDER BY month;

-- 16. Активные читатели: взяли книг больше заданного числа.
SELECT
    readers.name,
    COUNT(loans.id) AS loans_count
FROM readers
JOIN loans ON loans.reader_id = readers.id
GROUP BY readers.id, readers.name
HAVING COUNT(loans.id) > ?
ORDER BY loans_count DESC;

-- 17. Авторы, книги которых выдавали чаще одного раза.
SELECT
    books.author,
    COUNT(loans.id) AS loans_count
FROM books
JOIN loans ON loans.book_id = books.id
GROUP BY books.author
HAVING COUNT(loans.id) > 1
ORDER BY loans_count DESC;
