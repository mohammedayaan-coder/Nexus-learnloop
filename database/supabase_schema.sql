-- ==============================================================================
-- Nexus Learn Loop — Supabase PostgreSQL Schema, Grants & RLS Policies
-- Execute in Supabase SQL Editor: https://supabase.com/dashboard/project/_/sql
-- ==============================================================================

-- 1. LEARNER PROFILES
CREATE TABLE IF NOT EXISTS public.learner_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    bio TEXT DEFAULT '',
    username TEXT,
    learning_goals TEXT[] NOT NULL DEFAULT '{}',
    skills TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Keep public profile rows in sync with Supabase Auth, including when email
-- confirmation is enabled and signup has no access token yet.
ALTER TABLE public.learner_profiles ADD COLUMN IF NOT EXISTS username TEXT;

-- Older deployments used scalar TEXT values for these profile fields.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'learner_profiles'
          AND column_name = 'learning_goals' AND data_type = 'text'
    ) THEN
        ALTER TABLE public.learner_profiles ALTER COLUMN learning_goals DROP DEFAULT;
        ALTER TABLE public.learner_profiles ALTER COLUMN learning_goals TYPE TEXT[]
            USING CASE WHEN NULLIF(BTRIM(learning_goals), '') IS NULL THEN ARRAY[]::TEXT[]
                       ELSE string_to_array(learning_goals, ',') END;
        ALTER TABLE public.learner_profiles ALTER COLUMN learning_goals SET DEFAULT '{}';
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'learner_profiles'
          AND column_name = 'skills' AND data_type = 'text'
    ) THEN
        ALTER TABLE public.learner_profiles ALTER COLUMN skills DROP DEFAULT;
        ALTER TABLE public.learner_profiles ALTER COLUMN skills TYPE TEXT[]
            USING CASE WHEN NULLIF(BTRIM(skills), '') IS NULL THEN ARRAY[]::TEXT[]
                       ELSE string_to_array(skills, ',') END;
        ALTER TABLE public.learner_profiles ALTER COLUMN skills SET DEFAULT '{}';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION public.create_learner_profile_for_auth_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    INSERT INTO public.learner_profiles (user_id, username, bio, learning_goals)
    VALUES (
        NEW.id,
        COALESCE(NULLIF(NEW.raw_user_meta_data->>'username', ''), split_part(NEW.email, '@', 1)),
        'Passionate learner building daily habits.',
        ARRAY[COALESCE(NULLIF(NEW.raw_user_meta_data->>'learning_goals', ''), 'Web & Python Full-Stack')]
    )
    ON CONFLICT (user_id) DO UPDATE
    SET username = EXCLUDED.username;

    INSERT INTO public.learning_activities (user_id, activity_type, xp_earned)
    VALUES (NEW.id, 'signup', 50);
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.create_learner_profile_for_auth_user() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS create_learner_profile_after_signup ON auth.users;
CREATE TRIGGER create_learner_profile_after_signup
AFTER INSERT ON auth.users
FOR EACH ROW EXECUTE FUNCTION public.create_learner_profile_for_auth_user();

-- Backfill names for profiles created before this trigger was installed.
INSERT INTO public.learner_profiles (user_id, username, learning_goals)
SELECT
    au.id,
    COALESCE(NULLIF(au.raw_user_meta_data->>'username', ''), split_part(au.email, '@', 1)),
    ARRAY[COALESCE(NULLIF(au.raw_user_meta_data->>'learning_goals', ''), 'Web & Python Full-Stack')]
FROM auth.users au
ON CONFLICT (user_id) DO NOTHING;

UPDATE public.learner_profiles lp
SET username = COALESCE(NULLIF(au.raw_user_meta_data->>'username', ''), split_part(au.email, '@', 1))
FROM auth.users au
WHERE au.id = lp.user_id AND lp.username IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS learner_profiles_username_idx
ON public.learner_profiles (lower(username)) WHERE username IS NOT NULL;

-- Username-to-email lookup is needed for username login. Keep the email
-- lookup callable only by the server's service-role client.
CREATE OR REPLACE FUNCTION public.lookup_auth_email_by_username(requested_username TEXT)
RETURNS TEXT
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT au.email::TEXT
    FROM public.learner_profiles lp
    JOIN auth.users au ON au.id = lp.user_id
    WHERE lower(lp.username) = lower(requested_username)
    LIMIT 1
$$;
REVOKE ALL ON FUNCTION public.lookup_auth_email_by_username(TEXT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.lookup_auth_email_by_username(TEXT) TO service_role;

-- 2. LEARNING ACTIVITIES
-- If learning_activity existed previously from older schema, rename or sync
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'learning_activity')
       AND NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'learning_activities') THEN
        ALTER TABLE public.learning_activity RENAME TO learning_activities;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.learning_activities (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    activity_type TEXT NOT NULL,
    xp_earned INTEGER NOT NULL DEFAULT 0 CHECK (xp_earned >= 0),
    completed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- If both names existed from an earlier partial migration, copy the old rows
-- once when the new table is still empty.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'learning_activity')
       AND EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'learning_activities')
       AND NOT EXISTS (SELECT 1 FROM public.learning_activities) THEN
        INSERT INTO public.learning_activities (user_id, activity_type, xp_earned, completed_at)
        SELECT user_id, activity_type, xp_earned, completed_at FROM public.learning_activity;
    END IF;
END;
$$;

-- 3. STUDY SESSIONS
CREATE TABLE IF NOT EXISTS public.study_sessions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- 4. QUIZ RESULTS
CREATE TABLE IF NOT EXISTS public.quiz_results (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    quiz_name TEXT NOT NULL,
    score INTEGER NOT NULL CHECK (score >= 0),
    total_questions INTEGER NOT NULL CHECK (total_questions > 0),
    completed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (score <= total_questions)
);

-- 5. INDEXES FOR PERFORMANCE
CREATE INDEX IF NOT EXISTS learning_activities_user_id_idx ON public.learning_activities(user_id);
CREATE INDEX IF NOT EXISTS study_sessions_user_id_idx ON public.study_sessions(user_id);
CREATE INDEX IF NOT EXISTS quiz_results_user_id_idx ON public.quiz_results(user_id);

-- Keep result/session persistence and the corresponding XP event atomic.
DROP FUNCTION IF EXISTS public.record_study_session_with_xp(UUID, INTEGER, INTEGER);
CREATE OR REPLACE FUNCTION public.record_study_session_with_xp(
    p_user_id UUID, p_duration_minutes INTEGER, p_xp_earned INTEGER
)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE inserted_id TEXT;
BEGIN
    INSERT INTO public.study_sessions (user_id, duration_minutes)
    VALUES (p_user_id, p_duration_minutes)
    RETURNING id::TEXT INTO inserted_id;

    INSERT INTO public.learning_activities (user_id, activity_type, xp_earned)
    VALUES (p_user_id, 'study_session', p_xp_earned);
    RETURN inserted_id;
END;
$$;
REVOKE ALL ON FUNCTION public.record_study_session_with_xp(UUID, INTEGER, INTEGER) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.record_study_session_with_xp(UUID, INTEGER, INTEGER) TO service_role;

DROP FUNCTION IF EXISTS public.record_quiz_result_with_xp(UUID, TEXT, INTEGER, INTEGER, INTEGER);
CREATE OR REPLACE FUNCTION public.record_quiz_result_with_xp(
    p_user_id UUID, p_quiz_name TEXT, p_score INTEGER,
    p_total_questions INTEGER, p_xp_earned INTEGER
)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE inserted_id TEXT;
BEGIN
    INSERT INTO public.quiz_results (user_id, quiz_name, score, total_questions)
    VALUES (p_user_id, p_quiz_name, p_score, p_total_questions)
    RETURNING id::TEXT INTO inserted_id;

    INSERT INTO public.learning_activities (user_id, activity_type, xp_earned)
    VALUES (p_user_id, 'quiz', p_xp_earned);
    RETURN inserted_id;
END;
$$;
REVOKE ALL ON FUNCTION public.record_quiz_result_with_xp(UUID, TEXT, INTEGER, INTEGER, INTEGER) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.record_quiz_result_with_xp(UUID, TEXT, INTEGER, INTEGER, INTEGER) TO service_role;

-- 6. GRANT TABLE PRIVILEGES TO ROLES (Mandatory for RLS policies to evaluate)
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
GRANT SELECT, UPDATE ON public.learner_profiles TO authenticated;
GRANT SELECT ON public.learning_activities, public.study_sessions, public.quiz_results TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;

-- 7. ENABLE ROW LEVEL SECURITY
ALTER TABLE public.learner_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.learning_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.study_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quiz_results ENABLE ROW LEVEL SECURITY;

-- 8. PROFILE POLICIES
DROP POLICY IF EXISTS "Users can view own profile" ON public.learner_profiles;
CREATE POLICY "Users can view own profile"
ON public.learner_profiles FOR SELECT TO authenticated
USING ((SELECT auth.uid()) = user_id);

DROP POLICY IF EXISTS "Public can view profiles for leaderboard" ON public.learner_profiles;

DROP POLICY IF EXISTS "Users can create own profile" ON public.learner_profiles;
-- Profile creation is handled by the auth.users trigger above.

DROP POLICY IF EXISTS "Users can update own profile" ON public.learner_profiles;
CREATE POLICY "Users can update own profile"
ON public.learner_profiles FOR UPDATE TO authenticated
USING ((SELECT auth.uid()) = user_id)
WITH CHECK ((SELECT auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can delete own profile" ON public.learner_profiles;
CREATE POLICY "Users can delete own profile"
ON public.learner_profiles FOR DELETE TO authenticated
USING ((SELECT auth.uid()) = user_id);

-- 9. ACTIVITY POLICIES
DROP POLICY IF EXISTS "Users can view own activities" ON public.learning_activities;
CREATE POLICY "Users can view own activities"
ON public.learning_activities FOR SELECT TO authenticated
USING ((SELECT auth.uid()) = user_id);

DROP POLICY IF EXISTS "Public can aggregate activities for leaderboard" ON public.learning_activities;

DROP POLICY IF EXISTS "Users can create own activities" ON public.learning_activities;

DROP POLICY IF EXISTS "Users can update own activities" ON public.learning_activities;

-- 10. STUDY SESSION POLICIES
DROP POLICY IF EXISTS "Users can view own sessions" ON public.study_sessions;
CREATE POLICY "Users can view own sessions"
ON public.study_sessions FOR SELECT TO authenticated
USING ((SELECT auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can create own sessions" ON public.study_sessions;

DROP POLICY IF EXISTS "Users can update own sessions" ON public.study_sessions;

-- 11. QUIZ RESULT POLICIES
DROP POLICY IF EXISTS "Users can view own quiz results" ON public.quiz_results;
CREATE POLICY "Users can view own quiz results"
ON public.quiz_results FOR SELECT TO authenticated
USING ((SELECT auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can create own quiz results" ON public.quiz_results;

DROP POLICY IF EXISTS "Users can update own quiz results" ON public.quiz_results;

-- 12. LEADERBOARD VIEW
DROP VIEW IF EXISTS public.leaderboard;
CREATE VIEW public.leaderboard
WITH (security_invoker = false, security_barrier = true) AS
SELECT
    lp.user_id AS id,
    COALESCE(lp.username, au.raw_user_meta_data->>'username', split_part(au.email, '@', 1), 'Learner') AS username,
    FALSE AS is_demo,
    COALESCE(SUM(la.xp_earned), 0)::bigint AS xp
FROM public.learner_profiles lp
LEFT JOIN auth.users au ON au.id = lp.user_id
LEFT JOIN public.learning_activities la ON la.user_id = lp.user_id
GROUP BY lp.user_id, lp.username, au.raw_user_meta_data, au.email;

GRANT SELECT ON public.leaderboard TO anon, authenticated, service_role;
