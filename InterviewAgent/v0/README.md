# Interview Agent

An AI-powered job search assistant built with Streamlit and Supabase. It scrapes LinkedIn job postings, scores them against your resume, generates cover letters and optimized resumes, researches companies and market trends, and emails you a digest of the best matches — all from a single web UI.

---

## Features

- **LinkedIn Job Scraper** — scrapes jobs via a local LinkedIn MCP server; filters by age, applicant count, and company
- **AI Job Analysis** — scores each job against your resume using GPT-4o-mini; highlights matching and missing skills
- **Cover Letter Generator** — creates tailored cover letters with tone control
- **Resume Optimizer** — rewrites your resume to match a specific job description
- **Market Intel** — analyzes demand, competition, salary ranges, and trending skills for any keyword/location
- **Company Research** — overview, culture, tech stack, recent news, and interview tips per company
- **Network Contacts** — finds verified LinkedIn contacts at target companies and generates referral emails
- **Upwork Proposal Generator** — generates structured Upwork proposals using Gemini with your saved examples
- **Upwork Video Script Generator** — generates timestamped video pitch scripts using Gemini
- **Email Digest** — sends a scored job digest to your Gmail on a configurable schedule
- **Scheduled Runs** — cron-based weekly scrape + digest (first Friday 3am PT) and cleanup (fourth Friday 3am PT)

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit |
| Database | Supabase (PostgreSQL) |
| Job Scraping | LinkedIn MCP server (`linkedin-scraper-mcp`) |
| AI Analysis | OpenAI GPT-4o-mini |
| Proposal / Video | Google Gemini (`gemini-3-flash-preview`) |
| Email | Gmail SMTP |
| Scheduling | cron |

---

## Prerequisites

- Python 3.11+
- A [Supabase](https://supabase.com) account (free tier is sufficient)
- An [OpenAI](https://platform.openai.com) API key
- A [Google AI Studio](https://aistudio.google.com) API key (for Gemini)
- A Gmail account with an [App Password](https://myaccount.google.com/apppasswords) enabled
- Windows machine running the LinkedIn MCP server (see below), or a Linux/Mac equivalent

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/InterviewAgent.git
cd InterviewAgent/v0
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
SMTP_EMAIL=your_gmail@gmail.com
SMTP_PASSWORD=your_gmail_app_password
```

> **Never commit `.env` to git.** It is already listed in `.gitignore`.

### 4. Set up Supabase

1. Create a new project at [supabase.com](https://supabase.com)
2. Open the **SQL Editor** in your project dashboard
3. Run the schema file to create all tables:

```sql
-- paste the contents of docs/schema.sql and execute
```

4. Also run these additional columns added after the initial schema:

```sql
ALTER TABLE public.jobs
  ADD COLUMN IF NOT EXISTS fit_score INT,
  ADD COLUMN IF NOT EXISTS analysis JSONB,
  ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'new';

ALTER TABLE public.settings
  ADD COLUMN IF NOT EXISTS name TEXT,
  ADD COLUMN IF NOT EXISTS phone TEXT,
  ADD COLUMN IF NOT EXISTS work_authorization TEXT,
  ADD COLUMN IF NOT EXISTS years_of_experience TEXT,
  ADD COLUMN IF NOT EXISTS target_companies TEXT[],
  ADD COLUMN IF NOT EXISTS excluded_companies TEXT[],
  ADD COLUMN IF NOT EXISTS upwork_proposal_examples TEXT[],
  ADD COLUMN IF NOT EXISTS upwork_video_examples TEXT[];
```

### 5. Start the LinkedIn MCP server (Windows)

The job scraper requires the `linkedin-scraper-mcp` server running locally. On Windows PowerShell:

```powershell
uvx linkedin-scraper-mcp --transport streamable-http --host 0.0.0.0 --port 8765
```

> If you are running on WSL, the app connects to the Windows host automatically via the WSL gateway IP. No extra configuration needed.

> **Note:** You must be logged in to LinkedIn in your default browser for the MCP server to scrape successfully.

### 6. Run the app

```bash
streamlit run streamlit_app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## First-Time Configuration

1. Go to **Settings** and fill in:
   - Search keywords (e.g. `AI engineer, machine learning engineer`)
   - Location (e.g. `Remote` or `San Francisco, CA`)
   - Your resume text (paste full resume)
   - Your name, phone, work authorization, years of experience
   - Notification email and fit score threshold
   - Companies to target or exclude (optional)

2. Go to **Dashboard** and click **Scrape Jobs** to run your first scrape.

3. Click **Analyze Jobs (AI)** to score all scraped jobs against your resume.

4. Browse results on the **Jobs** page.

---

## Scheduled Automation (optional)

To run scrape + digest automatically, add these lines to your crontab (`crontab -e`):

```
TZ=America/Los_Angeles
# Scrape + digest: first Friday of every month at 3am PT
0 3 1-7 * 5 cd /path/to/InterviewAgent/v0 && /path/to/python scheduler.py

# Cleanup applied job files: fourth Friday of every month at 3am PT
0 3 22-28 * 5 cd /path/to/InterviewAgent/v0 && /path/to/python cleanup.py
```

---

## Project Structure

```
v0/
├── streamlit_app.py          # App entry point and navigation
├── scheduler.py              # Cron job: scrape + score + email digest
├── cleanup.py                # Cron job: delete files for applied jobs
├── requirements.txt
├── .env.example              # Template for environment variables
├── docs/
│   └── schema.sql            # Supabase table definitions
├── src/
│   ├── agents/
│   │   ├── job_scraper.py        # LinkedIn scraper via MCP
│   │   ├── ai_agent.py           # GPT-4o-mini job analysis
│   │   ├── cover_letter_agent.py # Cover letter generation
│   │   ├── resume_optimizer.py   # Resume optimization
│   │   ├── job_discovery_agent.py # Market intel + company research
│   │   └── network_contacts_agent.py # LinkedIn contact finder
│   ├── database/
│   │   └── supabase_client.py    # All Supabase read/write operations
│   ├── pages/
│   │   ├── dashboard.py          # Metrics, manual controls
│   │   ├── jobs.py               # Job list, cover letters, contacts
│   │   ├── resume.py             # Resume optimizer UI
│   │   ├── cover_letters.py      # Cover letter history
│   │   ├── market.py             # Market intel + company research
│   │   ├── settings.py           # User preferences
│   │   ├── upwork_proposal.py    # Upwork proposal generator
│   │   └── upwork_video.py       # Upwork video script generator
│   └── utils/
│       └── email_notifier.py     # Gmail SMTP digest sender
└── tests/
```

---

## License

MIT
