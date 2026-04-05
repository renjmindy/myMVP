"""
Daily job digest scheduler.
Runs scrape → score → send email digest.
Invoked by cron at 3am and 3pm Pacific time.
"""

import os
import sys
import logging
from datetime import datetime

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load .env
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(PROJECT_ROOT, "scheduler.log")),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def run():
    log.info("=== Scheduler run started ===")

    from src.database import supabase_client
    from src.agents.job_scraper import JobScraper
    from src.agents.ai_agent import JobAnalysisAgent
    from src.utils.email_notifier import EmailNotifier

    settings = supabase_client.get_user_settings()
    keywords = settings.get("keywords") or []
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    location = settings.get("location", "Remote")
    resume_text = settings.get("resume_text", "")
    recipient = settings.get("email", "")
    threshold = int(settings.get("notify_threshold", 0))
    excluded = settings.get("excluded_companies") or []

    smtp_email = os.getenv("SMTP_EMAIL", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")

    if not keywords:
        log.warning("No keywords configured — skipping scrape.")
        return
    if not recipient:
        log.warning("No recipient email configured — skipping digest.")
        return
    if not smtp_email or not smtp_password:
        log.warning("SMTP credentials missing — skipping digest.")
        return

    # Step 1: Scrape
    log.info(f"Scraping LinkedIn for: {keywords} in {location}")
    target = settings.get("target_companies") or []
    scraper = JobScraper()
    new_jobs = scraper.run_scrape(keywords, location, excluded_companies=excluded, target_companies=target)
    log.info(f"Scraped {len(new_jobs)} new job(s).")

    if not new_jobs:
        log.info("No new jobs found — sending empty digest.")
        EmailNotifier(sender_email=smtp_email, sender_password=smtp_password).send_job_digest(
            recipient, [], subject_prefix="Job Digest", threshold=threshold
        )
        return

    # Step 2: Score
    if resume_text:
        log.info("Scoring jobs with GPT-4o-mini...")
        analyzer = JobAnalysisAgent()
        scored = analyzer.batch_analyze(new_jobs, resume_text)
        log.info("Scoring complete.")
    else:
        log.warning("No resume found — skipping scoring.")
        scored = new_jobs

    # Step 3: Send digest
    qualifying = [j for j in scored if (j.get("fit_score") or 0) >= threshold]
    log.info(f"Sending digest to {recipient} — {len(qualifying)} job(s) above threshold {threshold}.")
    try:
        notifier = EmailNotifier(sender_email=smtp_email, sender_password=smtp_password)
        notifier.send_job_digest(
            recipient, scored,
            subject_prefix="Job Digest",
            threshold=threshold,
        )
        log.info("Digest sent successfully.")
    except Exception as e:
        log.error(f"Failed to send digest: {e}")

    log.info("=== Scheduler run complete ===")


if __name__ == "__main__":
    run()
