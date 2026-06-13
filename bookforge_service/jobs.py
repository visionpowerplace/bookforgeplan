"""Background render jobs. WeasyPrint is blocking, so renders run in a thread pool.
Results (status, message, page count, and the PDF bytes) are written to the database,
so they survive restarts with no persistent disk. For multi-worker scale, swap the
pool for Celery/RQ.
"""
import os
import traceback
from concurrent.futures import ThreadPoolExecutor

from pypdf import PdfReader

from .storage import JobStore
from . import db
from bookforge.model import BookMeta
from bookforge.theme import Theme
from bookforge.build import build_book

MAX_WORKERS = 2


class JobManager:
    def __init__(self, store: JobStore):
        self.store = store
        self._pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    def submit(self, book_id, docx_path, meta, theme):
        self._pool.submit(self._run, book_id, docx_path, meta, theme)

    def _run(self, book_id, docx_path, meta, theme):
        db.update_book(book_id, status="rendering", message="Setting type & paginating…")
        try:
            out_path = self.store.output_path(book_id, "book.pdf")
            book = build_book(docx_path, out_path, meta, theme, verbose=False)
            with open(out_path, "rb") as f:
                pdf = f.read()
            try:
                pages = len(PdfReader(out_path).pages)
            except Exception:
                pages = 0
            msg = f"{len(book.chapters)} chapter(s) formatted"
            if book.notes:
                msg += f" — {book.notes}"
            db.update_book(book_id, status="done", message=msg, pages=pages, pdf=pdf)
            for p in (docx_path, out_path):       # transient files; data now lives in the DB
                try: os.remove(p)
                except OSError: pass
        except Exception as e:
            db.update_book(book_id, status="error", message=f"{type(e).__name__}: {e}")
            traceback.print_exc()
