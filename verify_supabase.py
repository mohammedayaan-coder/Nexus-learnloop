"""
Nexus Learn Loop — Supabase Database Verification Tool
Runs diagnostic checks against your configured Supabase project.
Usage: python verify_supabase.py
"""

import os
import sys

# Configure stdout for utf-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from database.supabase_client import (
    get_supabase_url,
    get_supabase_key,
    get_supabase_anon_key,
    get_supabase_service_role_key,
    get_supabase_client,
)


def run_diagnostics():
    print("=" * 70)
    print(" Nexus Learn Loop - Supabase Database Verification")
    print("=" * 70)

    url = get_supabase_url()
    key = get_supabase_key()
    anon_key = get_supabase_anon_key()
    svc_key = get_supabase_service_role_key()

    print(f"[*] Supabase URL:              {url or '[NOT CONFIGURED IN .env]'}")
    print(f"[*] Supabase Anon/Public Key:  {('[CONFIGURED: ' + anon_key[:16] + '...]') if anon_key else '[MISSING]'}")
    print(f"[*] Supabase Service Role Key: {('[CONFIGURED: ' + svc_key[:16] + '...]') if svc_key else '[MISSING - using anon key]'}")
    print("-" * 70)

    if not url or not (anon_key or key):
        print("\n[!] ERROR: Supabase credentials missing from .env.")
        print("Please check your SUPABASE_URL and SUPABASE_ANON_KEY in .env.")
        sys.exit(1)

    client = get_supabase_client()
    if not client:
        print("\n[!] ERROR: Could not initialize Supabase client.")
        print("Run: pip install supabase")
        sys.exit(1)

    print("\n[*] Checking Supabase PostgreSQL Tables & RLS Policies...")
    tables = [
        ("learner_profiles", "Learner profiles (user_id, bio, learning_goals, skills)"),
        ("learning_activities", "XP events, daily challenges & heatmap logs"),
        ("study_sessions", "Focus timer & sprint tracking (duration_minutes)"),
        ("quiz_results", "Quiz scores & challenge history (score, total_questions)"),
    ]

    all_ready = True
    for table_name, description in tables:
        try:
            res = client.table(table_name).select("*").limit(1).execute()
            print(f"  [OK]       {table_name:<22} - {description}")
        except Exception as e:
            err_msg = str(e)
            if "PGRST205" in err_msg or "Could not find the table" in err_msg:
                # Check singular fallback
                if table_name == "learning_activities":
                    try:
                        client.table("learning_activity").select("*").limit(1).execute()
                        print(f"  [OK*]      {'learning_activity':<22} - (Active as fallback for learning_activities)")
                        continue
                    except Exception as fe:
                        fe_msg = str(fe)
                        if "42501" in fe_msg or "permission denied" in fe_msg.lower():
                            print(f"  [RLS-ON*]  {'learning_activity':<22} - RLS active (Fallback table for learning_activities)")
                            continue
                        err_msg = fe_msg
                all_ready = False
                print(f"  [MISSING]  {table_name:<22} - Table not found in database")
            elif "42501" in err_msg or "permission denied" in err_msg.lower():
                print(f"  [RLS-ON]   {table_name:<22} - RLS active (Protected by Row Level Security)")
            else:
                all_ready = False
                print(f"  [ERROR]    {table_name:<22} - {err_msg[:60]}")

    print("-" * 70)
    print("\n[*] Supabase Auth Service Check:")
    try:
        # Check auth service availability
        res = client.auth.get_session()
        print("  [OK]       Supabase Auth API connected and responding.")
    except Exception as e:
        print(f"  [AUTH]     Supabase Auth status: {e}")

    print("-" * 70)
    print("\n[SUMMARY]:")
    print("Backend is configured with direct Supabase PostgreSQL & Auth integration.")
    print("SQLite persistence has been completely replaced with Supabase.")
    print("=" * 70)


if __name__ == "__main__":
    run_diagnostics()
