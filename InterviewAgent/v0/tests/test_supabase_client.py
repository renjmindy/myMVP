import unittest
from unittest.mock import patch


def _reset_client():
    """Force the module to re-evaluate connection state."""
    import src.database.supabase_client as sc
    sc._client = None
    sc._mock_mode = False


class TestMockMode(unittest.TestCase):
    def setUp(self):
        _reset_client()

    def test_mock_mode_active_when_no_env_vars(self):
        with patch.dict("os.environ", {}, clear=True):
            import src.database.supabase_client as sc
            sc._client = None
            sc._mock_mode = False
            client = sc.get_client()
            self.assertIsNone(client)
            self.assertTrue(sc.is_mock_mode())

    def test_get_jobs_returns_mock_data_in_mock_mode(self):
        with patch.dict("os.environ", {}, clear=True):
            import src.database.supabase_client as sc
            sc._client = None
            sc._mock_mode = True
            jobs = sc.get_jobs()
            self.assertIsInstance(jobs, list)
            self.assertGreater(len(jobs), 0)
            self.assertIn("title", jobs[0])

    def test_get_jobs_filters_by_status_in_mock_mode(self):
        import src.database.supabase_client as sc
        sc._client = None
        sc._mock_mode = True
        jobs = sc.get_jobs({"status": ["new"]})
        for job in jobs:
            self.assertEqual(job["status"], "new")

    def test_get_jobs_filters_by_min_score_in_mock_mode(self):
        import src.database.supabase_client as sc
        sc._client = None
        sc._mock_mode = True
        jobs = sc.get_jobs({"min_fit_score": 70})
        for job in jobs:
            self.assertGreaterEqual(job.get("fit_score", 0), 70)

    def test_get_jobs_keyword_filter_in_mock_mode(self):
        import src.database.supabase_client as sc
        sc._client = None
        sc._mock_mode = True
        jobs = sc.get_jobs({"keyword": "python"})
        # all returned jobs should mention python somewhere
        for job in jobs:
            text = (
                (job.get("title") or "")
                + (job.get("company") or "")
                + (job.get("description") or "")
            ).lower()
            self.assertIn("python", text)

    def test_get_user_settings_returns_dict_in_mock_mode(self):
        import src.database.supabase_client as sc
        sc._client = None
        sc._mock_mode = True
        settings = sc.get_user_settings()
        self.assertIsInstance(settings, dict)
        self.assertIn("keywords", settings)

    def test_upsert_job_returns_job_in_mock_mode(self):
        import src.database.supabase_client as sc
        sc._client = None
        sc._mock_mode = True
        job = {"title": "Test", "url": "https://example.com/test", "company": "X"}
        result = sc.upsert_job(job)
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Test")

    def test_update_job_status_in_mock_mode(self):
        import src.database.supabase_client as sc
        sc._client = None
        sc._mock_mode = True
        from src.database.mock_data import MOCK_JOBS
        job_id = MOCK_JOBS[0]["id"]
        original_status = MOCK_JOBS[0]["status"]
        sc.update_job_status(job_id, "saved")
        self.assertEqual(MOCK_JOBS[0]["status"], "saved")
        # restore
        MOCK_JOBS[0]["status"] = original_status

    def test_save_analysis_in_mock_mode(self):
        import src.database.supabase_client as sc
        sc._client = None
        sc._mock_mode = True
        from src.database.mock_data import MOCK_JOBS
        job_id = MOCK_JOBS[0]["id"]
        analysis = {"fit_score": 99, "recommendation": "apply", "summary": "Perfect fit.",
                    "matching_skills": [], "missing_skills": [], "key_requirements": []}
        result = sc.save_analysis(job_id, analysis)
        self.assertTrue(result)
        self.assertEqual(MOCK_JOBS[0]["fit_score"], 99)

    def test_save_job_notes_in_mock_mode(self):
        import src.database.supabase_client as sc
        sc._client = None
        sc._mock_mode = True
        from src.database.mock_data import MOCK_JOBS
        job_id = MOCK_JOBS[0]["id"]
        sc.save_job_notes(job_id, "My note here")
        self.assertEqual(MOCK_JOBS[0]["notes"], "My note here")

    def test_save_interview_date_in_mock_mode(self):
        import src.database.supabase_client as sc
        sc._client = None
        sc._mock_mode = True
        from src.database.mock_data import MOCK_JOBS
        job_id = MOCK_JOBS[0]["id"]
        sc.save_interview_date(job_id, "2026-05-01")
        self.assertEqual(MOCK_JOBS[0]["interview_date"], "2026-05-01")

    def test_save_user_settings_in_mock_mode(self):
        import src.database.supabase_client as sc
        sc._client = None
        sc._mock_mode = True
        sc.save_user_settings({"location": "Austin, TX"})
        settings = sc.get_user_settings()
        self.assertEqual(settings["location"], "Austin, TX")


if __name__ == "__main__":
    unittest.main()
