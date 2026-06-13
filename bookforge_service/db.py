"""Data layer for accounts and the per-user library.

Persistence-agnostic: if DATABASE_URL is set (e.g. a Render/Neon Postgres) it uses
Postgres; otherwise it falls back to a local SQLite file under BOOKFORGE_DATA. The
rendered PDF bytes are stored in the database, so NO persistent disk is required —
everything survives restarts as long as the database does. Every call opens and
*closes* its own connection so Postgres connection limits aren't exhausted.
"""
import os
import time

DATA_DIR = os.environ.get("BOOKFORGE_DATA", "/tmp/bookforge_data")
DB_PATH = os.path.join(DATA_DIR, "bookforge.db")
DATABASE_URL = os.environ.get("DATABASE_URL")
USE_PG = bool(DATABASE_URL)

if USE_PG:
    import psycopg2
    import psycopg2.extras
    PH = "%s"
else:
    import sqlite3
    PH = "?"


def _connect():
    if USE_PG:
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        return psycopg2.connect(url)
    os.makedirs(DATA_DIR, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def _cur(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) if USE_PG else conn.cursor()


def _binary(b):
    if b is None:
        return None
    return psycopg2.Binary(b) if USE_PG else sqlite3.Binary(b)


def _exec(sql, params=(), fetch=None):
    """Run a statement on a fresh connection that is always closed.
    fetch: None | 'one' | 'all' | 'id' (lastrowid / RETURNING id)."""
    conn = _connect()
    try:
        c = _cur(conn)
        c.execute(sql, params)
        if fetch == "one":
            r = c.fetchone()
            out = dict(r) if r else None
        elif fetch == "all":
            out = [dict(r) for r in c.fetchall()]
        elif fetch == "id":
            out = c.fetchone()["id"] if USE_PG else c.lastrowid
        else:
            out = None
        conn.commit()
        return out
    finally:
        conn.close()


def init():
    uid_type = "SERIAL PRIMARY KEY" if USE_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    blob = "BYTEA" if USE_PG else "BLOB"
    real = "DOUBLE PRECISION" if USE_PG else "REAL"
    _exec(f"""CREATE TABLE IF NOT EXISTS users(
        id {uid_type}, email TEXT UNIQUE NOT NULL, name TEXT,
        pw_hash TEXT NOT NULL, pw_salt TEXT NOT NULL, created {real} NOT NULL)""")
    _exec(f"""CREATE TABLE IF NOT EXISTS books(
        id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, title TEXT, author TEXT,
        status TEXT NOT NULL, message TEXT, pages INTEGER DEFAULT 0,
        trim TEXT, mode TEXT, font TEXT, art_style TEXT, pdf {blob},
        created {real} NOT NULL, updated {real} NOT NULL)""")


# ---- users ----------------------------------------------------------------

def create_user(email, name, pw_hash, pw_salt):
    args = (email.lower().strip(), name.strip(), pw_hash, pw_salt, time.time())
    sql = f"INSERT INTO users(email,name,pw_hash,pw_salt,created) VALUES({PH},{PH},{PH},{PH},{PH})"
    if USE_PG:
        sql += " RETURNING id"
    return _exec(sql, args, fetch="id")


def get_user_by_email(email):
    return _exec(f"SELECT * FROM users WHERE email={PH}", (email.lower().strip(),), fetch="one")


def get_user(user_id):
    return _exec(f"SELECT * FROM users WHERE id={PH}", (user_id,), fetch="one")


# ---- books ----------------------------------------------------------------

_COLS = "id,user_id,title,author,status,message,pages,trim,mode,font,art_style,created,updated"


def create_book(book_id, user_id, meta, theme):
    now = time.time()
    _exec(f"INSERT INTO books(id,user_id,title,author,status,message,trim,mode,font,art_style,created,updated) "
          f"VALUES({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
          (book_id, user_id, meta.title, meta.author, "queued", "Queued…",
           theme.trim, theme.mode, theme.font, theme.art_style, now, now))


def update_book(book_id, **fields):
    if not fields:
        return
    fields["updated"] = time.time()
    if "pdf" in fields:
        fields["pdf"] = _binary(fields["pdf"])
    cols = ", ".join(f"{k}={PH}" for k in fields)
    _exec(f"UPDATE books SET {cols} WHERE id={PH}", (*fields.values(), book_id))


def get_book(book_id):
    return _exec(f"SELECT {_COLS} FROM books WHERE id={PH}", (book_id,), fetch="one")


def get_book_pdf(book_id):
    r = _exec(f"SELECT pdf FROM books WHERE id={PH}", (book_id,), fetch="one")
    if not r or r["pdf"] is None:
        return None
    return bytes(r["pdf"])


def list_books(user_id, limit=100):
    return _exec(f"SELECT {_COLS} FROM books WHERE user_id={PH} ORDER BY created DESC LIMIT {PH}",
                 (user_id, limit), fetch="all")
