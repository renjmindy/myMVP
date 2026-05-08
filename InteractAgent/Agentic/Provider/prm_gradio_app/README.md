# PRM Care Coordinator

An AI-powered care coordinator that follows up with patients on their **Patient Reported Measures (PRMs)** — PHQ-9, GAD-7, Pain Scale, and EQ-5D. Built with LangChain, OpenAI, and Gradio.

---

## Features

- **Sentiment-driven responses** — every message is classified (positive / negative / neutral / escalate) and routed to a tone-matched response template via `RunnableBranch`
- **PRM score lookup** — the coordinator retrieves PHQ-9, GAD-7, pain scale, and EQ-5D scores and explains them in plain language
- **Clinical escalation** — severe scores or safety concerns automatically raise a flagged clinical review ticket
- **Appointment Assistant** — detects location intent in the conversation and surfaces:
  - Top 5 nearby hospitals (OpenStreetMap / Nominatim)
  - Real-time weather + 35-day forecast grid (Open-Meteo)
  - Driving directions (Google Maps live traffic, or OSRM free fallback)
- **Quick-starter prompts** — grouped sample messages to explore all conversation flows

---

## Architecture

```
User message
    │
    ▼
Sentiment Detector  ← classification_template | LLM | StrOutputParser()
    │
    └── RunnableBranch ──► positive  → warm acknowledgment
                       ──► negative  → empathetic support + next steps
                       ──► neutral   → direct assistance or follow-up questions
                       ──► escalate  → immediate clinical escalation 🚨
    │
    ▼
Intent Detector  ← LLM JSON classifier (trigger + city extraction)
    │
    ├── trigger=true ──► Appointment Assistant Pipeline
    │                       ├── Nominatim geocoding (state-aware, typo-correcting)
    │                       ├── Nearby hospital search (OpenStreetMap, top 5)
    │                       ├── 35-day weather forecast (Open-Meteo)
    │                       └── Driving routes (Google Maps API or OSRM fallback)
    │
    └── Care Coordinator Agent  ← LangChain manual tool loop (max 5 iterations)
            ├── get_prm_score()          retrieve PHQ-9 / GAD-7 / pain / EQ-5D
            └── flag_clinical_review()   raise urgent clinical flag
```

---

## Setup

### Prerequisites

- Python 3.10+
- An [OpenAI API key](https://platform.openai.com/api-keys)
- *(Optional)* [Google Maps API key](https://console.cloud.google.com/) with the **Directions API** and **Maps Embed API** enabled — falls back to OSRM open routing without it

### Install

```bash
pip install -r requirements.txt
```

### Configure

Copy the example and fill in your keys:

```bash
cp .env.example .env   # or create .env manually
```

`.env`:
```
OPENAI_API_KEY=your-openai-api-key-here
GOOGLE_MAPS_API_KEY=your-google-maps-api-key-here   # optional
```

> **Never commit `.env` to git.** It is excluded by the root `.gitignore`.

### Run

```bash
python app.py
```

The app starts at `http://localhost:7860`.

---

## Tools

### Care Coordinator (LLM-bound)

| Tool | Description |
|------|-------------|
| `get_prm_score` | Returns the latest PHQ-9 / GAD-7 / pain scale / EQ-5D score with severity label and recommended action for patient P-1042 |
| `flag_clinical_review` | Creates a clinical review ticket and schedules a clinician follow-up within 24 hours |

### Appointment Assistant (UI pipeline)

| Tool | Description |
|------|-------------|
| `get_weather_for_appointment` | Real-time weather via Open-Meteo (free, no key required) |
| `get_traffic_route` | Driving routes via Google Maps Directions API (live traffic) with OSRM as a free fallback |

---

## Demo Patient — P-1042

| Measure | Score | Severity |
|---------|-------|----------|
| PHQ-9 | 14 | Moderate depression |
| GAD-7 | 11 | Moderate anxiety |
| Pain Scale | 7/10 | Severe |
| EQ-5D | 0.62 | Below population norm |

---

## Deployment on HuggingFace Spaces

1. Create a new **Gradio** Space.
2. Upload all files **except** `.env`.
3. Add your keys as **Space Secrets** (`OPENAI_API_KEY`, `GOOGLE_MAPS_API_KEY`).
4. The app reads secrets automatically via `os.getenv()` — no code changes needed.

---

## Tech Stack

| Library | Use |
|---------|-----|
| [LangChain](https://langchain.com) | `RunnableBranch`, `ChatPromptTemplate`, tool loop |
| [langchain-openai](https://github.com/langchain-ai/langchain) | `ChatOpenAI` (`gpt-4o-mini`) |
| [Gradio](https://gradio.app) | UI, chat interface, tabbed layout |
| [Open-Meteo](https://open-meteo.com) | Free weather forecast API |
| [Nominatim / OpenStreetMap](https://nominatim.org) | Free geocoding and hospital search |
| [OSRM](https://project-osrm.org) | Free open-source routing fallback |
| [Google Maps APIs](https://developers.google.com/maps) | Live traffic directions + map embed (optional) |
