"""Minimal SQLite data layer for accounts and the per-user book library.

Stdlib only. For a small/medium multi-user product this is plenty; swap for
Postgres later by reimplementing these functions. The DB file lives under
BOOKFORGE_DATA — mount a persistent disk there on your host (e.g. Render Disk at
/data with BOOKFORGE_DATA=/data) or accounts reset on every redeploy.
"""
import os
import sqlite3
import time

DATA_DIR = os.environ.get("BOOKFORGE_DATA", "/tmp/bookforge_data")
DB_PATH = os.path.join(DATA_DIR, "bookforge.db")


def _conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init():
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            pw_hash TEXT NOT NULL,
            pw_salt TEXT NOT NULL,
            created REAL NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS books(
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT, author TEXT,
            status TEXT NOT NULL, message TEXT,
            pages INTEGER DEFAULT 0,
            trim TEXT, mode TEXT, font TEXT, art_style TEXT,
            download_path TEXT,
            created REAL NOT NULL,
            updated REAL NOT NULL)""")


# ---- users ----------------------------------------------------------------

def create_user(email, name, pw_hash, pw_salt):
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO users(email,name,pw_hash,pw_salt,created) VALUES(?,?,?,?,?)",
            (email.lower().strip(), name.strip(), pw_hash, pw_salt, time.time()))
        return cur.lastrowid


def get_user_by_email(email):
    with _conn() as c:
        r = c.execute("SELECT * FROM users WHERE email=?", (email.lower().strip(),)).fetchone()
        return dict(r) if r else None


def get_user(user_id):
    with _conn() as c:
        r = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(r) if r else None


# ---- books ----------------------------------------------------------------

def create_book(book_id, user_id, meta, theme):
    with _conn() as c:
        now = time.time()
        c.execute("""INSERT INTO books(id,user_id,title,author,status,message,trim,mode,
                     font,art_style,created,updated)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (book_id, user_id, meta.title, meta.author, "queued", "Queued…",
                   theme.trim, theme.mode, theme.font, theme.art_style, now, now))


def update_book(book_id, **fields):
    if not fields:
        return
    fields["updated"] = time.time()
    cols = ", ".join(f"{k}=?" for k in fields)
    with _conn() as c:
        c.execute(f"UPDATE books SET {cols} WHERE id=?", (*fields.values(), book_id))


def get_book(book_id):
    with _conn() as c:
        r = c.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
        return dict(r) if r else None


def list_books(user_id, limit=100):
    with _conn() as c:
        rows = c.execute("SELECT * FROM books WHERE user_id=? ORDER BY created DESC LIMIT ?",
                         (user_id, limit)).fetchall()
        return [dict(r) for r in rows]
