# Nexus Learn Loop — Supabase PostgreSQL Migration Guide

This guide walks through connecting the Nexus Learn Loop Flask application to Supabase Postgres with Row Level Security (RLS).

---

## 1. Create a Supabase Project

1. Log in to [Supabase](https://supabase.com/) and click **New Project**.
2. Name your project (e.g. `nexus-learn-loop`) and set a strong database password.
3. Once provisioned, navigate to **Project Settings > API** to locate:
   * **Project URL**: `https://<your-project-id>.supabase.co`
   * **anon / public key**: `eyJhbGciOi...` (publishable key)
   * **service_role key**: `eyJhbGciOi...` (backend server operations only; keep secret)

---

## 2. Execute the Postgres Schema

Open the **SQL Editor** in your Supabase dashboard and run the contents of [`database/supabase_schema.sql`](../database/supabase_schema.sql).

This script automatically creates:
1. `public.profiles`: User profile data linked to Supabase Auth (`auth.users(id) ON DELETE CASCADE`).
2. `public.learning_activity`: XP log and daily activity counts.
3. `public.study_sessions`: Focus timer sprint logs with physiological checks (1–180 minutes).
4. `public.quiz_results`: Quiz attempts and scores.
5. `public.leaderboard`: SQL view calculating total XP across learners.
6. **Row Level Security (RLS)**: Enforces `auth.uid() = user_id` on all tables so learners can only read and write their own records.

---

## 3. Configure Flask Environment Variables

Add the following to your `.env` file:

```env
USE_SUPABASE=true
SUPABASE_URL=https://<your-project-id>.supabase.co
SUPABASE_KEY=eyJhbGciOi... (or SUPABASE_SERVICE_ROLE_KEY)
```

Install the Supabase Python client if you plan to use direct client integration:
```bash
pip install supabase
```

---

## 4. Auth Transition Architecture

### Recommended: Native Supabase Auth
* Users register and log in via Supabase Auth (or OAuth providers like GitHub / Google).
* Flask validates the JWT on incoming requests:
  ```python
  from supabase import create_client
  supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
  user = supabase.auth.get_user(jwt_token)
  ```
* Requests sent to Postgres carry the authenticated learner's identity so RLS is automatically enforced.

### Interim: Server-Side Postgres Connection
* Keep Flask session cookies.
* Flask connects using `SUPABASE_SERVICE_ROLE_KEY` to query Postgres.
* The Flask server enforces `user_id = session["user_id"]` on every route.
* `SUPABASE_SERVICE_ROLE_KEY` is kept on the server and never exposed to the frontend.
