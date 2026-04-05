"""
Cleanup automation: deletes cover letters and optimized resumes for all applied jobs.
Invoked daily by cron (see crontab).
"""

import os
import sys
import logging

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(PROJECT_ROOT, "cleanup.log")),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def run():
    log.info("=== Cleanup run started ===")
    from src.database import supabase_client

    result = supabase_client.cleanup_applied_job_files()
    log.info(
        f"Deleted {result['deleted_cover_letters']} cover letter(s) and "
        f"{result['deleted_resumes']} optimized resume(s) for applied jobs."
    )
    log.info("=== Cleanup run complete ===")


if __name__ == "__main__":
    run()
