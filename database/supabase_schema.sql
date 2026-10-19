-- ==============================================================================
-- Nexus Learn Loop — Supabase PostgreSQL Schema & Row Level Security (RLS)
-- Run this in your Supabase Project's SQL Editor to provision tables and policies.
-- ==============================================================================

-- 1. Learner Profiles Table (Linked to Supabase Auth users)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    username TEXT NOT NULL UNIQUE,
    bio TEXT NOT NULL DEFAULT '',
    learning_goals TEXT NOT NULL DEFAULT 'Web & Python Full-Stack',
    skills TEXT NOT NULL DEFAULT 'Python, Flask, PostgreSQL',
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 2. Learning Activity (XP & Daily Heatmap Tracking)
CREATE TABLE IF NOT EXISTS public.learning_activity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    activity_type TEXT NOT NULL,
    xp_earned INTEGER NOT NULL DEFAULT 0,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 3. Study Sessions (Pomodoro & Focus Timer)
CREATE TABLE IF NOT EXISTS public.study_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes BETWEEN 1 AND 180),
    started_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    completed_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 4. Quiz Results
CREATE TABLE IF NOT EXISTS public.quiz_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    quiz_name TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    total_questions INTEGER NOT NULL DEFAULT 1,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- Indexes for Query Performance
CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON public.profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_user_completed ON public.learning_activity(user_id, completed_at DESC);
CREATE INDEX IF NOT EXISTS idx_study_user_completed ON public.study_sessions(user_id, completed_at DESC);
CREATE INDEX IF NOT EXISTS idx_quiz_user_completed ON public.quiz_results(user_id, completed_at DESC);

-- ==============================================================================
-- Row Level Security (RLS) Setup
-- Enforces data ownership so learners can only read/write their own records.
-- ==============================================================================

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.learning_activity ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.study_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quiz_results ENABLE ROW LEVEL SECURITY;

-- Profiles Policies
CREATE POLICY "Public profiles are readable by everyone"
    ON public.profiles FOR SELECT
    USING (true);

CREATE POLICY "Users can update their own profile"
    ON public.profiles FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can insert their own profile"
    ON public.profiles FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Learning Activity Policies
CREATE POLICY "Users can read their own activities"
    ON public.learning_activity FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own activities"
    ON public.learning_activity FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Study Sessions Policies
CREATE POLICY "Users can read their own study sessions"
    ON public.study_sessions FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own study sessions"
    ON public.study_sessions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Quiz Results Policies
CREATE POLICY "Users can read their own quiz results"
    ON public.quiz_results FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own quiz results"
    ON public.quiz_results FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Leaderboard View (aggregated community XP rankings)
CREATE OR REPLACE VIEW public.leaderboard AS
SELECT 
    p.user_id,
    p.username,
    p.learning_goals,
    p.is_demo,
    COALESCE(SUM(la.xp_earned), 0) AS xp
FROM public.profiles p
LEFT JOIN public.learning_activity la ON la.user_id = p.user_id
GROUP BY p.user_id, p.username, p.learning_goals, p.is_demo
ORDER BY xp DESC;
