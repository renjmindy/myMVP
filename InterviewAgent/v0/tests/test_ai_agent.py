import json
import unittest
from unittest.mock import MagicMock, patch


SAMPLE_JOB = {
    "id": "test-001",
    "title": "Software Engineer",
    "company": "TestCo",
    "location": "Remote",
    "description": "Python, FastAPI, PostgreSQL required. 3+ years experience.",
}

SAMPLE_RESUME = "Senior Python developer with 5 years of FastAPI and PostgreSQL experience."

VALID_ANALYSIS = {
    "fit_score": 85,
    "key_requirements": ["Python", "FastAPI", "PostgreSQL"],
    "matching_skills": ["Python", "FastAPI", "PostgreSQL"],
    "missing_skills": [],
    "summary": "Strong match. All key requirements met.",
    "recommendation": "apply",
}


def _make_agent(response_content: str):
    """Return a JobAnalysisAgent with a mocked OpenAI client."""
    mock_message = MagicMock()
    mock_message.content = response_content

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_openai = MagicMock()
    mock_openai.chat.completions.create.return_value = mock_response

    with patch("src.agents.ai_agent.supabase_client"):
        with patch("openai.OpenAI", return_value=mock_openai):
            from src.agents.ai_agent import JobAnalysisAgent
            agent = JobAnalysisAgent()
            agent._client = mock_openai
            return agent


class TestAnalyzeJob(unittest.TestCase):
    def test_valid_response_parsed_correctly(self):
        agent = _make_agent(json.dumps(VALID_ANALYSIS))
        result = agent.analyze_job(SAMPLE_JOB, SAMPLE_RESUME)

        self.assertEqual(result["fit_score"], 85)
        self.assertEqual(result["recommendation"], "apply")
        self.assertIn("Python", result["matching_skills"])
        self.assertEqual(result["missing_skills"], [])

    def test_fit_score_clamped_above_100(self):
        over = {**VALID_ANALYSIS, "fit_score": 150}
        agent = _make_agent(json.dumps(over))
        result = agent.analyze_job(SAMPLE_JOB, SAMPLE_RESUME)
        self.assertEqual(result["fit_score"], 100)

    def test_fit_score_clamped_below_0(self):
        under = {**VALID_ANALYSIS, "fit_score": -20}
        agent = _make_agent(json.dumps(under))
        result = agent.analyze_job(SAMPLE_JOB, SAMPLE_RESUME)
        self.assertEqual(result["fit_score"], 0)

    def test_invalid_json_returns_defaults(self):
        agent = _make_agent("not valid json {{")
        result = agent.analyze_job(SAMPLE_JOB, SAMPLE_RESUME)
        self.assertEqual(result["fit_score"], 0)
        self.assertEqual(result["recommendation"], "skip")
        self.assertEqual(result["matching_skills"], [])

    def test_missing_keys_filled_with_defaults(self):
        partial = {"fit_score": 60}
        agent = _make_agent(json.dumps(partial))
        result = agent.analyze_job(SAMPLE_JOB, SAMPLE_RESUME)
        self.assertIn("key_requirements", result)
        self.assertIn("missing_skills", result)
        self.assertIn("summary", result)

    def test_empty_response_returns_defaults(self):
        agent = _make_agent("")
        result = agent.analyze_job(SAMPLE_JOB, SAMPLE_RESUME)
        self.assertEqual(result["fit_score"], 0)


class TestBatchAnalyze(unittest.TestCase):
    def test_batch_returns_updated_jobs(self):
        agent = _make_agent(json.dumps(VALID_ANALYSIS))
        jobs = [SAMPLE_JOB, {**SAMPLE_JOB, "id": "test-002", "title": "Backend Dev"}]

        with patch("src.agents.ai_agent.supabase_client") as mock_db:
            mock_db.save_analysis.return_value = True
            results = agent.batch_analyze(jobs, SAMPLE_RESUME)

        self.assertEqual(len(results), 2)
        for r in results:
            self.assertEqual(r["fit_score"], 85)

    def test_batch_skips_failed_jobs(self):
        agent = _make_agent(json.dumps(VALID_ANALYSIS))
        agent._client.chat.completions.create.side_effect = [
            Exception("API error"),
            MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps(VALID_ANALYSIS)))]),
        ]

        jobs = [SAMPLE_JOB, {**SAMPLE_JOB, "id": "test-002"}]
        with patch("src.agents.ai_agent.supabase_client"):
            results = agent.batch_analyze(jobs, SAMPLE_RESUME)

        self.assertEqual(len(results), 2)
        # first job failed, should not have fit_score updated
        self.assertNotEqual(results[0].get("fit_score"), 85)


class TestGenerateCoverLetter(unittest.TestCase):
    def test_returns_stripped_string(self):
        agent = _make_agent("  Dear Hiring Manager,\n\nParagraph one.\n\nParagraph two.\n  ")
        result = agent.generate_cover_letter(SAMPLE_JOB, SAMPLE_RESUME)
        self.assertIsInstance(result, str)
        self.assertFalse(result.startswith(" "))
        self.assertIn("Paragraph one", result)


if __name__ == "__main__":
    unittest.main()
