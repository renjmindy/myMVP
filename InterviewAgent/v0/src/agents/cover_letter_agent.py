import json
import os

from src.database import supabase_client


class CoverLetterAgent:
    TONES = ["professional", "enthusiastic", "confident", "creative"]

    def __init__(self):
        from openai import OpenAI  # type: ignore

        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self._model = "gpt-4o-mini"

    def _research_company(self, company_name: str) -> str:
        cached = supabase_client.get_company_research(company_name)
        if cached:
            data = cached.get("research_data", {})
            return data.get("summary", "") if isinstance(data, dict) else str(data)

        try:
            response = self._client.responses.create(
                model=self._model,
                tools=[{"type": "web_search_preview"}],
                input=(
                    f"Research this company for job application context: {company_name}. "
                    "Summarize: culture, tech stack, recent news, what they value in candidates. Be concise."
                ),
            )
            summary = response.output_text
        except Exception:
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {
                            "role": "user",
                            "content": f"What do you know about {company_name} as an employer? Summarize briefly.",
                        }
                    ],
                    max_tokens=300,
                )
                summary = response.choices[0].message.content or ""
            except Exception:
                summary = ""

        supabase_client.save_company_research(company_name, {"summary": summary})
        return summary

    def generate(
        self,
        job: dict,
        resume_text: str,
        tone: str = "professional",
        candidate_info: dict = None,
    ) -> dict:
        if tone not in self.TONES:
            tone = "professional"

        company_name = job.get("company", "")
        company_context = self._research_company(company_name) if company_name else ""

        tone_instructions = {
            "professional": (
                "Write in a formal, polished tone. Focus on concrete achievements and professional accomplishments. "
                "Use measured language that conveys competence and reliability."
            ),
            "enthusiastic": (
                "Write in an energetic, passion-forward tone. Express genuine excitement about the role and company. "
                "Let enthusiasm for the work shine through while remaining professional."
            ),
            "confident": (
                "Write in an assertive, results-focused tone. Lead with impact statements. "
                "Be direct about your value proposition without being arrogant."
            ),
            "creative": (
                "Use a storytelling approach with a memorable opening hook. "
                "Make the letter distinctive and engaging while still being appropriate for a job application."
            ),
        }

        candidate_block = ""
        if candidate_info:
            parts = [
                f"{k.capitalize()}: {v}"
                for k, v in candidate_info.items()
                if v and k in ("name", "email", "phone", "linkedin")
            ]
            if parts:
                candidate_block = "CANDIDATE INFO:\n" + "\n".join(parts) + "\n\n"

        prompt = (
            f"Write a tailored 3-paragraph cover letter for the following job.\n\n"
            f"TONE: {tone}\n"
            f"TONE INSTRUCTIONS: {tone_instructions[tone]}\n\n"
            f"{candidate_block}"
            f"JOB TITLE: {job.get('title', '')}\n"
            f"COMPANY: {company_name}\n"
            f"JOB DESCRIPTION:\n{job.get('description', '')}\n\n"
            f"COMPANY CONTEXT:\n{company_context}\n\n"
            f"CANDIDATE RESUME:\n{resume_text}\n\n"
            "Do not include a date or address block — just the three paragraphs.\n\n"
            "Return a JSON object with these exact fields:\n"
            "- content (string): the full cover letter text\n"
            "- quality_score (integer 0-100): score for structure, specificity, and tone match\n"
            "- personalization_score (integer 0-100): score for company-specific details and relevance\n"
        )

        result = {
            "content": "",
            "tone": tone,
            "quality_score": 0,
            "personalization_score": 0,
            "word_count": 0,
            "company_context": company_context,
        }

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert cover letter writer. Respond only with valid JSON containing: "
                            "content (string), quality_score (int 0-100), personalization_score (int 0-100)."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
            )
            raw = response.choices[0].message.content or "{}"
            parsed = json.loads(raw)
            result["content"] = parsed.get("content", "")
            result["quality_score"] = max(0, min(100, int(parsed.get("quality_score", 0))))
            result["personalization_score"] = max(
                0, min(100, int(parsed.get("personalization_score", 0)))
            )
            result["word_count"] = len(result["content"].split())
        except Exception as e:
            result["error"] = str(e)

        agent_result_id = supabase_client.log_agent_result(
            agent_type="CoverLetterAgent",
            task_type="generate_cover_letter",
            input_data={"job_title": job.get("title", ""), "company": company_name, "tone": tone},
            output_data={
                "quality_score": result["quality_score"],
                "personalization_score": result["personalization_score"],
                "word_count": result["word_count"],
            },
            success="error" not in result,
            error=result.get("error"),
        )

        supabase_client.save_cover_letter({
            "job_title": job.get("title", ""),
            "company_name": company_name,
            "content": result["content"],
            "tone": tone,
            "quality_score": result["quality_score"],
            "personalization_score": result["personalization_score"],
            "word_count": result["word_count"],
            "agent_result_id": agent_result_id,
        })

        return result

    def generate_batch(
        self, jobs: list[dict], resume_text: str, tone: str = "professional"
    ) -> list[dict]:
        results = []
        for job in jobs:
            try:
                res = self.generate(job, resume_text, tone)
                results.append({**job, "cover_letter": res})
            except Exception as e:
                results.append({**job, "cover_letter": {"error": str(e)}})
        return results
