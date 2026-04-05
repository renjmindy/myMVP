import asyncio
import json
import os
import random

_WINDOWS_HOST = "172.27.160.1"
_MCP_PORT = 8765


async def _random_delay(min_s: float = 0.5, max_s: float = 1.2):
    await asyncio.sleep(random.uniform(min_s, max_s))


def _parse_degree(connection_text: str) -> str:
    """Infer connection degree from LinkedIn profile text."""
    lower = connection_text.lower()
    if "1st" in lower or "1st degree" in lower:
        return "1st"
    if "2nd" in lower or "2nd degree" in lower:
        return "2nd"
    return "3rd"


def _parse_mutual(connection_text: str) -> str | None:
    """Extract mutual connection name from profile text if present."""
    import re
    m = re.search(r"mutual connection[s]?\s*[:\-]?\s*([A-Z][a-z]+ [A-Z][a-z]+)", connection_text)
    if m:
        return m.group(1)
    m = re.search(r"([A-Z][a-z]+ [A-Z][a-z]+) is a mutual", connection_text)
    if m:
        return m.group(1)
    return None


class NetworkContactsAgent:

    def __init__(self):
        self._mcp_url = f"http://{_WINDOWS_HOST}:{_MCP_PORT}/mcp"

    async def _search_via_mcp(self, company: str, max_results: int = 3) -> list[dict]:
        from mcp import ClientSession  # type: ignore
        from mcp.client.streamable_http import streamable_http_client  # type: ignore
        import httpx  # type: ignore

        contacts: list[dict] = []

        http_client = httpx.AsyncClient(timeout=httpx.Timeout(30))
        async with streamable_http_client(self._mcp_url, http_client=http_client) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # List available tools so we know what the MCP exposes
                tools_result = await session.list_tools()
                tool_names = {t.name for t in (tools_result.tools or [])}

                # ── Try people/profile search tools ──────────────────────
                search_tool = None
                for candidate in ("search_people", "search_profiles", "search_connections"):
                    if candidate in tool_names:
                        search_tool = candidate
                        break

                if not search_tool:
                    return []

                try:
                    result = await session.call_tool(search_tool, {
                        "keywords": company,
                        "company": company,
                    })
                except Exception:
                    return []

                raw = None
                for content in (result.content or []):
                    if hasattr(content, "text"):
                        try:
                            raw = json.loads(content.text)
                        except Exception:
                            raw = {"raw": content.text}
                        break

                if not raw:
                    return []

                profiles = raw.get("profiles") or raw.get("results") or raw.get("people") or []
                if isinstance(profiles, str):
                    # Plain text block — parse line by line
                    lines = [l.strip() for l in profiles.split("\n") if l.strip()]
                    for line in lines[:max_results]:
                        contacts.append({
                            "name": line,
                            "title": "",
                            "degree": "3rd",
                            "mutual": None,
                            "linkedin_url": None,
                        })
                    return contacts

                for profile in profiles[:max_results]:
                    if isinstance(profile, str):
                        contacts.append({
                            "name": profile,
                            "title": "",
                            "degree": "3rd",
                            "mutual": None,
                            "linkedin_url": None,
                        })
                        continue

                    name = (
                        profile.get("name")
                        or profile.get("full_name")
                        or f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()
                    )
                    if not name:
                        continue

                    title = (
                        profile.get("title")
                        or profile.get("headline")
                        or profile.get("position")
                        or ""
                    )
                    raw_text = json.dumps(profile)
                    degree = _parse_degree(raw_text)
                    mutual = _parse_mutual(raw_text)
                    linkedin_url = profile.get("url") or profile.get("linkedin_url") or profile.get("profile_url")

                    contacts.append({
                        "name": name,
                        "title": title,
                        "degree": degree,
                        "mutual": mutual,
                        "linkedin_url": linkedin_url,
                    })
                    await _random_delay()

        return contacts

    def _search_via_openai(self, company: str, max_results: int = 3) -> list[dict]:
        """Fallback: ask GPT to suggest realistic contact archetypes for the company."""
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a LinkedIn network assistant. Given a company name, return "
                        f"exactly {max_results} realistic professional contacts who might work "
                        "there. Use diverse names and realistic job titles. "
                        "Respond ONLY with JSON: "
                        '{"contacts": [{"name": str, "title": str, "degree": "2nd"|"3rd", '
                        '"mutual": str|null, "linkedin_url": null}]}'
                    ),
                },
                {
                    "role": "user",
                    "content": f"Company: {company}\nGenerate {max_results} plausible network contacts.",
                },
            ],
            temperature=0.7,
        )
        raw = response.choices[0].message.content or "{}"
        try:
            data = json.loads(raw)
            return data.get("contacts", [])[:max_results]
        except Exception:
            return []

    def find_contacts(self, company: str, max_results: int = 3) -> list[dict]:
        """
        Search LinkedIn MCP for people at `company`.
        Falls back to OpenAI-generated contacts if MCP is unavailable or returns nothing.
        """
        contacts: list[dict] = []
        try:
            contacts = asyncio.run(self._search_via_mcp(company, max_results))
        except Exception:
            pass

        if not contacts:
            try:
                contacts = self._search_via_openai(company, max_results)
            except Exception:
                pass

        return contacts[:max_results]
