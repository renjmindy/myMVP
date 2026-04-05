-- users
CREATE TABLE IF NOT EXISTS public.users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  full_name TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- resume_templates
CREATE TABLE IF NOT EXISTS public.resume_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  content TEXT NOT NULL,
  is_default BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- agent_results (log every agent run)
CREATE TABLE IF NOT EXISTS public.agent_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_type TEXT NOT NULL,
  task_type TEXT NOT NULL,
  input_data JSONB NOT NULL,
  output_data JSONB NOT NULL,
  success BOOLEAN NOT NULL,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- cover_letters
CREATE TABLE IF NOT EXISTS public.cover_letters (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_title TEXT NOT NULL,
  company_name TEXT NOT NULL,
  content TEXT NOT NULL,
  tone TEXT,
  quality_score INT,
  personalization_score INT,
  word_count INT,
  agent_result_id UUID REFERENCES public.agent_results(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- optimized_resumes
CREATE TABLE IF NOT EXISTS public.optimized_resumes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_title TEXT NOT NULL,
  company_name TEXT NOT NULL,
  original_content TEXT NOT NULL,
  optimized_content TEXT NOT NULL,
  optimization_mode TEXT,
  match_score INT,
  quality_score INT,
  changes_made JSONB,
  agent_result_id UUID REFERENCES public.agent_results(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- company_research (cache web research results)
CREATE TABLE IF NOT EXISTS public.company_research (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_name TEXT NOT NULL,
  research_data JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_company_research_name ON public.company_research (lower(company_name));

-- job_searches (saved search history)
CREATE TABLE IF NOT EXISTS public.job_searches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  keywords TEXT[],
  location TEXT,
  sources TEXT[],
  results_count INT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- market_insights
CREATE TABLE IF NOT EXISTS public.market_insights (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  keywords TEXT[],
  location TEXT,
  insight_data JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- interview_prep
CREATE TABLE IF NOT EXISTS public.interview_prep (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id TEXT,
  job_title TEXT,
  company_name TEXT,
  questions JSONB,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- network_contacts (people in or near the user's network at target companies)
CREATE TABLE IF NOT EXISTS public.network_contacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company TEXT NOT NULL,
  name TEXT NOT NULL,
  title TEXT,
  degree TEXT CHECK (degree IN ('1st', '2nd', '3rd')),
  mutual TEXT,
  linkedin_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_network_contacts_company ON public.network_contacts (lower(company));
CREATE UNIQUE INDEX IF NOT EXISTS idx_network_contacts_company_name ON public.network_contacts (lower(company), lower(name));

-- disable RLS on all new tables
ALTER TABLE public.users DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.resume_templates DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_results DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.cover_letters DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.optimized_resumes DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_research DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.job_searches DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.market_insights DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.interview_prep DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.network_contacts DISABLE ROW LEVEL SECURITY;
