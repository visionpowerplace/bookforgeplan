"""BookForge cloud service — a thin, runnable web layer over the formatting engine.

Authors upload a .docx + metadata; the engine renders a print-ready PDF in a
background worker; the client polls for status and downloads the result.

The two abstractions (storage.py, jobs.py) are deliberately swappable: local disk
-> S3, and an in-process thread pool -> Celery/RQ + Redis, without touching app.py.
"""
__version__ = "0.1.0"
