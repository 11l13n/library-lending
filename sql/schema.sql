-- ==========================================
-- Учёт выдачи книг: структура базы данных
-- ==========================================

-- Экземпляры книг каталога.
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT NOT NULL
);

-- Читатели; номер читательского билета не повторяется.
CREATE TABLE IF NOT EXISTS readers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    ticket TEXT NOT NULL UNIQUE
);

-- Выдачи. return_date = NULL означает, что книга ещё у читателя.
CREATE TABLE IF NOT EXISTS loans (
    id INTEGER PRIMARY KEY,
    book_id INTEGER NOT NULL,
    reader_id INTEGER NOT NULL,
    issue_date TEXT NOT NULL,
    return_date TEXT,
    FOREIGN KEY (book_id) REFERENCES books(id),
    FOREIGN KEY (reader_id) REFERENCES readers(id)
);
