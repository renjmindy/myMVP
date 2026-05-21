import queue
import threading
import time
from datetime import datetime

from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Job, _utcnow

# In-memory queue (simulates SQS for prototype)
job_queue: queue.Queue[int] = queue.Queue()


def get_time_bucket(scheduled_at: datetime) -> str:
    """Convert scheduled time to time bucket — used as DB partition key.

    The time bucket groups jobs into hourly windows so the watcher can
    efficiently query only the relevant partition instead of scanning
    the entire jobs table.
    """
    # TODO: Implement this function
    #
    # Design decision: Time-based partitioning for efficient job lookup
    #
    # Hints:
    # 1. Format the datetime into a string that represents an hourly bucket
    # 2. Use strftime with a format like "%Y%m%d%H" (e.g., "2025030114")
    # 3. This bucket string becomes the partition key in the jobs table
    return "0000000000"


def find_due_jobs(current_time: datetime, db: Session) -> list[Job]:
    """Watcher calls every minute: find due jobs in current time bucket.

    Queries the jobs table using the time bucket as a partition key,
    then filters for jobs that are due (scheduled_at <= now) and still
    in 'pending' status.
    """
    # TODO: Implement this function
    #
    # Design decision: Watcher pattern — poll DB for due jobs using
    #   the time bucket as a partition key to avoid full table scans
    #
    # Hints:
    # 1. Compute the current time bucket using get_time_bucket()
    # 2. Query Job where time_bucket matches AND scheduled_at <= current_time
    # 3. Only include jobs with status == "pending"
    # 4. Return the list of matching Job objects
    return []


def watcher_loop(interval: int = 10):
    """Watcher scans DB for due jobs and pushes them to the queue."""
    while True:
        db = SessionLocal()
        try:
            now = _utcnow()
            due_jobs = find_due_jobs(now, db)
            for job in due_jobs:
                job.status = "queued"
                db.commit()
                job_queue.put(job.id)
        finally:
            db.close()
        time.sleep(interval)


def worker_loop():
    """Worker pulls jobs from queue and executes them."""
    while True:
        job_id = job_queue.get()
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job is None or job.status == "cancelled":
                continue

            job.status = "running"
            db.commit()

            # Simulate execution — in production this would call LLM
            job.result = f"Executed: {job.description}"
            job.status = "completed"
            db.commit()
        except Exception as e:
            job.status = "failed"
            job.result = str(e)
            db.commit()
        finally:
            db.close()
            job_queue.task_done()


def start_scheduler():
    """Start watcher and worker threads."""
    watcher = threading.Thread(target=watcher_loop, daemon=True)
    worker = threading.Thread(target=worker_loop, daemon=True)
    watcher.start()
    worker.start()
