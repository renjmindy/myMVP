import json
import os

from src.database import supabase_client


class JobDiscoveryAgent:
    def __init__(self):
        from openai import OpenAI  # type: ignore

        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self._model = "gpt-4o-mini"

    def _web_search(self, query: str, fallback_prompt: str) -> str:
        try:
            response = self._client.responses.create(
                model=self._model,
                tools=[{"type": "web_search_preview"}],
                input=query,
            )
            return response.output_text
        except Exception:
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": fallback_prompt}],
                    max_tokens=500,
                )
                return response.choices[0].message.content or ""
            except Exception:
                return ""

    def analyze_market(self, keywords: list[str], location: str) -> dict:
        query = (
            f"What is the current job market like for {', '.join(keywords)} roles in {location}? "
            "Include: demand level (high/medium/low), typical salary ranges, top hiring companies, "
            "trending skills, competition level, and a brief market summary."
        )
        fallback = query

        raw_text = self._web_search(query, fallback)

        result = {
            "demand_level": "medium",
            "avg_salary_range": "Not available",
            "top_companies": [],
            "trending_skills": [],
            "market_summary": raw_text,
            "competition_level": "medium",
        }

        try:
            parse_prompt = (
                f"Based on this market research text, extract structured data:\n\n{raw_text}\n\n"
                f"Keywords: {keywords}, Location: {location}\n\n"
                "Return JSON with: demand_level (high/medium/low string), avg_salary_range (string), "
                "top_companies (string array), trending_skills (string array), "
                "market_summary (string), competition_level (high/medium/low string)."
            )
            response = self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "Extract structured market insight data. Return valid JSON only.",
                    },
                    {"role": "user", "content": parse_prompt},
                ],
                temperature=0.2,
            )
            parsed = json.loads(response.choices[0].message.content or "{}")
            result["demand_level"] = parsed.get("demand_level", "medium")
            result["avg_salary_range"] = parsed.get("avg_salary_range", "Not available")
            result["top_companies"] = parsed.get("top_companies", [])
            result["trending_skills"] = parsed.get("trending_skills", [])
            result["market_summary"] = parsed.get("market_summary", raw_text)
            result["competition_level"] = parsed.get("competition_level", "medium")
        except Exception:
            pass

        supabase_client.save_market_insight(keywords, location, result)
        return result

    def research_company(self, company_name: str) -> dict:
        cached = supabase_client.get_company_research(company_name)
        if cached:
            data = cached.get("research_data", {})
            if isinstance(data, dict) and "overview" in data:
                return data

        query = (
            f"Research {company_name} as an employer. Include: company overview, culture, "
            "tech stack they use, recent news, Glassdoor rating if available, and interview tips."
        )
        fallback = query

        raw_text = self._web_search(query, fallback)

        result = {
            "overview": "",
            "culture": "",
            "tech_stack": [],
            "recent_news": [],
            "glassdoor_rating": "Not available",
            "interview_tips": "",
        }

        try:
            parse_prompt = (
                f"Based on this company research text about {company_name}, extract structured data:\n\n{raw_text}\n\n"
                "Return JSON with: overview (string), culture (string), tech_stack (string array), "
                "recent_news (string array), glassdoor_rating (string), interview_tips (string)."
            )
            response = self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "Extract structured company research data. Return valid JSON only.",
                    },
                    {"role": "user", "content": parse_prompt},
                ],
                temperature=0.2,
            )
            parsed = json.loads(response.choices[0].message.content or "{}")
            result["overview"] = parsed.get("overview", "")
            result["culture"] = parsed.get("culture", "")
            result["tech_stack"] = parsed.get("tech_stack", [])
            result["recent_news"] = parsed.get("recent_news", [])
            result["glassdoor_rating"] = parsed.get("glassdoor_rating", "Not available")
            result["interview_tips"] = parsed.get("interview_tips", "")
        except Exception:
            result["overview"] = raw_text

        supabase_client.save_company_research(company_name, result)
        return result

    def generate_interview_prep(self, job: dict, resume_text: str) -> dict:
        company_name = job.get("company", "")
        job_title = job.get("title", "")

        prompt = (
            f"Generate interview preparation materials for this job application.\n\n"
            f"JOB TITLE: {job_title}\n"
            f"COMPANY: {company_name}\n"
            f"JOB DESCRIPTION:\n{job.get('description', '')}\n\n"
            f"CANDIDATE RESUME:\n{resume_text}\n\n"
            "Return JSON with:\n"
            "- likely_questions (string array): 8-10 likely interview questions\n"
            "- talking_points (string array): key talking points about the candidate's fit\n"
            "- questions_to_ask (string array): 5 thoughtful questions the candidate should ask\n"
            "- red_flags (string array): potential concerns to address proactively\n"
        )

        result = {
            "likely_questions": [],
            "talking_points": [],
            "questions_to_ask": [],
            "red_flags": [],
        }

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert interview coach. Return valid JSON with: "
                            "likely_questions (string[]), talking_points (string[]), "
                            "questions_to_ask (string[]), red_flags (string[])."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
            )
            parsed = json.loads(response.choices[0].message.content or "{}")
            result["likely_questions"] = parsed.get("likely_questions", [])
            result["talking_points"] = parsed.get("talking_points", [])
            result["questions_to_ask"] = parsed.get("questions_to_ask", [])
            result["red_flags"] = parsed.get("red_flags", [])
        except Exception as e:
            result["error"] = str(e)

        job_id = str(job.get("id", ""))
        supabase_client.save_interview_prep({
            "job_id": job_id,
            "job_title": job_title,
            "company_name": company_name,
            "questions": result,
            "notes": "",
        })

        return result
