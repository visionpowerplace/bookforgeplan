"""Per-job storage. Local filesystem implementation behind a small interface so a
hosted deployment can drop in S3/GCS by implementing the same four methods.
"""
import os
import shutil
import uuid

DATA_ROOT = os.environ.get("BOOKFORGE_DATA", "/tmp/bookforge_data")


class JobStore:
    """One directory per job: uploads/ (input), out/ (deliverable)."""

    def __init__(self, root: str = DATA_ROOT):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def new_job_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def job_dir(self, job_id: str) -> str:
        d = os.path.join(self.root, job_id)
        os.makedirs(os.path.join(d, "uploads"), exist_ok=True)
        os.makedirs(os.path.join(d, "out"), exist_ok=True)
        return d

    def save_upload(self, job_id: str, filename: str, data: bytes) -> str:
        safe = os.path.basename(filename).replace("\\", "_")
        path = os.path.join(self.job_dir(job_id), "uploads", safe)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def output_path(self, job_id: str, filename: str) -> str:
        return os.path.join(self.job_dir(job_id), "out", filename)

    def cleanup(self, job_id: str):
        shutil.rmtree(os.path.join(self.root, job_id), ignore_errors=True)
