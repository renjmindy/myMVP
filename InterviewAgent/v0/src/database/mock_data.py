from datetime import datetime, timezone, timedelta

_NOW = datetime.now(timezone.utc)


def _days_ago(n: int) -> str:
    return (_NOW - timedelta(days=n)).isoformat()


MOCK_JOBS: list[dict] = [
    {
        "id": "mock-001",
        "title": "Senior Software Engineer",
        "company": "Acme Corp",
        "location": "San Francisco, CA",
        "url": "https://example.com/jobs/001",
        "description": (
            "We are looking for a Senior Software Engineer with 5+ years of experience "
            "in Python and distributed systems. You will design and build scalable backend "
            "services, mentor junior engineers, and collaborate with product teams.\n\n"
            "Requirements:\n- Python (5+ years)\n- PostgreSQL or similar\n"
            "- Experience with cloud platforms (AWS/GCP)\n- Strong communication skills"
        ),
        "source": "linkedin",
        "posted_date": _days_ago(1),
        "scraped_at": _days_ago(0),
        "status": "new",
        "fit_score": 88,
        "analysis": {
            "fit_score": 88,
            "recommendation": "apply",
            "summary": "Strong match — your Python and backend experience align well with the role. Cloud experience is a plus.",
            "matching_skills": ["Python", "PostgreSQL", "Backend development"],
            "missing_skills": ["AWS certification"],
            "key_requirements": ["5+ years Python", "Distributed systems", "Cloud platforms"],
        },
        "notes": "",
        "interview_date": None,
    },
    {
        "id": "mock-002",
        "title": "Full Stack Developer",
        "company": "StartupXYZ",
        "location": "Remote",
        "url": "https://example.com/jobs/002",
        "description": (
            "Join our fast-growing startup as a Full Stack Developer. "
            "You'll work across the stack using React, Node.js, and Python. "
            "We value autonomy, fast iteration, and clean code.\n\n"
            "Requirements:\n- React and TypeScript\n- Python or Node.js backend\n"
            "- Familiarity with CI/CD\n- Startup experience preferred"
        ),
        "source": "indeed",
        "posted_date": _days_ago(2),
        "scraped_at": _days_ago(0),
        "status": "saved",
        "fit_score": 72,
        "analysis": {
            "fit_score": 72,
            "recommendation": "apply",
            "summary": "Good fit for backend requirements. Frontend React/TypeScript is a gap but the role is flexible.",
            "matching_skills": ["Python", "Node.js", "CI/CD"],
            "missing_skills": ["React", "TypeScript"],
            "key_requirements": ["React", "TypeScript", "Python or Node.js"],
        },
        "notes": "Interesting product — worth a conversation.",
        "interview_date": None,
    },
    {
        "id": "mock-003",
        "title": "Machine Learning Engineer",
        "company": "DataCo",
        "location": "New York, NY",
        "url": "https://example.com/jobs/003",
        "description": (
            "DataCo is hiring an ML Engineer to build and deploy production ML pipelines. "
            "You will work with large datasets, fine-tune models, and collaborate with data scientists.\n\n"
            "Requirements:\n- Python, PyTorch or TensorFlow\n- MLOps experience\n"
            "- Experience with model serving (TorchServe, Triton, etc.)\n- PhD preferred"
        ),
        "source": "linkedin",
        "posted_date": _days_ago(3),
        "scraped_at": _days_ago(1),
        "status": "applied",
        "fit_score": 61,
        "analysis": {
            "fit_score": 61,
            "recommendation": "maybe",
            "summary": "Partial fit — Python is a match but MLOps and model serving experience are required and not evident from resume.",
            "matching_skills": ["Python", "Data pipelines"],
            "missing_skills": ["PyTorch", "MLOps", "Model serving"],
            "key_requirements": ["PyTorch or TensorFlow", "MLOps", "PhD preferred"],
        },
        "notes": "Applied via LinkedIn. Waiting for response.",
        "interview_date": (_NOW + timedelta(days=3)).date().isoformat(),
    },
    {
        "id": "mock-004",
        "title": "DevOps Engineer",
        "company": "CloudBase",
        "location": "Austin, TX",
        "url": "https://example.com/jobs/004",
        "description": (
            "Looking for a DevOps Engineer to manage our Kubernetes clusters, "
            "CI/CD pipelines, and infrastructure as code. "
            "Must have strong Terraform and Helm experience.\n\n"
            "Requirements:\n- Kubernetes (3+ years)\n- Terraform\n- Helm\n"
            "- AWS or Azure\n- On-call rotation required"
        ),
        "source": "indeed",
        "posted_date": _days_ago(5),
        "scraped_at": _days_ago(2),
        "status": "rejected",
        "fit_score": 34,
        "analysis": {
            "fit_score": 34,
            "recommendation": "skip",
            "summary": "Low fit — the role is heavily infrastructure-focused. Minimal overlap with current experience.",
            "matching_skills": ["AWS basics"],
            "missing_skills": ["Kubernetes", "Terraform", "Helm", "On-call ops"],
            "key_requirements": ["Kubernetes 3+ years", "Terraform", "Helm"],
        },
        "notes": "",
        "interview_date": None,
    },
    {
        "id": "mock-005",
        "title": "Backend Engineer (Python)",
        "company": "FinTechPro",
        "location": "Remote",
        "url": "https://example.com/jobs/005",
        "description": (
            "FinTechPro is seeking a Backend Engineer to build high-performance APIs "
            "and data processing systems for our financial platform. "
            "We use Python, FastAPI, and PostgreSQL.\n\n"
            "Requirements:\n- Python (FastAPI or Django)\n- PostgreSQL\n"
            "- REST API design\n- Financial domain knowledge a plus"
        ),
        "source": "linkedin",
        "posted_date": _days_ago(1),
        "scraped_at": _days_ago(0),
        "status": "new",
        "fit_score": 91,
        "analysis": {
            "fit_score": 91,
            "recommendation": "apply",
            "summary": "Excellent match. Python, FastAPI, and PostgreSQL are direct skill matches. Highly recommended.",
            "matching_skills": ["Python", "FastAPI", "PostgreSQL", "REST API design"],
            "missing_skills": ["Financial domain knowledge"],
            "key_requirements": ["Python (FastAPI or Django)", "PostgreSQL", "REST API design"],
        },
        "notes": "",
        "interview_date": None,
    },
    {
        "id": "mock-006",
        "title": "Software Engineer II",
        "company": "MegaCorp",
        "location": "Seattle, WA",
        "url": "https://example.com/jobs/006",
        "description": (
            "Join MegaCorp's platform team. You will build internal tooling and "
            "APIs used by hundreds of engineers. Java and Go experience required.\n\n"
            "Requirements:\n- Java (Spring Boot)\n- Go\n- Microservices architecture\n"
            "- 3+ years experience"
        ),
        "source": "indeed",
        "posted_date": _days_ago(4),
        "scraped_at": _days_ago(1),
        "status": "new",
        "fit_score": 45,
        "analysis": {
            "fit_score": 45,
            "recommendation": "maybe",
            "summary": "Below-average fit — Java and Go are the primary languages and are not in the resume. Architecture experience may partially transfer.",
            "matching_skills": ["Microservices concepts", "API design"],
            "missing_skills": ["Java", "Go", "Spring Boot"],
            "key_requirements": ["Java (Spring Boot)", "Go", "Microservices"],
        },
        "notes": "",
        "interview_date": None,
    },
]

# Network contacts keyed by company name (3 per company).
# degree: "1st" = direct connection, "2nd" = friend of a connection, "3rd" = extended network
MOCK_NETWORK_CONTACTS: dict[str, list[dict]] = {
    "Acme Corp": [
        {
            "name": "Sarah Chen",
            "title": "Engineering Manager",
            "degree": "1st",
            "mutual": None,
            "linkedin_url": "https://linkedin.com/in/sarah-chen-acme",
        },
        {
            "name": "James Patel",
            "title": "Senior Software Engineer",
            "degree": "2nd",
            "mutual": "David Kim",
            "linkedin_url": "https://linkedin.com/in/james-patel-acme",
        },
        {
            "name": "Maria Torres",
            "title": "Staff Engineer",
            "degree": "2nd",
            "mutual": "Alice Zhang",
            "linkedin_url": "https://linkedin.com/in/maria-torres-acme",
        },
    ],
    "StartupXYZ": [
        {
            "name": "Leo Nguyen",
            "title": "Co-Founder & CTO",
            "degree": "2nd",
            "mutual": "Rachel Park",
            "linkedin_url": "https://linkedin.com/in/leo-nguyen-xyz",
        },
        {
            "name": "Priya Sharma",
            "title": "Full Stack Engineer",
            "degree": "1st",
            "mutual": None,
            "linkedin_url": "https://linkedin.com/in/priya-sharma-xyz",
        },
        {
            "name": "Tom Walsh",
            "title": "Head of Product",
            "degree": "3rd",
            "mutual": None,
            "linkedin_url": "https://linkedin.com/in/tom-walsh-xyz",
        },
    ],
    "DataCo": [
        {
            "name": "Aisha Okonkwo",
            "title": "Principal ML Engineer",
            "degree": "2nd",
            "mutual": "Kevin Liu",
            "linkedin_url": "https://linkedin.com/in/aisha-okonkwo-dataco",
        },
        {
            "name": "Raj Mehta",
            "title": "Data Scientist",
            "degree": "2nd",
            "mutual": "Kevin Liu",
            "linkedin_url": "https://linkedin.com/in/raj-mehta-dataco",
        },
        {
            "name": "Chloe Dubois",
            "title": "ML Infrastructure Engineer",
            "degree": "3rd",
            "mutual": None,
            "linkedin_url": "https://linkedin.com/in/chloe-dubois-dataco",
        },
    ],
    "CloudBase": [
        {
            "name": "Marcus Reed",
            "title": "DevOps Tech Lead",
            "degree": "3rd",
            "mutual": None,
            "linkedin_url": "https://linkedin.com/in/marcus-reed-cloudbase",
        },
        {
            "name": "Yuki Tanaka",
            "title": "Site Reliability Engineer",
            "degree": "2nd",
            "mutual": "Chris Moore",
            "linkedin_url": "https://linkedin.com/in/yuki-tanaka-cloudbase",
        },
        {
            "name": "Nina Kowalski",
            "title": "Cloud Architect",
            "degree": "3rd",
            "mutual": None,
            "linkedin_url": "https://linkedin.com/in/nina-kowalski-cloudbase",
        },
    ],
    "FinTechPro": [
        {
            "name": "Daniel Osei",
            "title": "Backend Engineer",
            "degree": "1st",
            "mutual": None,
            "linkedin_url": "https://linkedin.com/in/daniel-osei-fintechpro",
        },
        {
            "name": "Fatima Al-Hassan",
            "title": "Engineering Manager",
            "degree": "2nd",
            "mutual": "Sarah Chen",
            "linkedin_url": "https://linkedin.com/in/fatima-alhassan-fintechpro",
        },
        {
            "name": "Ben Carter",
            "title": "Senior Python Developer",
            "degree": "2nd",
            "mutual": "David Kim",
            "linkedin_url": "https://linkedin.com/in/ben-carter-fintechpro",
        },
    ],
    "MegaCorp": [
        {
            "name": "Lisa Zhang",
            "title": "Software Engineer II",
            "degree": "2nd",
            "mutual": "Alice Zhang",
            "linkedin_url": "https://linkedin.com/in/lisa-zhang-megacorp",
        },
        {
            "name": "Omar Hassan",
            "title": "Senior Go Engineer",
            "degree": "3rd",
            "mutual": None,
            "linkedin_url": "https://linkedin.com/in/omar-hassan-megacorp",
        },
        {
            "name": "Grace Kim",
            "title": "Platform Tech Lead",
            "degree": "2nd",
            "mutual": "Rachel Park",
            "linkedin_url": "https://linkedin.com/in/grace-kim-megacorp",
        },
    ],
}

MOCK_SETTINGS: dict = {
    "id": 1,
    "keywords": ["software engineer", "python developer"],
    "location": "Remote",
    "resume_text": "",
    "email": "",
    "notify_threshold": 70,
    "notify_frequency": "daily",
    "excluded_companies": [],
}
