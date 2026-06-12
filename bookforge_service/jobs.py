"""Background render jobs. WeasyPrint is blocking, so renders run in a thread pool.
Job state is persisted to the books table (db.py) so it survives across requests and
is tied to a user's library. For multi-worker scale, swap the pool for Celery/RQ.
"""
import traceback
from concurrent.futures import ThreadPoolExecutor

from .storage import JobStore
from . import db
from bookforge.model import BookMeta
from bookforge.theme import Theme
from bookforge.build import build_book

MAX_WORKERS = 2          # WeasyPrint is heavy; keep modest per CPU


class JobManager:
    def __init__(self, store: JobStore):
        self.store = store
        self._pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    def submit(self, book_id: str, docx_path: str, meta: BookMeta, theme: Theme):
        self._pool.submit(self._run, book_id, docx_path, meta, theme)

    def _run(self, book_id, docx_path, meta, theme):
        db.update_book(book_id, status="rendering", message="Setting type & paginating…")
        try:
            out_path = self.store.output_path(book_id, "book.pdf")
            book = build_book(docx_path, out_path, meta, theme, verbose=False)
            msg = f"{len(book.chapters)} chapter(s) formatted"
            if book.notes:
                msg += f" — {book.notes}"
            db.update_book(book_id, status="done", message=msg,
                           pages=0, download_path=out_path)
        except Exception as e:
            db.update_book(book_id, status="error", message=f"{type(e).__name__}: {e}")
            traceback.print_exc()
