#!/usr/bin/env bash
set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BOLD}Interview Agent — startup${NC}"
echo "----------------------------"

# 1. Check .env
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo -e "${YELLOW}[warn]${NC} .env not found. Copying from .env.example (mock mode will be active)."
        cp .env.example .env
    else
        echo -e "${YELLOW}[warn]${NC} No .env file found. Running in mock mode."
    fi
else
    echo -e "${GREEN}[ok]${NC}   .env found."
fi

# 2. Check Python
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}[error]${NC} python3 not found. Install Python 3.10+."
    exit 1
fi
echo -e "${GREEN}[ok]${NC}   Python: $(python3 --version)"

# 3. Install/check dependencies
echo -e "${YELLOW}[...]${NC}  Checking dependencies..."
pip install -q -r requirements.txt
echo -e "${GREEN}[ok]${NC}   Dependencies installed."

# 4. Check Playwright browsers
if ! python3 -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); p.stop()" &>/dev/null; then
    echo -e "${YELLOW}[...]${NC}  Installing Playwright browsers..."
    playwright install chromium
    echo -e "${GREEN}[ok]${NC}   Playwright browsers installed."
else
    echo -e "${GREEN}[ok]${NC}   Playwright browsers ready."
fi

# 5. Health check — import core modules
echo -e "${YELLOW}[...]${NC}  Running health checks..."
python3 - <<'EOF'
import sys
errors = []

def check(label, fn):
    try:
        fn()
        print(f"\033[0;32m[ok]\033[0m   {label}")
    except Exception as e:
        print(f"\033[0;31m[fail]\033[0m {label}: {e}")
        errors.append(label)

check("streamlit",         lambda: __import__("streamlit"))
check("supabase",          lambda: __import__("supabase"))
check("openai",            lambda: __import__("openai"))
check("playwright",        lambda: __import__("playwright"))
check("database module",   lambda: __import__("src.database.supabase_client", fromlist=["get_client"]))
check("ai_agent module",   lambda: __import__("src.agents.ai_agent", fromlist=["JobAnalysisAgent"]))
check("job_scraper module",lambda: __import__("src.agents.job_scraper", fromlist=["JobScraper"]))
check("email module",      lambda: __import__("src.utils.email_notifier", fromlist=["EmailNotifier"]))

if errors:
    print(f"\n\033[0;31m{len(errors)} check(s) failed: {', '.join(errors)}\033[0m")
    sys.exit(1)
else:
    print("\n\033[1mAll checks passed.\033[0m")
EOF

echo ""
echo -e "${GREEN}${BOLD}Starting Interview Agent...${NC}"
echo -e "Open ${BOLD}http://localhost:8501${NC} in your browser."
echo ""

streamlit run streamlit_app.py
