import json
import os

from src.database import supabase_client


class JobAnalysisAgent:
    def __init__(self):
        from openai import OpenAI  # type: ignore

        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self._model = "gpt-4o-mini"

    def analyze_job(self, job: dict, resume_text: str) -> dict:
        response = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a career coach. Respond only with valid JSON matching "
                        "this schema: fit_score (int 0-100), key_requirements (string[]), "
                        "matching_skills (string[]), missing_skills (string[]), "
                        "summary (2-3 sentence string), recommendation ('apply'|'maybe'|'skip')."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"JOB TITLE: {job.get('title', '')}\n"
                        f"COMPANY: {job.get('company', '')}\n"
                        f"LOCATION: {job.get('location', '')}\n\n"
                        f"JOB DESCRIPTION:\n{job.get('description', '')}\n\n"
                        f"CANDIDATE RESUME:\n{resume_text}\n\n"
                        "Analyze the fit and return the JSON object."
                    ),
                },
            ],
            temperature=0.3,
        )

        raw = response.choices[0].message.content or "{}"
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            result = {}

        result.setdefault("fit_score", 0)
        result.setdefault("key_requirements", [])
        result.setdefault("matching_skills", [])
        result.setdefault("missing_skills", [])
        result.setdefault("summary", "")
        result.setdefault("recommendation", "skip")
        result["fit_score"] = max(0, min(100, int(result["fit_score"])))

        return result

    def batch_analyze(self, jobs: list[dict], resume_text: str) -> list[dict]:
        updated: list[dict] = []
        for job in jobs:
            try:
                analysis = self.analyze_job(job, resume_text)
                job_id = job.get("id")
                if job_id:
                    supabase_client.save_analysis(job_id, analysis)
                updated.append({**job, "analysis": analysis, "fit_score": analysis["fit_score"]})
            except Exception:
                updated.append(job)
        return updated
