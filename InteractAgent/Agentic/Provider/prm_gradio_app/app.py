# app.py — PRM Care Coordinator
#
# HuggingFace Spaces entry point.
# Set OPENAI_API_KEY as a Space Secret before deploying.
#
# Architecture (mirrors 05-simulation-sentiment-agent.py):
#   User message
#       │
#       ▼
#   Sentiment Detector  ← classification_template | LLM | StrOutputParser()
#       │                         │
#       └── RunnableBranch ──► positive / negative / neutral / escalate note
#       │
#       ▼
#   Care Coordinator Agent  ← LangChain tool loop
#       ├── get_prm_score()          retrieve PHQ-9 / GAD-7 / pain / EQ-5D
#       └── flag_clinical_review()   raise urgent clinical flag

import math
import os
import re
import requests
from datetime import date, timedelta
from typing import List, Tuple
from urllib.parse import quote as _url_quote

import gradio as gr
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableBranch
from langchain_core.tools import tool

load_dotenv()  # no-op on HF Spaces; keys come from Space Secrets

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

# ---------------------------------------------------------------------------
# 1. Models
# ---------------------------------------------------------------------------

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)

# ---------------------------------------------------------------------------
# 2. Tools  (Patient Reported Measures)
# ---------------------------------------------------------------------------

@tool
def get_prm_score(patient_id: str, measure_name: str) -> str:
    """
    Retrieve the patient's most recent PRM submission score.
    measure_name: one of 'PHQ-9', 'GAD-7', 'pain_scale', 'EQ-5D'.
    """
    records = {
        ("P-1042", "PHQ-9"):      (14,   "Moderate depression",
                                    "Schedule follow-up with a mental health professional within 2 weeks."),
        ("P-1042", "GAD-7"):      (11,   "Moderate anxiety",
                                    "Discuss stress management; consider referral if score remains elevated."),
        ("P-1042", "pain_scale"): (7,    "Severe pain (7/10)",
                                    "Review current pain management plan with the treating physician."),
        ("P-1042", "EQ-5D"):      (0.62, "Below population norm",
                                    "Explore barriers to daily functioning and quality-of-life improvement."),
    }
    key = (patient_id, measure_name)
    if key in records:
        score, severity, action = records[key]
        return (
            f"Patient {patient_id} — {measure_name}: score {score} ({severity}). "
            f"Recommended action: {action}"
        )
    return f"No recent {measure_name} submission found for patient {patient_id}."


@tool
def flag_clinical_review(patient_name: str, measure_name: str, score: str, reason: str) -> str:
    """
    Flag a patient's PRM result for urgent clinical review.
    score: the concerning score value as a string.
    reason: brief clinical reason for the flag.
    """
    ticket_id = f"CLN-{abs(hash(patient_name + measure_name)) % 100000:05d}"
    return (
        f"Clinical review flag {ticket_id} raised for {patient_name}. "
        f"Measure: {measure_name}, Score: {score}. "
        f"A clinician will follow up within 24 hours. Reason: {reason}"
    )


_WMO_CODES = {
    0: "Clear sky ☀️",         1: "Mainly clear 🌤️",       2: "Partly cloudy ⛅",     3: "Overcast ☁️",
    45: "Foggy 🌫️",            48: "Icy fog 🌫️",
    51: "Light drizzle 🌦️",    53: "Moderate drizzle 🌧️",  55: "Heavy drizzle 🌧️",
    61: "Slight rain 🌧️",      63: "Moderate rain 🌧️",     65: "Heavy rain 🌧️",
    71: "Slight snow 🌨️",      73: "Moderate snow 🌨️",     75: "Heavy snow ❄️",       77: "Snow grains ❄️",
    80: "Slight showers 🌦️",   81: "Moderate showers 🌦️",  82: "Violent showers ⛈️",
    95: "Thunderstorm ⛈️",     96: "Thunderstorm + hail ⛈️", 99: "Heavy thunderstorm ⛈️",
}


_US_STATES = {
    "Alabama","Alaska","Arizona","Arkansas","California","Colorado","Connecticut",
    "Delaware","Florida","Georgia","Hawaii","Idaho","Illinois","Indiana","Iowa",
    "Kansas","Kentucky","Louisiana","Maine","Maryland","Massachusetts","Michigan",
    "Minnesota","Mississippi","Missouri","Montana","Nebraska","Nevada",
    "New Hampshire","New Jersey","New Mexico","New York","North Carolina",
    "North Dakota","Ohio","Oklahoma","Oregon","Pennsylvania","Rhode Island",
    "South Carolina","South Dakota","Tennessee","Texas","Utah","Vermont",
    "Virginia","Washington","West Virginia","Wisconsin","Wyoming",
    "District of Columbia",
}

_STATE_ABBREV = {
    "AL": "Alabama",    "AK": "Alaska",       "AZ": "Arizona",      "AR": "Arkansas",
    "CA": "California", "CO": "Colorado",     "CT": "Connecticut",  "DE": "Delaware",
    "FL": "Florida",    "GA": "Georgia",      "HI": "Hawaii",       "ID": "Idaho",
    "IL": "Illinois",   "IN": "Indiana",      "IA": "Iowa",         "KS": "Kansas",
    "KY": "Kentucky",   "LA": "Louisiana",    "ME": "Maine",        "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan",  "MN": "Minnesota",    "MS": "Mississippi",
    "MO": "Missouri",   "MT": "Montana",      "NE": "Nebraska",     "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey","NM": "New Mexico",   "NY": "New York",
    "NC": "North Carolina","ND": "North Dakota","OH": "Ohio",        "OK": "Oklahoma",
    "OR": "Oregon",     "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota","TN": "Tennessee",   "TX": "Texas",        "UT": "Utah",
    "VT": "Vermont",    "VA": "Virginia",     "WA": "Washington",   "WV": "West Virginia",
    "WI": "Wisconsin",  "WY": "Wyoming",      "DC": "District of Columbia",
}


def _geocode(query: str, _retry: bool = True):
    """Return (lat, lon, display_name) or None.
    Handles 'City, ST', 'City ST', 'City, State', 'City State', zip codes.
    When a US state is identified, uses Nominatim structured search to correctly
    disambiguate same-name cities (e.g. Aurora IL → Illinois, not Colorado).
    Falls back to Open-Meteo for plain city names without state context.
    If both fail and _retry=True, asks the LLM to spell-correct the city name
    and retries once (catches typos like 'Los Angelas', 'Seatel', 'Phonix').
    """
    raw = query.strip()
    city_part  = raw
    state_full = None

    if "," in raw:
        # "Aurora, IL"  or  "Newport News, VA"  or  "Austin, TX 78701"
        parts   = [p.strip() for p in raw.split(",", 1)]
        city_part = parts[0]
        suffix  = re.sub(r"\b\d{5}(-\d{4})?\b", "", parts[1]).strip()
        abbrev  = suffix.upper()
        if re.match(r"^[A-Z]{2}$", abbrev):
            state_full = _STATE_ABBREV.get(abbrev)
        else:
            for s in _US_STATES:
                if suffix.lower() == s.lower():
                    state_full = s
                    break
    else:
        # "Aurora IL"  (trailing 2-letter uppercase abbreviation)
        m = re.search(r"\s+([A-Z]{2})\s*$", raw)
        if m and m.group(1) in _STATE_ABBREV:
            state_full = _STATE_ABBREV[m.group(1)]
            city_part  = raw[: m.start()].strip()

        if state_full is None:
            # "Plano Texas"  (trailing full state name)
            for state in _US_STATES:
                if raw.lower().endswith(" " + state.lower()):
                    city_part  = raw[: -len(state) - 1].strip()
                    state_full = state
                    break

    # Strip zip codes from city_part
    city_part = re.sub(r"\b\d{5}(-\d{4})?\b", "", city_part).strip()

    # State-aware: Nominatim structured search gives exact state-level match
    if state_full:
        try:
            r = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "city":           city_part,
                    "state":          state_full,
                    "country":        "United States",
                    "format":         "json",
                    "limit":          1,
                    "addressdetails": 1,
                },
                headers={"User-Agent": "prm-care-coordinator/1.0"},
                timeout=8,
            ).json()
            if r:
                lat  = float(r[0]["lat"])
                lon  = float(r[0]["lon"])
                addr = r[0].get("address", {})
                city_name = (
                    addr.get("city") or addr.get("town") or
                    addr.get("village") or city_part
                )
                return lat, lon, f"{city_name}, {state_full}"
        except Exception:
            pass

    # Fallback: Open-Meteo (no state disambiguation — works for unambiguous names)
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city_part, "count": 1, "language": "en", "format": "json"},
            timeout=8,
        ).json()
        if geo.get("results"):
            r = geo["results"][0]
            name = f"{r.get('name', city_part)}, {r.get('admin1', '')}, {r.get('country_code', '')}"
            return r["latitude"], r["longitude"], name
    except Exception:
        pass

    # LLM spell-correction — retry once with corrected city name
    if _retry:
        try:
            corrected = llm.invoke(
                f"The US city name '{city_part}' could not be geocoded — it likely has a typo. "
                f"Return only the correctly spelled US city name"
                + (f" in {state_full}" if state_full else "")
                + ", nothing else."
            ).content.strip()
            if corrected and corrected.lower() != city_part.lower():
                retry_query = f"{corrected}, {state_full}" if state_full else corrected
                return _geocode(retry_query, _retry=False)
        except Exception:
            pass

    return None


def _geocode_hospital(city: str):
    """Return (lat, lon, name) for a nearby hospital using Open-Meteo coords + Nominatim viewbox."""
    origin = _geocode(city)
    if origin is None:
        return None
    lat, lon, _ = origin
    delta = 0.3  # ~20-mile bounding box
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "amenity":  "hospital",
                "viewbox":  f"{lon-delta},{lat+delta},{lon+delta},{lat-delta}",
                "bounded":  1,
                "format":   "json",
                "limit":    1,
            },
            headers={"User-Agent": "prm-care-coordinator/1.0"},
            timeout=8,
        ).json()
        if r:
            return float(r[0]["lat"]), float(r[0]["lon"]), r[0]["display_name"].split(",")[0]
    except Exception:
        pass
    return None


def _haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles between two lat/lon points."""
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _find_nearby_hospitals(city: str, n: int = 5) -> list:
    """
    Return up to n hospitals closest to the city centre.
    Each entry: {"name": str, "address": str, "dist_mi": float, "lat": float, "lon": float}
    Uses Nominatim (OpenStreetMap) — no API key required.
    """
    origin = _geocode(city)
    if not origin:
        return []
    lat, lon, _ = origin
    delta = 0.5  # ~35-mile bounding box
    try:
        results = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "amenity":  "hospital",
                "viewbox":  f"{lon-delta},{lat+delta},{lon+delta},{lat-delta}",
                "bounded":  1,
                "format":   "json",
                "limit":    20,
            },
            headers={"User-Agent": "prm-care-coordinator/1.0"},
            timeout=10,
        ).json()
    except Exception:
        return []

    hospitals = []
    seen = set()
    for h in results:
        name = h["display_name"].split(",")[0].strip()
        if name in seen:
            continue
        seen.add(name)
        hlat, hlon = float(h["lat"]), float(h["lon"])
        dist = _haversine_mi(lat, lon, hlat, hlon)
        addr_parts = [p.strip() for p in h["display_name"].split(",")[:3]]
        hospitals.append({
            "name":    name,
            "address": ", ".join(addr_parts),
            "dist_mi": dist,
            "lat":     hlat,
            "lon":     hlon,
        })

    hospitals.sort(key=lambda x: x["dist_mi"])
    return hospitals[:n]


def _extended_forecast_html(lat: float, lon: float) -> str:
    """35-day daily weather grid (today → today+34), 7 columns × 5 rows.
    Days 0-15: actual Open-Meteo forecast (forecast_days=16 always anchors to today).
    Days 16-34: historical archive from the same period last year, filling
                exactly the remaining slots after the actual forecast ends.
    """
    today     = date.today()
    _DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    _DAILY    = "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode"
    _BASE     = {"latitude": lat, "longitude": lon, "daily": _DAILY,
                 "temperature_unit": "fahrenheit", "precipitation_unit": "inch",
                 "timezone": "auto"}

    def _row(d):
        return {"temperature_2m_max": d.get("temperature_2m_max", []),
                "temperature_2m_min": d.get("temperature_2m_min", []),
                "precipitation_sum":  d.get("precipitation_sum",  []),
                "weathercode":        d.get("weathercode",        [])}

    # ── Actual forecast: forecast_days=16 always starts from today ─────────
    entries = []
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast",
                         params={**_BASE, "forecast_days": 16},
                         timeout=10).json()
        daily = r.get("daily", {})
        for i, ds in enumerate(daily.get("time", [])):
            entries.append({
                "date":   date.fromisoformat(ds),
                "max_f":  daily["temperature_2m_max"][i],
                "min_f":  daily["temperature_2m_min"][i],
                "precip": daily.get("precipitation_sum", [0]*20)[i] or 0,
                "code":   daily.get("weathercode",        [0]*20)[i] or 0,
                "actual": True,
            })
    except Exception:
        pass

    # ── Historical estimate: fill whatever slots remain after forecast ──────
    remaining = 35 - len(entries)
    if remaining > 0:
        # Start right after the last forecast day (or today if forecast failed)
        h_start = entries[-1]["date"] + timedelta(days=1) if entries else today
        h_end   = h_start + timedelta(days=remaining - 1)

        def _prev_year(d: date) -> date:
            try:    return date(d.year - 1, d.month, d.day)
            except: return date(d.year - 1, d.month, 28)   # Feb 29 → Feb 28

        try:
            r = requests.get("https://archive-api.open-meteo.com/v1/archive",
                             params={**_BASE,
                                     "start_date": _prev_year(h_start).isoformat(),
                                     "end_date":   _prev_year(h_end).isoformat()},
                             timeout=10).json()
            daily = r.get("daily", {})
            for i, ds in enumerate(daily.get("time", [])):
                if len(entries) >= 35:
                    break
                entries.append({
                    "date":   h_start + timedelta(days=i),   # mapped to this year
                    "max_f":  daily["temperature_2m_max"][i],
                    "min_f":  daily["temperature_2m_min"][i],
                    "precip": daily.get("precipitation_sum", [0]*40)[i] or 0,
                    "code":   daily.get("weathercode",        [0]*40)[i] or 0,
                    "actual": False,
                })
        except Exception:
            pass

    # Pad to exactly 35 slots
    entries = entries[:35]
    while len(entries) < 35:
        entries.append(None)

    # Use the API's first returned date as "today" for the location's timezone.
    # date.today() reflects the server's system clock, which can be a day ahead
    # when the server is in UTC and the location is in a timezone like US/Eastern.
    display_today = entries[0]["date"] if entries[0] is not None else today

    # ── Render 7×5 grid ────────────────────────────────────────────────────
    cells = ""
    for e in entries:
        if e is None:
            cells += '<div></div>'
            continue

        d      = e["date"]
        emoji  = _WMO_CODES.get(e["code"], "🌡️").split()[-1]
        wet    = e["precip"] and float(e["precip"]) > 0.05
        max_c  = round((e["max_f"] - 32) * 5 / 9)
        min_c  = round((e["min_f"] - 32) * 5 / 9)

        if d == display_today:
            bg, border = "#1565C0", "2px solid #0d47a1"
            dlc, tc    = "#bbdefb", "#ffffff"
        elif e["actual"]:
            bg, border = "#ffffff", "1px solid #dee2e6"
            dlc, tc    = "#999999", "#222222"
        else:
            bg, border = "#f5f5f5", "1px solid #e8e8e8"
            dlc, tc    = "#bbbbbb", "#888888"

        cells += (
            f'<div style="background:{bg};border:{border};border-radius:5px;'
            f'padding:4px 1px;text-align:center;">'
            f'<div style="font-size:0.54rem;color:{dlc};line-height:1.3;">'
            f'{_DAY_ABBR[d.weekday()]}<br>{d.month}/{d.day}</div>'
            f'<div style="font-size:0.95rem;line-height:1.15;">{emoji}</div>'
            f'<div style="font-size:0.60rem;font-weight:700;color:{tc};">'
            f'{e["max_f"]:.0f}°</div>'
            f'<div style="font-size:0.56rem;color:{dlc};">{e["min_f"]:.0f}°</div>'
            f'<div style="font-size:0.54rem;color:{dlc};">'
            f'{max_c}/{min_c}°C</div>'
            + ('<div style="font-size:0.50rem;">💧</div>' if wet else '')
            + '</div>'
        )

    has_hist = any(e and not e["actual"] for e in entries)
    legend   = (
        '<div style="font-size:0.58rem;color:#bbb;margin-top:4px;font-style:italic;">'
        'White = forecast · Gray = historical estimate (prior year)</div>'
    ) if has_hist else ""

    return (
        '<div style="background:#f0f4f8;border-radius:8px;padding:8px;margin-top:6px;">'
        '<div style="font-size:0.73rem;font-weight:700;color:#555;margin-bottom:5px;">'
        '📅&nbsp;35-Day Forecast (Today → +34 days)</div>'
        '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:3px;">'
        f'{cells}</div>{legend}</div>'
    )


def _has_state(city: str) -> bool:
    """Return True only when city string ends with a 2-letter US state abbreviation."""
    return bool(re.search(r'\b[A-Z]{2}$', city.strip()))


def _missing_state_html(city_hint: str = "") -> str:
    """Panel shown when the user mentions a city without a state."""
    city_part = f" for <b>{city_hint}</b>" if city_hint and city_hint.lower() not in ("unknown", "needs_state", "your city") else ""
    return (
        '<div style="background:#fff8e1;border:1.5px solid #f9a825;border-radius:8px;'
        'padding:12px;margin-bottom:8px;">'
        '<div style="font-size:0.95rem;font-weight:700;color:#f57f17;">'
        f'📍 State required{city_part}</div>'
        '<div style="font-size:0.80rem;color:#555;margin-top:6px;line-height:1.55;">'
        'Many US cities share the same name across states (e.g. Springfield exists in IL, MO, OH, and more).<br>'
        'Please include your <b>state abbreviation</b> so we can find the right hospitals.<br>'
        'Example: <b>"I am in Richardson, TX"</b> &nbsp;or&nbsp; <b>"I\'m in Springfield, IL"</b>'
        '</div></div>'
    )


def _hospitals_html(hospitals: list, city: str) -> str:
    if not hospitals:
        city_display = city if city and city.lower() not in ("unknown", "your city") else "your area"
        return (
            f'<div style="background:#fff3e0;border-radius:8px;padding:12px;margin-bottom:8px;">'
            f'  <div style="font-size:0.95rem;font-weight:700;color:#e65100;">🏥 No hospitals found near {city_display}</div>'
            f'  <div style="font-size:0.80rem;color:#555;margin-top:6px;">'
            f'    Try including your state abbreviation, e.g. <b>"I am in Richardson TX"</b> or <b>"I\'m in Boston, MA"</b>.'
            f'  </div>'
            f'</div>'
        )
    rows = ""
    for i, h in enumerate(hospitals, 1):
        rows += f"""
  <div style="padding:8px 0;border-bottom:1px solid #ffe0b2;">
    <div style="font-weight:700;font-size:0.88rem;color:#e65100;">#{i}&nbsp;{h['name']}</div>
    <div style="font-size:0.75rem;color:#555;margin-top:2px;">{h['address']}</div>
    <div style="font-size:0.75rem;color:#888;">{h['dist_mi']:.1f} mi from {city}</div>
  </div>"""
    return f"""
<div style="background:#fff3e0;border-radius:8px;padding:12px;margin-bottom:8px;">
  <div style="font-size:0.95rem;font-weight:700;color:#e65100;">🏥 Nearby Hospitals</div>
  <div style="font-size:0.75rem;color:#777;margin:2px 0 6px;">Top {len(hospitals)} closest to {city} — select one below for directions</div>
  {rows}
</div>"""


@tool
def get_weather_for_appointment(city: str, appointment_date: str) -> str:
    """
    Get real-time weather for a city using the Open-Meteo API (free, no key required).
    Uses _geocode() for state-aware city disambiguation.
    """
    try:
        # Step 1 — geocode city name to lat/lon (state-aware)
        coords = _geocode(city)
        if not coords:
            return f"Could not locate '{city}' for weather lookup."
        lat, lon, city_display = coords

        # Step 2 — fetch current conditions
        wx = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,apparent_temperature,weathercode,windspeed_10m,precipitation",
                "temperature_unit": "fahrenheit",
                "windspeed_unit": "mph",
                "precipitation_unit": "inch",
                "timezone": "auto",
            },
            timeout=10,
        ).json()
        curr = wx.get("current", {})
        temp_f   = curr.get("temperature_2m", "N/A")
        feels_f  = curr.get("apparent_temperature", "N/A")
        wind     = curr.get("windspeed_10m", "N/A")
        precip   = curr.get("precipitation", 0)
        code     = int(curr.get("weathercode", 0))
        desc     = _WMO_CODES.get(code, f"Conditions (code {code})")

        try:
            temp_c  = round((float(temp_f)  - 32) * 5 / 9, 1)
            feels_c = round((float(feels_f) - 32) * 5 / 9, 1)
        except Exception:
            temp_c = feels_c = "N/A"

        precip_note = f" Precipitation: {precip} in." if precip and float(precip) > 0 else ""
        return (
            f"Real-time weather in {city_display} ({appointment_date}): {desc}. "
            f"{temp_f}°F ({temp_c}°C), feels like {feels_f}°F ({feels_c}°C). "
            f"Wind: {wind} mph.{precip_note}"
        )
    except Exception as exc:
        return f"Weather service temporarily unavailable ({exc}). Please check weather.com for {city}."


def _osrm_fallback(from_city: str, to_address: str, preamble: str = "") -> str:
    """OSRM open routing — free, no API key, no live traffic."""
    origin = _geocode(from_city)
    if origin is None:
        return f"{preamble}Could not locate '{from_city}' for routing."
    olat, olon, origin_name = origin

    # Geocode the nearest real hospital via Nominatim (OpenStreetMap)
    dest = _geocode_hospital(from_city)
    if dest is None:
        return f"{preamble}Could not find a medical destination near {from_city}."
    dlat, dlon, dest_name = dest

    # Guard: skip OSRM if origin and dest resolved to the same point
    if abs(olat - dlat) < 0.001 and abs(olon - dlon) < 0.001:
        return (
            f"{preamble}Could not find a distinct medical destination near {from_city}. "
            "Please check Google Maps for directions to City Health Clinic."
        )
    try:
        r = requests.get(
            f"http://router.project-osrm.org/route/v1/driving/{olon},{olat};{dlon},{dlat}",
            params={"overview": "false", "alternatives": "true"},
            timeout=12,
        ).json()
        if r.get("code") != "Ok":
            return f"{preamble}Route calculation unavailable. Please check Google Maps."
        lines = [f"{preamble}🗺️ Estimated routes from {origin_name} toward {to_address}:"]
        for i, route in enumerate(r.get("routes", [])[:3], 1):
            dist_mi = route["distance"] / 1609.34
            dur_min = round(route["duration"] / 60)
            lines.append(f"  Route {i}: {dist_mi:.1f} mi — ~{dur_min} min (estimated, no live traffic).")
        lines.append("  ℹ️ Enable Google Maps Directions API for live traffic & exact address.")
        return "\n".join(lines)
    except Exception as exc:
        return f"{preamble}Routing service unavailable ({exc}). Please check Google Maps."


@tool
def get_traffic_route(from_city: str, to_address: str) -> str:
    """
    Get route options from a city to the clinic.
    Uses Google Maps Directions API (live traffic) when GOOGLE_MAPS_API_KEY is set and valid;
    falls back to OSRM open routing (free, no key) otherwise.
    """
    # ── Google Maps (live traffic, multiple named routes) ────────────────────
    if GOOGLE_MAPS_API_KEY:
        try:
            resp = requests.get(
                "https://maps.googleapis.com/maps/api/directions/json",
                params={
                    "origin":         from_city,
                    "destination":    to_address,
                    "departure_time": "now",
                    "alternatives":   "true",
                    "traffic_model":  "best_guess",
                    "key":            GOOGLE_MAPS_API_KEY,
                },
                timeout=15,
            ).json()
            status = resp.get("status")
            if status == "OK":
                routes = resp.get("routes", [])
                # Sanity check: if best route < 0.1 mi the destination resolved
                # to the same location as origin (fictional clinic name collision)
                best_dist_m = routes[0]["legs"][0]["distance"]["value"] if routes else 0
                if best_dist_m < 160:  # < 0.1 miles → bad match, fall to OSRM
                    preamble = ""
                else:
                    lines = [f"🗺️ Live routes from {from_city} to {to_address}:"]
                    for i, route in enumerate(routes[:3], 1):
                        leg    = route["legs"][0]
                        via    = route.get("summary", f"Route {i}")
                        dist   = leg["distance"]["text"]
                        dur    = leg["duration"]["text"]
                        dur_tx = leg.get("duration_in_traffic", {}).get("text", dur)
                        lines.append(
                            f"  Route {i} via {via}: {dist} — "
                            f"~{dur_tx} with live traffic (normally {dur})."
                        )
                    return "\n".join(lines)
            elif status == "REQUEST_DENIED":
                preamble = (
                    "⚠️ Google Maps API key is set but REQUEST_DENIED. "
                    "Fix: go to Google Cloud Console → APIs & Services → "
                    "enable 'Directions API' and ensure billing is active. "
                    "Showing estimated route via open routing:\n"
                )
            else:
                preamble = f"⚠️ Google Maps unavailable (status: {status}). Estimated route:\n"
        except Exception as exc:
            preamble = f"⚠️ Google Maps error ({exc}). Estimated route:\n"
    else:
        preamble = ""

    # ── OSRM fallback ────────────────────────────────────────────────────────
    return _osrm_fallback(from_city, to_address, preamble)


# Coordinator only uses PRM tools. Weather/hospital/route info is handled by the
# UI pipeline (_run_appointment_pipeline + get_directions), not by the chat LLM.
llm_with_tools = llm.bind_tools([get_prm_score, flag_clinical_review])
_TOOLS_MAP     = {t.name: t for t in [get_prm_score, flag_clinical_review]}


# ---------------------------------------------------------------------------
# 3. Sentiment Detection Chain  (05_branch.py pattern)
# ---------------------------------------------------------------------------

positive_template = ChatPromptTemplate.from_messages([
    ("system", "You are a compassionate patient relations specialist at a healthcare clinic."),
    ("human",
     "A patient has sent the following message with a positive tone.\n"
     "Respond warmly and helpfully based on exactly what they said: "
     "if they report improvement, acknowledge it and reinforce their care plan; "
     "if they are requesting an appointment or asking a question, assist with that directly.\n\n"
     "Patient message: {feedback}")
])

negative_template = ChatPromptTemplate.from_messages([
    ("system", "You are a compassionate clinical care coordinator at a healthcare clinic."),
    ("human",
     "A patient has sent the following message expressing distress or worsening symptoms.\n"
     "Respond empathetically based on exactly what they said: "
     "validate their experience, outline concrete supportive next steps the care team will take, "
     "and assist with any specific request they made (such as scheduling an appointment).\n\n"
     "Patient message: {feedback}")
])

neutral_template = ChatPromptTemplate.from_messages([
    ("system", "You are an attentive patient support coordinator at a healthcare clinic."),
    ("human",
     "A patient has sent the following message with a neutral tone.\n"
     "Respond helpfully and directly based on exactly what they said: "
     "if they are requesting an appointment or logistics help, acknowledge and assist with that; "
     "if they are reporting unclear symptoms, ask two focused follow-up questions; "
     "if they are asking a factual question, answer it concisely.\n\n"
     "Patient message: {feedback}")
])

escalate_template = ChatPromptTemplate.from_messages([
    ("system", "You are a patient safety officer at a healthcare clinic."),
    ("human",
     "A patient has sent the following message indicating severe distress or a safety concern.\n"
     "Write a calm, reassuring response that immediately connects them with a clinician or "
     "crisis support resource, confirms escalation, and addresses any specific request they made.\n\n"
     "Patient message: {feedback}")
])

classification_template = ChatPromptTemplate.from_messages([
    ("system",
     "You are a sentiment analysis expert specialising in healthcare patient-reported outcomes. "
     "Use 'escalate' when the patient expresses severe distress, hopelessness, or any safety concern."),
    ("human",
     "Classify the following patient feedback as exactly one of: "
     "'positive', 'negative', 'neutral', or 'escalate'. "
     "Feedback: {feedback}")
])

# RunnableBranch routes on the label string; the selected chain receives {feedback}.
# NOTE: invoke via _invoke_branch() so {feedback} gets the real user message,
# not just the label word.
_BRANCH_TEMPLATES = {
    "positive": positive_template,
    "negative": negative_template,
    "neutral":  neutral_template,
    "escalate": escalate_template,
}

branches = RunnableBranch(
    (lambda x: "positive" in x.lower(), positive_template | llm | StrOutputParser()),
    (lambda x: "negative" in x.lower(), negative_template | llm | StrOutputParser()),
    (lambda x: "neutral"  in x.lower(), neutral_template  | llm | StrOutputParser()),
    escalate_template | llm | StrOutputParser()
)


def _invoke_branch(label: str, user_message: str) -> str:
    """Route to the right template and pass the actual user message as {feedback}."""
    template = _BRANCH_TEMPLATES.get(label, escalate_template)
    return (template | llm | StrOutputParser()).invoke({"feedback": user_message})


classify_chain  = classification_template | llm | StrOutputParser()
sentiment_chain = classify_chain | branches

# ---------------------------------------------------------------------------
# 4. Appointment Planning Pipeline  (03-state-management.py pattern)
# ---------------------------------------------------------------------------

def _extract_city(user_message: str) -> str:
    """LLM-based city+state extractor.
    State is REQUIRED — many US cities share the same name across states.
    Returns 'City, ST' on success, 'unknown' if state is absent or no city found.
    """
    prompt = (
        f"Extract the US city name AND its two-letter state abbreviation from this sentence. "
        f"The state abbreviation is REQUIRED — do not return a city without one, "
        f"because many US cities share the same name across states (e.g. Springfield exists in IL, MO, OH, and more). "
        f"Correct obvious city-name misspellings (e.g. 'Los Angelas' → 'Los Angeles'). "
        f"Convert full state names to two-letter abbreviations (e.g. Texas → TX, California → CA). "
        f"Return ONLY 'City, ST' format (e.g. 'Richardson, TX'). "
        f"If no state is mentioned or no city is mentioned, return 'unknown'. "
        f"Sentence: '{user_message}'"
    )
    return llm.invoke(prompt).content.strip()


def _run_appointment_pipeline(user_message: str, city: str = ""):
    """
    hospitals → weather_agent
    city is pre-supplied by _detect_location_intent (spelling-corrected).
    Falls back to _extract_city if not provided.
    Traffic route is NOT pre-computed here; calculated on demand via Get Directions.
    Returns (city, hospitals_list, hospitals_html, weather_html, traffic_placeholder).
    """
    if not city or city.lower() in ("unknown", "needs_state"):
        city = _extract_city(user_message)
    # _extract_city now returns 'unknown' when state is absent — propagate that
    if not city or city.lower() in ("unknown", "needs_state"):
        city = "unknown"

    hospitals = _find_nearby_hospitals(city)
    hosp_html = _hospitals_html(hospitals, city)

    today_str = date.today().strftime("%B %d, %Y")
    weather_text = get_weather_for_appointment.invoke(
        {"city": city, "appointment_date": today_str}
    )

    # 35-day daily grid — reuses the geocode coords
    forecast_grid_html = ""
    coords = _geocode(city)
    if coords:
        try:
            forecast_grid_html = _extended_forecast_html(coords[0], coords[1])
        except Exception:
            pass

    weather_html = (
        f'<div style="background:#1565C0;border-radius:8px;padding:12px;margin-bottom:4px;">'
        f'  <div style="font-size:0.95rem;font-weight:700;color:#ffffff;">🌤️ Weather Forecast</div>'
        f'  <div style="font-size:0.83rem;color:#ffffff;margin-top:6px;line-height:1.5;">{weather_text}</div>'
        f'</div>'
        f'{forecast_grid_html}'
    )

    traffic_html = """
<div style="background:#eeeeee;border-radius:8px;padding:12px;color:#555;font-size:0.83rem;">
  👆 Select a hospital above and click <strong>Get Directions</strong> to see routes from your location.
</div>"""

    return city, hospitals, hosp_html, weather_html, traffic_html


# ---------------------------------------------------------------------------
# 5. Care Coordinator Agent
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a compassionate and professional patient care coordinator. "
    "Follow up with patients about their Patient Reported Measures (PRMs): "
    "PHQ-9 (depression), GAD-7 (anxiety), pain scale, and EQ-5D (quality of life). "
    "Use get_prm_score to retrieve the patient's latest scores (patient ID: P-1042) before discussing them. "
    "Use flag_clinical_review immediately if any score indicates severe distress or a safety concern. "
    "Be empathetic, clear, and concise. Never diagnose — always guide toward the appropriate clinician.\n\n"
    "APPOINTMENT SCHEDULING RULE: "
    "Whenever you flag a clinical review, mention a clinician follow-up, or identify a concerning PRM score, "
    "you MUST recommend an in-person appointment.\n"
    "— If the patient's current message does NOT contain both a city AND a state, ask once: "
    "'Could you share your current city and state? For example: \\'I am in Richardson, TX\\'. "
    "Many US city names are shared across states, so both are needed to find the right hospitals near you.'\n"
    "— ONLY IF the patient's current message explicitly contains both a city AND a state "
    "(e.g. 'I am in Newport News, VA' or 'I\\'m currently in Plano, TX'), "
    "acknowledge it: 'Thank you — the nearby hospitals and weather for [city, state] "
    "are now shown in the panel on the right. Please select a hospital and click Get Directions.'\n"
    "— If the patient mentions a city WITHOUT a state, ask them to add the state: "
    "'Could you also share your state? For example, \\'Richardson, TX\\'. "
    "This helps me find the correct hospitals since many cities share the same name.'\n"
    "— NEVER say a city was shared if the patient\\'s current message does not contain one. "
    "Do not assume or hallucinate a city or state from prior conversation turns.\n\n"
    "IMPORTANT — do NOT invent travel times, distances, weather, or hospital names. "
    "That information is shown automatically in the sidebar. "
    "Do NOT book or suggest specific appointment dates — "
    "tell the patient to contact the chosen hospital directly to schedule."
)


def _run_coordinator(lc_messages: List[BaseMessage]) -> str:
    """Run the care coordinator with a manual tool loop; return the final text reply."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="messages"),
    ])
    working = list(lc_messages)

    for _ in range(5):  # max tool round-trips
        response = (prompt | llm_with_tools).invoke({"messages": working})

        if not (hasattr(response, "tool_calls") and response.tool_calls):
            return response.content

        # Append the assistant message with tool calls
        working.append(response)

        # Execute each tool call directly — avoids ToolNode graph-config requirement
        for tc in response.tool_calls:
            tool_fn = _TOOLS_MAP.get(tc["name"])
            if tool_fn:
                result = tool_fn.invoke(tc["args"])
                working.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

    return response.content  # fallback after 5 iterations

# ---------------------------------------------------------------------------
# 5. Intent detection  (LLM-based — replaces keyword/regex pipeline trigger)
# ---------------------------------------------------------------------------

def _msg_text(content) -> str:
    """Extract plain text from Gradio message content (str or list of parts)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            p.get("text", "") if isinstance(p, dict) else str(p) for p in content
        )
    return str(content)


def _detect_location_intent(user_message: str, history: list) -> dict:
    """
    Ask the LLM whether this message should trigger the Appointment Assistant panel.
    Returns {"trigger": bool, "city": "City ST"}  — city is spelling-corrected,
    "unknown" when no city is mentioned.

    Handles any natural phrasing ("find other clinicians", "Seattle WA", "I need a new
    doctor near me", misspelled cities, etc.) without keyword lists or regexes.
    """
    import json as _json

    # Include last 4 turns so the model sees if the assistant previously asked for a city
    recent_lines = [
        f'{"Patient" if m["role"] == "user" else "Assistant"}: {_msg_text(m["content"])}'
        for m in history[-4:]
    ]
    context_block = ("\nRecent conversation:\n" + "\n".join(recent_lines) + "\n") if recent_lines else ""

    prompt = (
        "You are a routing classifier for a healthcare patient app.\n\n"
        "Decide whether to activate the Appointment Assistant panel.\n"
        "Set trigger=true when the patient is doing ANY of the following:\n"
        "  • Mentioning their current city, town, or location (e.g. 'I am in Richardson TX', "
        "'I live in Boston', 'I'm currently in Chicago, IL', 'my city is Denver CO')\n"
        "  • Asking to find a nearby hospital, clinic, doctor, or clinician\n"
        "  • Requesting, scheduling, or booking an appointment\n"
        "  • Saying they need urgent care or want to see someone\n"
        "IMPORTANT: sharing a city name alone (with no other context) is ALWAYS trigger=true.\n"
        "Set trigger=false ONLY for: general health discussion, PRM score questions, "
        "emotional expression with no location/provider-seeking intent, or greetings.\n\n"
        "Also extract the US city AND state (both required — many cities share names across states). "
        "Convert full state names to 2-letter abbreviations (e.g. Texas→TX, California→CA). "
        "Return city as 'City ST' format (e.g. 'Richardson TX'). "
        "If city is mentioned WITHOUT a state, return city='needs_state'. "
        "Return city='unknown' only when no city is mentioned at all.\n"
        + context_block
        + f'\nCurrent patient message: "{user_message}"\n\n'
        "Reply with ONLY valid JSON, no markdown fences:\n"
        '{"trigger": true, "city": "City ST"}'
    )
    try:
        raw = llm.invoke(prompt).content.strip()
        # Strip markdown code fences if the model adds them
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
        result = _json.loads(raw)
        return {
            "trigger": bool(result.get("trigger", False)),
            "city":    str(result.get("city", "unknown")).strip(),
        }
    except Exception:
        return {"trigger": False, "city": "unknown"}


# ---------------------------------------------------------------------------
# 6. UI helpers
# ---------------------------------------------------------------------------

_COLORS = {
    "positive": "#27ae60",
    "negative": "#e74c3c",
    "neutral":  "#f39c12",
    "escalate": "#8e44ad",
}
_EMOJI = {
    "positive": "😊",
    "negative": "😔",
    "neutral":  "😐",
    "escalate": "🚨",
}


def _sentiment_card(sentiment: str, user_text: str = "") -> str:
    color = _COLORS.get(sentiment, "#7f8c8d")
    emoji = _EMOJI.get(sentiment, "💬")
    quote = (
        f'<div style="font-size:0.82rem;color:#ffffffcc;margin-top:8px;'
        f'font-style:italic;line-height:1.45;">'
        f'&ldquo;{user_text}&rdquo;</div>'
    ) if user_text else ""
    return f"""
<div style="border:2px solid {color};border-radius:10px;padding:14px;
            background:{color};margin-bottom:12px;">
  <div style="font-size:1.35rem;font-weight:700;color:#ffffff;">
    {emoji}&nbsp;{sentiment.upper()}
  </div>
  {quote}
</div>"""


_READY_CARD = _sentiment_card("neutral")

# ---------------------------------------------------------------------------
# 6. Gradio callbacks
# ---------------------------------------------------------------------------

_APPT_PLACEHOLDER = """
<div style="background:#eeeeee;border-radius:8px;padding:12px;color:#888;
            font-size:0.83rem;font-style:italic;">
  Mention an appointment or clinic visit to see weather and route info here.
</div>"""

_MAP_PLACEHOLDER = """
<div style="background:#eeeeee;border-radius:8px;padding:12px;color:#888;
            font-size:0.83rem;font-style:italic;">
  Select a hospital and click Get Directions to view the route map here.
</div>"""


def _pill_label(icon: str, text: str) -> str:
    """Ellipse pill label with light-blue background used as section headers."""
    return (
        '<div style="margin:10px 0 4px;">'
        '<span style="display:inline-block;background:#e3f2fd;'
        'border:1.5px solid #1565C0;border-radius:50px;'
        'padding:4px 16px;font-size:0.78rem;font-weight:700;color:#1565C0;">'
        f'{icon}&nbsp;{text}'
        '</span></div>'
    )


def _map_embed_html(origin: str, destination: str) -> str:
    """Return a Google Maps Embed iframe (with API key) or an Open-in-Maps link (without)."""
    origin_enc = _url_quote(origin)
    dest_enc   = _url_quote(destination)
    if GOOGLE_MAPS_API_KEY:
        src = (
            "https://www.google.com/maps/embed/v1/directions"
            f"?key={GOOGLE_MAPS_API_KEY}"
            f"&origin={origin_enc}"
            f"&destination={dest_enc}"
            "&mode=driving"
        )
        return f"""
<div style="border-radius:8px;overflow:hidden;margin-top:8px;">
  <div style="font-size:0.88rem;font-weight:700;color:#1565C0;margin-bottom:4px;">🗺️ Route Map</div>
  <iframe
    width="100%" height="320"
    style="border:0;display:block;border-radius:8px;"
    loading="lazy"
    allowfullscreen
    referrerpolicy="no-referrer-when-downgrade"
    src="{src}">
  </iframe>
</div>"""
    else:
        maps_url = (
            "https://www.google.com/maps/dir/?api=1"
            f"&origin={origin_enc}"
            f"&destination={dest_enc}"
            "&travelmode=driving"
        )
        return f"""
<div style="background:#e8f5e9;border-radius:8px;padding:12px;
            text-align:center;margin-top:8px;">
  <div style="font-size:0.82rem;color:#555;margin-bottom:8px;">
    Add <code>GOOGLE_MAPS_API_KEY</code> to embed the map directly.
  </div>
  <a href="{maps_url}" target="_blank"
     style="display:inline-block;background:#2e7d32;color:#fff;
            padding:9px 18px;border-radius:6px;text-decoration:none;
            font-size:0.88rem;font-weight:700;">
    📍 Open Route in Google Maps ↗
  </a>
</div>"""


def respond(
    user_message: str,
    history: List[dict],
):
    """Return updated history, cleared input, sentiment card, hospitals panel,
    hospital radio update, city state, weather panel, traffic panel."""
    _blank = (history, "", _READY_CARD, _APPT_PLACEHOLDER,
               gr.Radio(choices=[], visible=False), "", [], _APPT_PLACEHOLDER, _APPT_PLACEHOLDER, _MAP_PLACEHOLDER)
    if not user_message.strip():
        return _blank

    # --- Sentiment detection (05_branch.py pattern) ---
    label = classify_chain.invoke({"feedback": user_message}).strip().lower()
    if "positive" in label:
        sentiment = "positive"
    elif "negative" in label:
        sentiment = "negative"
    elif "neutral" in label:
        sentiment = "neutral"
    else:
        sentiment = "escalate"

    # --- Appointment planning pipeline (03-state-management.py pattern) ---
    hosp_html    = _APPT_PLACEHOLDER
    radio_update = gr.Radio(choices=[], visible=False)
    city_val     = ""
    hospitals    = []
    weather_html = _APPT_PLACEHOLDER
    traffic_html = _APPT_PLACEHOLDER

    # Single LLM call: detect intent + extract/correct city name
    intent = _detect_location_intent(user_message, history)

    # Safety-net: if the LLM didn't trigger but the message contains a clear
    # location+appointment signal, force-trigger with a regex-extracted city.
    if not intent["trigger"]:
        _appt_re = re.search(
            r"\b(appointment|schedule|hospital|clinic|doctor|clinician|book|visit)\b",
            user_message, re.I,
        )

        # Three passes for city detection. "is" covers "my city is X".
        # State is enforced by the _has_state() gate below — not here.

        # Pass 1: "in/from/near/at/is City ST"  or  "City, ST"
        _city_abbrev = re.search(
            r"\b(?:in|from|near|at|is)\s+([A-Za-z][A-Za-z ]{1,20}?)(?:,?\s+([A-Z]{2}))\b",
            user_message,
        )
        # Pass 2: "in/from/near/at/is City StateName"  (full name → abbrev in extraction below)
        _state_names_pat = (
            r"Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|"
            r"Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|"
            r"Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|"
            r"Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|"
            r"New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|"
            r"Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|"
            r"Virginia|Washington|West Virginia|Wisconsin|Wyoming"
        )
        _city_fullstate = re.search(
            r"\b(?:in|from|near|at|is)\s+([A-Za-z][A-Za-z ]{1,20}?),?\s+("
            + _state_names_pat + r")\b",
            user_message, re.I,
        )
        # Pass 3: city-only — triggers the intent so the missing-state panel is shown;
        # the _has_state() gate below prevents the pipeline from running without a state.
        _city_only = re.search(
            r"\b(?:in|from|near|at|is)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)"
            r"(?=\s*[.!?,\-—]|\s+(?:now|here|and|but|so|the|I|can|please|help|there|—)|$)",
            user_message,
        )

        _city_re = _city_abbrev or _city_fullstate or _city_only

        if _appt_re or _city_re:
            intent["trigger"] = True
            if _city_re and intent["city"] in ("unknown", "needs_state"):
                if _city_abbrev:
                    city_name  = _city_abbrev.group(1).strip()
                    state_abbr = _city_abbrev.group(2)
                    intent["city"] = f"{city_name} {state_abbr}"
                elif _city_fullstate:
                    city_name  = _city_fullstate.group(1).strip().rstrip(",")
                    state_full = _city_fullstate.group(2).strip()
                    _ST_MAP = {
                        "Alabama":"AL","Alaska":"AK","Arizona":"AZ","Arkansas":"AR",
                        "California":"CA","Colorado":"CO","Connecticut":"CT",
                        "Delaware":"DE","Florida":"FL","Georgia":"GA","Hawaii":"HI",
                        "Idaho":"ID","Illinois":"IL","Indiana":"IN","Iowa":"IA",
                        "Kansas":"KS","Kentucky":"KY","Louisiana":"LA","Maine":"ME",
                        "Maryland":"MD","Massachusetts":"MA","Michigan":"MI",
                        "Minnesota":"MN","Mississippi":"MS","Missouri":"MO",
                        "Montana":"MT","Nebraska":"NE","Nevada":"NV",
                        "New Hampshire":"NH","New Jersey":"NJ","New Mexico":"NM",
                        "New York":"NY","North Carolina":"NC","North Dakota":"ND",
                        "Ohio":"OH","Oklahoma":"OK","Oregon":"OR",
                        "Pennsylvania":"PA","Rhode Island":"RI","South Carolina":"SC",
                        "South Dakota":"SD","Tennessee":"TN","Texas":"TX",
                        "Utah":"UT","Vermont":"VT","Virginia":"VA",
                        "Washington":"WA","West Virginia":"WV","Wisconsin":"WI",
                        "Wyoming":"WY",
                    }
                    abbr = _ST_MAP.get(state_full.title(), state_full[:2].upper())
                    intent["city"] = f"{city_name} {abbr}"
                else:
                    # Pass 3: city without state — store bare city name so _has_state() returns False
                    intent["city"] = _city_only.group(1).strip()

    if intent["trigger"]:
        _detected_city = intent["city"]
        # Gate: state is mandatory. If city is missing or has no state, show prompt instead.
        if _detected_city in ("unknown", "needs_state") or not _has_state(_detected_city):
            hosp_html = _missing_state_html(
                _detected_city if _detected_city not in ("unknown", "needs_state") else ""
            )
        else:
            try:
                city_val, hospitals, hosp_html, weather_html, traffic_html = \
                    _run_appointment_pipeline(user_message, city=_detected_city)
                if hospitals:
                    choices = [
                        f"#{i} {h['name']} ({h['dist_mi']:.1f} mi)"
                        for i, h in enumerate(hospitals, 1)
                    ]
                    radio_update = gr.Radio(
                        choices=choices, value=None, visible=True,
                        label="Select a hospital then click Get Directions ↓",
                    )
            except Exception as _exc:
                print(f"[pipeline error] {_exc}")

    # --- Build LangChain message history ---
    lc_messages: List[BaseMessage] = []
    for msg in history:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=_msg_text(msg["content"])))
        elif msg["role"] == "assistant":
            lc_messages.append(AIMessage(content=_msg_text(msg["content"])))
    lc_messages.append(HumanMessage(content=user_message))

    # --- Run care coordinator ---
    try:
        reply = _run_coordinator(lc_messages)
    except Exception as exc:
        reply = f"I'm sorry, something went wrong: {exc}"

    new_history = history + [
        {"role": "user",      "content": user_message},
        {"role": "assistant", "content": reply},
    ]
    return new_history, "", _sentiment_card(sentiment, user_message), hosp_html, radio_update, city_val, hospitals, weather_html, traffic_html, _MAP_PLACEHOLDER


def get_directions(selected_hospital: str, city: str, hospitals_data: list):
    """Recalculate traffic route and map for the selected hospital.
    Uses the hospital's Nominatim coordinates so the map and route text are
    always consistent — no geocoding ambiguity from bare hospital names.
    Returns (traffic_html, map_html).
    """
    if not selected_hospital or not city:
        return _APPT_PLACEHOLDER, _MAP_PLACEHOLDER

    # Parse the 1-based index from the radio label "#1 Hospital Name (0.5 mi)"
    m_idx = re.match(r"#(\d+)\s+", selected_hospital)
    hosp = None
    if m_idx and hospitals_data:
        idx = int(m_idx.group(1)) - 1
        if 0 <= idx < len(hospitals_data):
            hosp = hospitals_data[idx]

    if hosp:
        # Precise coordinate-based destination — eliminates all geocoding ambiguity
        dest_coord   = f"{hosp['lat']},{hosp['lon']}"
        hospital_label = hosp["name"]
    else:
        # Fallback: use name + city for a more qualified search
        m_name = re.match(r"#\d+\s+(.+?)\s+\(\d", selected_hospital)
        hospital_label = m_name.group(1) if m_name else selected_hospital
        dest_coord   = f"{hospital_label}, {city}"

    traffic_text = get_traffic_route.invoke(
        {"from_city": city, "to_address": dest_coord}
    )
    traffic_html = f"""
<div style="background:#2e7d32;border-radius:8px;padding:12px;">
  <div style="font-size:0.95rem;font-weight:700;color:#ffffff;">🚗 Travel & Route to {hospital_label}</div>
  <div style="font-size:0.83rem;color:#ffffff;margin-top:6px;line-height:1.5;">{traffic_text}</div>
</div>"""
    map_html = _map_embed_html(city, dest_coord)
    return traffic_html, map_html


def clear_conversation():
    return [], "", _READY_CARD, _APPT_PLACEHOLDER, gr.Radio(choices=[], visible=False), "", [], _APPT_PLACEHOLDER, _APPT_PLACEHOLDER, _MAP_PLACEHOLDER


# ---------------------------------------------------------------------------
# 7. Gradio layout  (follows reference ui/app.py conventions)
# ---------------------------------------------------------------------------

_CSS = """
.gradio-container { max-width: 1280px !important; margin: 0 auto; }
.tab-nav button    { font-size: 0.92rem; }

/* Quick-starter group colour bands */
.starter-blue   button { background:#e3f2fd !important; border:1px solid #1565C0 !important; color:#1565C0 !important; font-weight:600 !important; }
.starter-orange button { background:#fff3e0 !important; border:1px solid #e65100 !important; color:#e65100 !important; font-weight:600 !important; }
.starter-green  button { background:#e8f5e9 !important; border:1px solid #2e7d32 !important; color:#2e7d32 !important; font-weight:600 !important; }
.starter-purple button { background:#f3e5f5 !important; border:1px solid #6a1b9a !important; color:#6a1b9a !important; font-weight:600 !important; }
"""

_SAMPLE_GROUPS = [
    ("starter-blue", "📋 Understanding Scores", [
        "I just received my questionnaire results and I'm not sure what they mean.",
        "What does my PHQ-9 score of 14 mean for my treatment?",
        "Can you explain what the EQ-5D quality of life score measures?",
        "What does a GAD-7 score of 11 indicate about my anxiety level?",
        "How does my pain scale score of 7 compare to the normal range?",
        "My EQ-5D score dropped since last month — what does that mean?",
        "Can you walk me through what each PRM questionnaire is measuring?",
        "What is considered a normal range for the PHQ-9 depression score?",
        "How often should I be submitting my PRM questionnaires?",
    ]),
    ("starter-orange", "😔 Worsening Symptoms", [
        "I've been feeling exhausted and really low for the past few weeks.",
        "My anxiety feels overwhelming — I can't stop worrying about everything.",
        "My pain level is around 7 or 8 most days and it's affecting my sleep.",
        "My depression has been getting worse — I scored a 17 on my PHQ-9.",
        "I've been skipping meals and losing weight because of my anxiety.",
        "My quality of life has dropped — I can barely manage my daily tasks.",
        "I've stopped doing activities I used to enjoy because of the pain.",
        "My GAD-7 score went up to 15 this month — I feel out of control.",
        "I've been having panic attacks several times a week lately.",
    ]),
    ("starter-green", "😊 Improving", [
        "I think I'm doing a bit better — my mood has improved since last month.",
        "My pain has improved to a 3 — the new medication is helping!",
        "I've been sleeping better and feeling less anxious this week.",
        "My PHQ-9 score went down from 14 to 8 — the therapy is working!",
        "I've been able to go for walks again — my pain is much more manageable.",
        "My GAD-7 score improved to 6 — the breathing exercises really help.",
        "I feel more hopeful about my recovery after my last appointment.",
        "My EQ-5D score improved — I'm back to most of my daily activities.",
        "I completed all my PRM questionnaires on time this month — feeling good!",
    ]),
    ("starter-purple", "🚨 Escalate & Appointment", [
        "I honestly don't see the point in continuing treatment anymore.",
        "Yes, I'd like to schedule an appointment. I'm currently in [city], [state].",
        "I'm in [city], [state] — can you help me book an appointment?",
        "I've been feeling hopeless and don't want to get out of bed anymore.",
        "My pain has become unbearable — I need to see someone urgently.",
        "I need to see a doctor soon. I'm currently located in [city], [state].",
        "Can you find me a nearby hospital? I'm currently in [city], [state].",
        "I've been having thoughts I shouldn't be having and need help now.",
        "I want to visit a hospital near me. My city is [city], [state].",
    ]),
]

with gr.Blocks(title="PRM Care Coordinator") as demo:

    gr.Markdown("""
# 🏥 PRM Care Coordinator
**AI-powered follow-up for Patient Reported Measures — PHQ-9 · GAD-7 · Pain Scale · EQ-5D**

Chat with your care coordinator about your recent health questionnaire results.
Sentiment is detected on every message and shapes the coordinator's response style.
""")

    with gr.Tabs():

        # ── Tab 1: Chat ───────────────────────────────────────────────────────
        with gr.TabItem("Chat with Coordinator"):
            with gr.Row(equal_height=False):

                # Left column — conversation
                with gr.Column(scale=3):
                    chatbot = gr.Chatbot(
                        value=[],
                        label="Conversation",
                        height=500,
                        avatar_images=(None, "https://cdn-icons-png.flaticon.com/512/4228/4228704.png"),
                    )
                    with gr.Row():
                        msg_input = gr.Textbox(
                            placeholder="Describe how you are feeling, or ask about your PRM scores…",
                            label="Your message",
                            lines=2,
                            scale=5,
                            show_label=False,
                        )
                        send_btn = gr.Button("Send ➤", variant="primary", scale=1)
                    clear_btn = gr.Button("🗑️  Start New Conversation", variant="secondary")

                    gr.Markdown("**Quick starters — click to load [modified as needed]:**")
                    for css_cls, group_label, group_samples in _SAMPLE_GROUPS:
                        gr.HTML(
                            f'<div style="font-size:0.75rem;font-weight:700;'
                            f'margin:8px 0 2px;letter-spacing:0.02em;">{group_label}</div>'
                        )
                        for row_start in range(0, len(group_samples), 3):
                            with gr.Row(elem_classes=[css_cls]):
                                for s in group_samples[row_start:row_start + 3]:
                                    gr.Button(s, size="sm").click(
                                        fn=lambda txt=s: txt, outputs=msg_input
                                    )

                # Right column — sentiment + appointment assistant + PRM panel
                with gr.Column(scale=1, min_width=260):
                    city_state      = gr.State("")
                    hospitals_state = gr.State([])

                    gr.Markdown("### 📊 Sentiment")
                    sentiment_panel = gr.HTML(value=_READY_CARD)

                    gr.Markdown("### 📅 Appointment Assistant")
                    gr.HTML(_pill_label("🏥", "Top 5 Hospital Recommended"))
                    hospitals_panel = gr.HTML(value=_APPT_PLACEHOLDER)
                    hospital_radio  = gr.Radio(choices=[], visible=False,
                                               label="Select a hospital then click Get Directions ↓")
                    directions_btn  = gr.Button("🗺️ Get Directions to Selected Hospital",
                                                variant="primary", visible=True, size="sm")
                    gr.HTML(_pill_label("🌤️", "Today's Weather"))
                    weather_panel   = gr.HTML(value=_APPT_PLACEHOLDER)
                    gr.HTML(_pill_label("🚗", "Today's Traffic Time"))
                    traffic_panel   = gr.HTML(value=_APPT_PLACEHOLDER)
                    gr.HTML(_pill_label("🗺️", "Today's Traffic Live Map"))
                    map_panel       = gr.HTML(value=_MAP_PLACEHOLDER)

                    gr.HTML("""
<hr>
<div style="font-size:1rem;font-weight:700;margin-bottom:8px;">📋 Your Latest PRM Scores</div>
<table style="width:100%;border-collapse:collapse;font-size:0.88rem;">
  <thead>
    <tr style="background:#1e3a5f;color:#ffffff;">
      <th style="padding:8px 10px;text-align:left;width:30%;">Measure</th>
      <th style="padding:8px 10px;text-align:center;width:20%;">Score</th>
      <th style="padding:8px 10px;text-align:left;width:50%;">Severity</th>
    </tr>
  </thead>
  <tbody>
    <tr style="background:#fef9e7;">
      <td style="padding:8px 10px;font-weight:600;color:#000000;">PHQ-9</td>
      <td style="padding:8px 10px;text-align:center;font-weight:700;color:#000000;">14</td>
      <td style="padding:8px 10px;font-weight:700;color:#000000;">Moderate depression</td>
    </tr>
    <tr style="background:#ffffff;">
      <td style="padding:8px 10px;font-weight:700;color:#000000;">GAD-7</td>
      <td style="padding:8px 10px;text-align:center;font-weight:700;color:#000000;">11</td>
      <td style="padding:8px 10px;font-weight:700;color:#000000;">Moderate anxiety</td>
    </tr>
    <tr style="background:#fef9e7;">
      <td style="padding:8px 10px;font-weight:700;color:#000000;">Pain</td>
      <td style="padding:8px 10px;text-align:center;font-weight:700;color:#000000;">7/10</td>
      <td style="padding:8px 10px;font-weight:700;color:#000000;">Severe</td>
    </tr>
    <tr style="background:#ffffff;">
      <td style="padding:8px 10px;font-weight:700;color:#000000;">EQ-5D</td>
      <td style="padding:8px 10px;text-align:center;font-weight:700;color:#000000;">0.62</td>
      <td style="padding:8px 10px;font-weight:700;color:#000000;">Below norm</td>
    </tr>
  </tbody>
</table>
<p style="font-size:0.78rem;color:#888;margin-top:6px;font-style:italic;">
  Ask the coordinator to explain any score or next steps.
</p>
""")

        # ── Tab 2: About ──────────────────────────────────────────────────────
        with gr.TabItem("About"):
            gr.Markdown("""
## About This App

This app is an AI-powered **care coordinator follow-up** for patients who have submitted
Patient Reported Measures (PRMs). It combines:

- **LangChain `RunnableBranch`** for sentiment-driven response routing
- **LangChain manual tool loop** for conditional PRM tool use (up to 5 round-trips)
- **LLM-based intent detection** to trigger the Appointment Assistant panel
- **Appointment Assistant** with hospital finder, 35-day weather forecast, and driving directions

---

### Architecture
```
User message
    │
    ▼
Sentiment Detector  ← classification_template | LLM | StrOutputParser()
    │                         │
    └── RunnableBranch ──► positive / negative / neutral / escalate note
    │
    ▼
Intent Detector  ← LLM JSON classifier (_detect_location_intent)
    │
    ├── trigger=true ──► Appointment Assistant Pipeline
    │                       ├── Nominatim geocoding (state-aware)
    │                       ├── Nearby hospital search (OpenStreetMap)
    │                       ├── 35-day weather forecast (Open-Meteo)
    │                       └── Driving routes (Google Maps or OSRM fallback)
    │
    └── Care Coordinator Agent  ← LangChain manual tool loop
            ├── get_prm_score()          retrieve PHQ-9 / GAD-7 / pain / EQ-5D
            └── flag_clinical_review()   raise urgent clinical flag
```

---

### Care Coordinator Tools (bound to LLM)
| Tool | Purpose |
|------|---------|
| `get_prm_score` | Retrieve PHQ-9 / GAD-7 / pain scale / EQ-5D scores for patient P-1042 |
| `flag_clinical_review` | Raise urgent clinical flag — clinician follow-up within 24 hours |

### Appointment Assistant Tools (UI pipeline)
| Tool | Purpose |
|------|---------|
| `get_weather_for_appointment` | Real-time weather via Open-Meteo API (no key required) + 35-day forecast grid |
| `get_traffic_route` | Driving routes via Google Maps Directions API (live traffic) or OSRM fallback |

### Sentiment Classes
| Label | Trigger | Care Response |
|-------|---------|---------------|
| 😊 Positive | Improvement reported | Encouragement + reinforce care plan |
| 😔 Negative | Distress / worsening | Validation + concrete next steps |
| 😐 Neutral | Vague / ambiguous | Direct assistance or focused follow-up questions |
| 🚨 Escalate | Safety concern / hopelessness | Immediate clinical escalation + crisis resource |

### Demo Patient — P-1042
| Measure | Score | Severity |
|---------|-------|----------|
| PHQ-9 | 14 | Moderate depression |
| GAD-7 | 11 | Moderate anxiety |
| Pain Scale | 7/10 | Severe |
| EQ-5D | 0.62 | Below population norm |

---
*Built with [LangChain](https://langchain.com) · [OpenAI gpt-4o-mini](https://openai.com) · [Open-Meteo](https://open-meteo.com) · [OpenStreetMap / Nominatim](https://nominatim.org) · [OSRM](https://project-osrm.org) · [Gradio](https://gradio.app)*
""")

    # ── Event wiring ──────────────────────────────────────────────────────────
    _outputs = [chatbot, msg_input, sentiment_panel,
                hospitals_panel, hospital_radio, city_state, hospitals_state,
                weather_panel, traffic_panel, map_panel]

    send_btn.click(fn=respond, inputs=[msg_input, chatbot], outputs=_outputs)
    msg_input.submit(fn=respond, inputs=[msg_input, chatbot], outputs=_outputs)
    clear_btn.click(fn=clear_conversation, outputs=_outputs)

    directions_btn.click(
        fn=get_directions,
        inputs=[hospital_radio, city_state, hospitals_state],
        outputs=[traffic_panel, map_panel],
    )

# ---------------------------------------------------------------------------
# 8. Launch
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _on_spaces = os.getenv("SPACE_ID") is not None
    demo.launch(
        server_name="0.0.0.0" if not _on_spaces else None,
        server_port=int(os.getenv("PORT", 7860)) if not _on_spaces else None,
        share=False,
        ssr_mode=False,
        theme=gr.themes.Soft(primary_hue="blue", neutral_hue="slate"),
        css=_CSS,
    )
