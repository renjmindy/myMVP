import json
import os

from src.database import supabase_client


class ResumeOptimizationAgent:
    MODES = ["keyword", "skills", "experience"]

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

    def optimize(self, resume_text: str, job: dict, mode: str = "keyword") -> dict:
        if mode not in self.MODES:
            mode = "keyword"

        company_name = job.get("company", "")
        company_context = self._research_company(company_name) if company_name else ""

        mode_instructions = {
            "keyword": (
                "Focus on ATS keyword optimization. Identify critical keywords from the job description "
                "that are missing or underrepresented in the resume and incorporate them naturally. "
                "Preserve all factual information — do not invent experience."
            ),
            "skills": (
                "Reorder and emphasize the skills section to match the job requirements. "
                "Put the most relevant skills first and group them logically. "
                "Add transferable skills that genuinely apply."
            ),
            "experience": (
                "Rewrite bullet points in the experience section to highlight the most relevant "
                "experience for this role. Use strong action verbs and quantify achievements. "
                "Tailor the language to mirror the job description."
            ),
        }

        prompt = (
            f"You are an expert resume writer optimizing a resume for a specific job.\n\n"
            f"OPTIMIZATION MODE: {mode}\n"
            f"INSTRUCTIONS: {mode_instructions[mode]}\n\n"
            f"JOB TITLE: {job.get('title', '')}\n"
            f"COMPANY: {company_name}\n"
            f"JOB DESCRIPTION:\n{job.get('description', '')}\n\n"
            f"COMPANY CONTEXT:\n{company_context}\n\n"
            f"ORIGINAL RESUME:\n{resume_text}\n\n"
            "Return a JSON object with these exact fields:\n"
            "- optimized_content (string): the full optimized resume text\n"
            "- changes_made (array of strings): list of specific changes made\n"
            "- match_score (integer 0-100): how well the optimized resume matches the job\n"
            "- quality_score (integer 0-100): overall quality of the optimized resume\n"
        )

        result = {
            "optimized_content": resume_text,
            "changes_made": [],
            "match_score": 0,
            "quality_score": 0,
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
                            "You are an expert resume optimizer. Respond only with valid JSON containing: "
                            "optimized_content (string), changes_made (string[]), "
                            "match_score (int 0-100), quality_score (int 0-100)."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
            )
            raw = response.choices[0].message.content or "{}"
            parsed = json.loads(raw)
            result["optimized_content"] = parsed.get("optimized_content", resume_text)
            result["changes_made"] = parsed.get("changes_made", [])
            result["match_score"] = max(0, min(100, int(parsed.get("match_score", 0))))
            result["quality_score"] = max(0, min(100, int(parsed.get("quality_score", 0))))
        except Exception as e:
            result["error"] = str(e)

        agent_result_id = supabase_client.log_agent_result(
            agent_type="ResumeOptimizationAgent",
            task_type=f"optimize_{mode}",
            input_data={"job_title": job.get("title", ""), "company": company_name, "mode": mode},
            output_data={
                "match_score": result["match_score"],
                "quality_score": result["quality_score"],
                "changes_count": len(result["changes_made"]),
            },
            success="error" not in result,
            error=result.get("error"),
        )

        supabase_client.save_optimized_resume({
            "job_title": job.get("title", ""),
            "company_name": company_name,
            "original_content": resume_text,
            "optimized_content": result["optimized_content"],
            "optimization_mode": mode,
            "match_score": result["match_score"],
            "quality_score": result["quality_score"],
            "changes_made": result["changes_made"],
            "agent_result_id": agent_result_id,
        })

        return result

    def batch_optimize(
        self, resume_text: str, jobs: list[dict], mode: str = "keyword"
    ) -> list[dict]:
        results = []
        for job in jobs:
            try:
                res = self.optimize(resume_text, job, mode)
                results.append({**job, "optimization": res})
            except Exception as e:
                results.append({**job, "optimization": {"error": str(e)}})
        return results
