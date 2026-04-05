import unittest
from unittest.mock import patch, MagicMock
from src.utils.email_notifier import EmailNotifier

SAMPLE_JOB = {
    "id": "job-001",
    "title": "Python Engineer",
    "company": "TechCorp",
    "location": "Remote",
    "url": "https://example.com/job/001",
    "fit_score": 82,
    "analysis": {
        "recommendation": "apply",
        "summary": "Strong match for this role.",
        "matching_skills": ["Python", "FastAPI"],
        "missing_skills": ["Docker"],
        "key_requirements": ["3+ years Python", "REST APIs"],
    },
}

LOW_SCORE_JOB = {**SAMPLE_JOB, "id": "job-002", "title": "DevOps Lead", "fit_score": 30}


def _make_notifier():
    return EmailNotifier(
        sender_email="sender@example.com",
        sender_password="password",
    )


class TestEmailHTML(unittest.TestCase):
    def test_instant_alert_contains_job_title(self):
        notifier = _make_notifier()
        html = notifier._build_alert_html(SAMPLE_JOB)
        self.assertIn("Python Engineer", html)
        self.assertIn("TechCorp", html)

    def test_instant_alert_contains_skills(self):
        notifier = _make_notifier()
        html = notifier._build_alert_html(SAMPLE_JOB)
        self.assertIn("FastAPI", html)
        self.assertIn("Docker", html)

    def test_instant_alert_contains_fit_score(self):
        notifier = _make_notifier()
        html = notifier._build_alert_html(SAMPLE_JOB)
        self.assertIn("82", html)

    def test_digest_html_sorts_by_score(self):
        notifier = _make_notifier()
        jobs = [LOW_SCORE_JOB, SAMPLE_JOB]
        html = notifier._build_digest_html(jobs, threshold=0)
        # higher score job should appear first
        idx_high = html.find("Python Engineer")
        idx_low = html.find("DevOps Lead")
        self.assertLess(idx_high, idx_low)

    def test_digest_filters_below_threshold(self):
        notifier = _make_notifier()
        jobs = [SAMPLE_JOB, LOW_SCORE_JOB]
        html = notifier._build_digest_html(jobs, threshold=70)
        self.assertIn("Python Engineer", html)
        self.assertNotIn("DevOps Lead", html)

    def test_digest_empty_after_filtering(self):
        notifier = _make_notifier()
        html = notifier._build_digest_html([LOW_SCORE_JOB], threshold=70)
        self.assertIn("No jobs", html)

    def test_job_with_no_analysis_renders(self):
        notifier = _make_notifier()
        bare_job = {"title": "Dev", "company": "Co", "fit_score": 75, "url": "https://example.com"}
        html = notifier._build_alert_html(bare_job)
        self.assertIn("Dev", html)


class TestEmailSend(unittest.TestCase):
    def _mock_smtp(self):
        mock_server = MagicMock()
        mock_smtp_cls = MagicMock(return_value=mock_server)
        mock_server.__enter__ = MagicMock(return_value=mock_server)
        mock_server.__exit__ = MagicMock(return_value=False)
        return mock_smtp_cls, mock_server

    def test_send_instant_alert_calls_sendmail(self):
        notifier = _make_notifier()
        mock_cls, mock_server = self._mock_smtp()
        with patch("smtplib.SMTP_SSL", mock_cls):
            notifier.send_instant_alert("recipient@example.com", SAMPLE_JOB)
        mock_server.sendmail.assert_called_once()

    def test_send_digest_calls_sendmail_when_jobs_pass_threshold(self):
        notifier = _make_notifier()
        mock_cls, mock_server = self._mock_smtp()
        with patch("smtplib.SMTP_SSL", mock_cls):
            notifier.send_job_digest("recipient@example.com", [SAMPLE_JOB], threshold=70)
        mock_server.sendmail.assert_called_once()

    def test_send_digest_skips_send_when_no_jobs_pass_threshold(self):
        notifier = _make_notifier()
        mock_cls, mock_server = self._mock_smtp()
        with patch("smtplib.SMTP_SSL", mock_cls):
            notifier.send_job_digest("recipient@example.com", [LOW_SCORE_JOB], threshold=70)
        mock_server.sendmail.assert_not_called()


if __name__ == "__main__":
    unittest.main()
