"""Generate Nexus Learn Loop architecture + next-steps PDF."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT_PATH = Path(__file__).with_name("Nexus-LearnLoop-File-Map-and-Next-Steps.pdf")

NAVY = colors.HexColor("#0f172a")
TEAL = colors.HexColor("#0d9488")
SLATE = colors.HexColor("#334155")
LIGHT = colors.HexColor("#f1f5f9")
AMBER = colors.HexColor("#f59e0b")
WHITE = colors.white


def styles():
    base = getSampleStyleSheet()
    s = {
        "cover_kicker": ParagraphStyle(
            "cover_kicker",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            textColor=TEAL,
            alignment=TA_CENTER,
            letterSpacing=1.2,
            spaceAfter=8,
        ),
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=26,
            textColor=NAVY,
            alignment=TA_CENTER,
            leading=32,
            spaceAfter=8,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=11,
            textColor=SLATE,
            alignment=TA_CENTER,
            leading=16,
            spaceAfter=6,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=NAVY,
            spaceBefore=14,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=TEAL,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            textColor=SLATE,
            leading=13.5,
            alignment=TA_JUSTIFY,
            spaceAfter=7,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            textColor=SLATE,
            leading=13,
            leftIndent=4,
        ),
        "cell": ParagraphStyle(
            "cell",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=SLATE,
            leading=11,
        ),
        "cell_b": ParagraphStyle(
            "cell_b",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=NAVY,
            leading=11,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.HexColor("#64748b"),
            alignment=TA_CENTER,
        ),
        "mono": ParagraphStyle(
            "mono",
            parent=base["Normal"],
            fontName="Courier",
            fontSize=8,
            textColor=NAVY,
            leading=11,
            leftIndent=6,
            spaceAfter=4,
        ),
        "callout": ParagraphStyle(
            "callout",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            textColor=NAVY,
            leading=13.5,
            alignment=TA_LEFT,
        ),
    }
    return s


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, A4[1] - 14 * mm, A4[0], 14 * mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(18 * mm, A4[1] - 9 * mm, "Nexus Learn Loop  |  File connectivity map")
    canvas.drawRightString(A4[0] - 18 * mm, A4[1] - 9 * mm, "20 Oct 2026")
    canvas.setFillColor(TEAL)
    canvas.rect(0, 0, A4[0], 10 * mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(18 * mm, 4 * mm, "Internal architecture brief")
    canvas.drawRightString(A4[0] - 18 * mm, 4 * mm, f"Page {doc.page}")
    canvas.restoreState()


def bullets(items, st):
    return ListFlowable(
        [ListItem(Paragraph(i, st["bullet"]), leftIndent=12, bulletColor=TEAL) for i in items],
        bulletType="bullet",
        start="•",
        leftIndent=12,
        bulletFontName="Helvetica",
        bulletFontSize=9,
        spaceAfter=8,
    )


def table(headers, rows, st, col_widths):
    head = [Paragraph(h, st["cell_b"]) for h in headers]
    body = [[Paragraph(str(c), st["cell"]) for c in row] for row in rows]
    t = Table([head] + body, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("BACKGROUND", (0, 1), (-1, -1), WHITE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    return t


def callout_box(text, st):
    inner = Table(
        [[Paragraph(text, st["callout"])]],
        colWidths=[170 * mm],
    )
    inner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ecfeff")),
                ("BOX", (0, 0), (-1, -1), 1, TEAL),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return inner


def warn_box(text, st):
    inner = Table(
        [[Paragraph(text, st["callout"])]],
        colWidths=[170 * mm],
    )
    inner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffbeb")),
                ("BOX", (0, 0), (-1, -1), 1, AMBER),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return inner


def build():
    st = styles()
    story = []

    story.append(Spacer(1, 28 * mm))
    story.append(Paragraph("ARCHITECTURE BRIEF", st["cover_kicker"]))
    story.append(Paragraph("Nexus Learn Loop", st["cover_title"]))
    story.append(Paragraph("Connected files, current data path, and next steps", st["cover_sub"]))
    story.append(
        Paragraph(
            "Flask + Jinja templates &nbsp;|&nbsp; SQLite today &nbsp;|&nbsp; Supabase planned<br/>Reviewed 20 October 2026",
            st["cover_sub"],
        )
    )
    story.append(Spacer(1, 8 * mm))
    story.append(
        callout_box(
            "<b>Bottom line:</b> The app is a working Flask learning platform with modular blueprints, "
            "session login, quizzes, timer XP, leaderboard, and Gemini AI mentor. Live data still goes through "
            "<b>SQLite</b> (<font face='Courier'>database/database.py</font> + <font face='Courier'>schema.sql</font>). "
            "Supabase files exist as a starter kit only — they are not wired into <font face='Courier'>app.py</font> yet. "
            "Authentication is Flask sessions + password hashes in SQLite, not Supabase Auth.",
            st,
        )
    )

    story.append(Paragraph("1. How the project is wired today", st["h1"]))
    story.append(
        Paragraph(
            "Everything starts in <b>app.py</b>. It loads <font face='Courier'>.env</font>, sets the secret key, "
            "initializes SQLite, injects <b>current_user</b> into templates, and registers five blueprints. "
            "Templates render pages. JavaScript hydrates heatmaps, timer claims, resources search, LWB UI, "
            "and the AI mentor. Tests hit the same blueprints against a temporary SQLite file.",
            st["body"],
        )
    )

    story.append(Paragraph("1.1 Runtime stack (live path)", st["h2"]))
    story.append(
        table(
            ["Layer", "Files", "Role"],
            [
                [
                    "Entrypoint",
                    "app.py",
                    "create_app(), session user, CORS, blueprint registration, SQLite init + seed",
                ],
                [
                    "Auth pages",
                    "blueprints/auth.py → login.html, register.html",
                    "Register / login / logout. Passwords hashed with Werkzeug. Session stores user_id",
                ],
                [
                    "Learner pages",
                    "blueprints/dashboard.py → index, dashboard, profile, leaderboard HTML",
                    "Landing, XP dashboard, profile editor, public rankings",
                ],
                [
                    "Learning loop",
                    "blueprints/learning.py → quiz, result, timer, resources, lwb HTML",
                    "Server-scored quiz, Pomodoro XP, curated resources, LWB preview",
                ],
                [
                    "AI mentor",
                    "blueprints/ai_mentor.py → ai_agent.html + ai_agent.js",
                    "Gemini chat via /api/ai-* using GEMINI_API_KEY",
                ],
                [
                    "JSON APIs",
                    "blueprints/api.py ← main.js, timer.js",
                    "/api/current-user, leaderboard, record-quiz, record-study-session, activity-counts",
                ],
                [
                    "Live database",
                    "database/database.py + schema.sql → instance/nexus.db",
                    "Users, profiles, XP log, study sessions, quiz results",
                ],
                [
                    "Guards",
                    "services/security.py",
                    "login_required, CSRF, SECRET_KEY, safe CORS",
                ],
                [
                    "Scoring",
                    "services/quiz_service.py, streak_service.py",
                    "Answer key + XP on the server; consecutive UTC-day streak",
                ],
            ],
            st,
            [28 * mm, 58 * mm, 84 * mm],
        )
    )

    story.append(Paragraph("1.2 Page graph (templates connected by navigation)", st["h2"]))
    story.append(
        Paragraph(
            "These HTML files share one CSS file (<font face='Courier'>static/css/style.css</font>) and "
            "link to each other through Flask routes (and matching .html aliases).",
            st["body"],
        )
    )
    story.append(
        table(
            ["From", "Goes to", "Why"],
            [
                ["index.html", "login, register, dashboard, AI, quiz, timer, resources, leaderboard, LWB", "Public home / CTAs"],
                ["login.html ↔ register.html", "dashboard after POST", "Auth conversion"],
                ["dashboard.html", "AI, quiz, timer, leaderboard, resources, profile, LWB", "Logged-in hub"],
                ["quiz.html → result.html", "dashboard, timer, leaderboard", "Challenge loop"],
                ["timer.html", "dashboard (after POST XP), quiz, resources", "Focus sprint"],
                ["profile.html", "dashboard, quiz, timer, leaderboard, login", "Showcase + edit form"],
                ["ai_agent.html", "dashboard, resources, quiz, leaderboard, timer", "Mentor workspace"],
                ["lwb.html", "dashboard, AI agent", "Study-buddy preview (UI only)"],
            ],
            st,
            [42 * mm, 72 * mm, 56 * mm],
        )
    )

    story.append(Paragraph("1.3 Frontend scripts and the APIs they call", st["h2"]))
    story.append(
        table(
            ["JS file", "Used by", "Talks to"],
            [
                ["static/js/main.js", "dashboard.html, profile.html", "GET /api/activity-counts, GET /api/current-user"],
                ["static/js/timer.js", "timer.html", "POST /api/record-study-session (JSON duration)"],
                ["static/js/resources.js", "resources.html", "Client-only search/filter (no backend)"],
                ["static/js/lwb.js", "lwb.html", "Local UI only — no WebRTC / Socket.IO yet"],
                [
                    "static/js/ai_agent.js",
                    "ai_agent.html",
                    "GET /api/ai-status, POST /api/ai-chat, /api/ai-models, /api/ai-test-key, or Gemini directly",
                ],
            ],
            st,
            [38 * mm, 48 * mm, 84 * mm],
        )
    )

    story.append(Paragraph("1.4 Data writes (who saves what)", st["h2"]))
    story.append(
        table(
            ["User action", "Route", "SQLite tables written"],
            [
                ["Register", "POST /register", "users + learner_profiles + learning_activity (+50 XP)"],
                ["Login / logout", "POST /login, POST /logout", "session cookie only (no DB write)"],
                ["Edit profile", "POST /profile", "learner_profiles + learning_activity (+15 XP)"],
                ["Submit quiz", "POST /quiz or POST /api/record-quiz", "quiz_results + learning_activity (server XP)"],
                ["Finish timer", "POST /timer or POST /api/record-study-session", "study_sessions + learning_activity"],
                ["Dashboard / heatmap", "GET /dashboard, GET /api/activity-counts", "read-only aggregations"],
                ["Leaderboard", "GET /leaderboard, GET /api/leaderboard", "SUM of learning_activity.xp_earned"],
            ],
            st,
            [40 * mm, 58 * mm, 72 * mm],
        )
    )

    story.append(PageBreak())
    story.append(Paragraph("2. SQLite vs Supabase — current truth", st["h1"]))
    story.append(
        warn_box(
            "<b>Supabase is not the live database yet.</b> <font face='Courier'>app.py</font> always calls "
            "<font face='Courier'>database.database.init_db()</font>. Every blueprint does "
            "<font face='Courier'>import database.database as db</font>. "
            "<font face='Courier'>USE_SUPABASE</font> in <font face='Courier'>.env.example</font> is never read. "
            "<font face='Courier'>supabase</font> is not in <font face='Courier'>requirements.txt</font>. "
            "The adapter only implements stats read — not register, login, quiz write, or timer write.",
            st,
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(
        table(
            ["SQLite (running)", "Supabase (prepared, unused)"],
            [
                [
                    "database/schema.sql — integer IDs, users.password_hash",
                    "database/supabase_schema.sql — UUID user_id from auth.users, RLS policies",
                ],
                [
                    "database/database.py — full CRUD used by all routes",
                    "database/supabase_client.py — client factory + supabase_get_user_stats only",
                ],
                [
                    "instance/nexus.db created on first run",
                    "docs/supabase_guide.md + verify_supabase.py (script currently imports helpers that do not exist)",
                ],
                [
                    "Tests run against temp SQLite",
                    "package.json lists @supabase/server (Node) — unused by the Flask app",
                ],
            ],
            st,
            [85 * mm, 85 * mm],
        )
    )

    story.append(Paragraph("SQLite tables (connected by user_id)", st["h2"]))
    for line in [
        "users 1──1 learner_profiles",
        "users 1──* learning_activity   (XP + heatmap dates)",
        "users 1──* study_sessions      (timer minutes)",
        "users 1──* quiz_results        (challenge scores)",
        "leaderboard = GROUP BY users + SUM(xp_earned)",
        "streak = distinct dates in learning_activity via streak_service.py",
    ]:
        story.append(Paragraph(line, st["mono"]))

    story.append(Paragraph("Supabase tables (designed, not connected)", st["h2"]))
    for line in [
        "auth.users (Supabase Auth) 1──1 public.profiles",
        "auth.users 1──* public.learning_activity",
        "auth.users 1──* public.study_sessions",
        "auth.users 1──* public.quiz_results",
        "public.leaderboard VIEW  (needs extra SELECT policy for community ranks)",
    ]:
        story.append(Paragraph(line, st["mono"]))

    story.append(Paragraph("3. Gaps found in this review", st["h1"]))
    story.append(
        bullets(
            [
                "<b>Auth is local, not Supabase.</b> Register stores password_hash in SQLite. There is no JWT, no Google/GitHub OAuth, no auth.users trigger to create profiles.",
                "<b>Adapter is incomplete.</b> supabase_client.py does not implement create_user, get_user_by_login, record_quiz_result, record_study_session, get_leaderboard, or get_activity_counts.",
                "<b>verify_supabase.py is broken as written</b> — it imports get_supabase_url / get_supabase_key / get_supabase_anon_key, which are missing from supabase_client.py.",
                "<b>Leaderboard + RLS conflict:</b> activity rows are private (auth.uid() = user_id) while the leaderboard view needs public XP totals. That policy must be designed before go-live.",
                "<b>Integer IDs vs UUIDs:</b> Flask session currently stores integer user_id. Supabase Auth uses UUID. Session, APIs, and tests all need that change.",
                "<b>LWB is a mock UI.</b> lwb.js does not persist chat or voice. Needs Socket.IO / WebRTC later.",
                "<b>Only one live quiz</b> is served by the page (jinja2-interpolation); a second quiz exists in quiz_service.py but is unused.",
                "<b>package.json</b> has @supabase/server but the product is Python/Flask — do not mix that in unless you add a Node backend.",
            ],
            st,
        )
    )

    story.append(Paragraph("4. Next steps — authentication + Supabase as the database", st["h1"]))
    story.append(
        Paragraph(
            "Do this in order. Do not flip USE_SUPABASE=true until steps 1–5 work. Keep SQLite as a fallback until the adapter covers every function the blueprints already call.",
            st["body"],
        )
    )

    story.append(Paragraph("Step 1 — Supabase project and schema", st["h2"]))
    story.append(
        bullets(
            [
                "Create a project at supabase.com. Copy Project URL, anon key, and service_role key into <font face='Courier'>.env</font> (never commit service_role).",
                "In SQL Editor, run <font face='Courier'>database/supabase_schema.sql</font>.",
                "Add a trigger: after insert on auth.users, insert a row into public.profiles (username from raw_user_meta_data).",
                "Fix/add RLS: public SELECT on leaderboard (or a SECURITY DEFINER view). Keep writes on activity/quiz/timer owner-only.",
                "Add <font face='Courier'>supabase</font> to <font face='Courier'>requirements.txt</font> and pip install it.",
            ],
            st,
        )
    )

    story.append(Paragraph("Step 2 — Finish the Python adapter (drop-in for database.py)", st["h2"]))
    story.append(
        bullets(
            [
                "Implement the same function names used by blueprints: create_user, get_user, get_user_by_login, update_profile, record_learning_activity, record_study_session, record_quiz_result, get_quiz_result, get_user_stats, get_leaderboard, get_activity_counts, seed_defaults_if_empty.",
                "Use the service_role key only on the Flask server. Never send it to the browser.",
                "Fix verify_supabase.py helpers (URL/key getters) so diagnostics actually run.",
                "Add a thin selector in <font face='Courier'>database/__init__.py</font>: if USE_SUPABASE=true import supabase adapter, else SQLite. Then app.py and blueprints stay unchanged.",
            ],
            st,
        )
    )

    story.append(Paragraph("Step 3 — Replace Flask password auth with Supabase Auth", st["h2"]))
    story.append(
        bullets(
            [
                "<b>Recommended:</b> Register/login call supabase.auth.sign_up / sign_in_with_password from blueprints/auth.py. Store the access token (or user UUID) in the Flask session. Stop writing password_hash locally.",
                "Optional later: Google / GitHub OAuth via Supabase Auth providers.",
                "Update login_required to treat a missing/expired Supabase user as logged out.",
                "On first login, ensure a profiles row exists (trigger or explicit insert).",
                "Award +50 XP signup bonus by inserting into learning_activity with the new UUID.",
                "Logout: session.clear() plus supabase.auth.sign_out() if you keep a refresh token server-side.",
            ],
            st,
        )
    )

    story.append(Paragraph("Step 4 — Wire writes (quiz, timer, profile, heatmap)", st["h2"]))
    story.append(
        bullets(
            [
                "Keep scoring in quiz_service.py (server still decides XP). Only the persistence target changes.",
                "Timer still validates 1–180 minutes in quiz_service; then insert study_sessions + learning_activity in Postgres.",
                "Heatmap GET /api/activity-counts should query learning_activity grouped by day for the session UUID.",
                "Leaderboard should read the Postgres view, not SQLite GROUP BY.",
            ],
            st,
        )
    )

    story.append(Paragraph("Step 5 — Tests, then cut over", st["h2"]))
    story.append(
        bullets(
            [
                "Keep existing unittest suite on SQLite (local CI).",
                "Add a small integration test (or verify_supabase.py) that inserts one profile, one quiz, one session, then reads stats.",
                "Set USE_SUPABASE=true only after register → dashboard → quiz → timer → heatmap → leaderboard all succeed against Postgres.",
                "Stop calling init_db() / seed_defaults against SQLite when Supabase is on (demo peers can be inserted once via SQL).",
            ],
            st,
        )
    )

    story.append(Paragraph("Step 6 — After the cutover (product, not blockers)", st["h2"]))
    story.append(
        bullets(
            [
                "Turn LWB from mockup into real rooms (Socket.IO + optional WebRTC).",
                "Serve more quizzes from the registry; persist question banks in Supabase if they grow.",
                "Move Gemini key fully server-side; stop encouraging client-side key paste in production.",
                "Deploy Flask (Render/Fly/Railway) with SECRET_KEY, SESSION_COOKIE_SECURE, and ALLOWED_ORIGINS.",
            ],
            st,
        )
    )

    story.append(Paragraph("5. Suggested file work list (implementation order)", st["h1"]))
    story.append(
        table(
            ["#", "File", "Change"],
            [
                ["1", "database/supabase_schema.sql", "Add auth.users → profiles trigger; leaderboard SELECT policy"],
                ["2", "database/supabase_client.py", "Full CRUD matching database.py; URL/key helpers"],
                ["3", "database/__init__.py (new)", "Switch SQLite vs Supabase from USE_SUPABASE"],
                ["4", "requirements.txt", "Add supabase Python client"],
                ["5", "blueprints/auth.py", "sign_up / sign_in_with_password; session user UUID"],
                ["6", "app.py + get_current_user", "Skip SQLite init when USE_SUPABASE; UUID users"],
                ["7", "blueprints/api.py, dashboard.py, learning.py", "No SQL change if adapter is drop-in"],
                ["8", "verify_supabase.py", "Fix imports; optional write smoke test"],
                ["9", "tests/", "Keep SQLite tests; add skipped-unless-env Supabase test"],
                ["10", ".env / .env.example", "USE_SUPABASE=true only after Step 5"],
            ],
            st,
            [12 * mm, 52 * mm, 106 * mm],
        )
    )

    story.append(Paragraph("6. File inventory (all connected pieces)", st["h1"]))
    story.append(
        table(
            ["Path", "Connected to"],
            [
                ["app.py", "security.py, database.py, all five blueprints, templates via context"],
                ["blueprints/auth.py", "database.py, security.py, login.html, register.html, dashboard"],
                ["blueprints/dashboard.py", "database.py, security.py, index/dashboard/profile/leaderboard.html"],
                ["blueprints/learning.py", "database.py, quiz_service.py, quiz/result/timer/resources/lwb.html"],
                ["blueprints/ai_mentor.py", "GEMINI_API_KEY, ai_agent.html, Google Generative Language API"],
                ["blueprints/api.py", "database.py, quiz_service.py, main.js, timer.js"],
                ["database/database.py", "schema.sql, streak_service.py, instance/nexus.db, every blueprint"],
                ["database/supabase_client.py", "streak_service.py, env vars — not imported by app.py"],
                ["services/security.py", "app.py, auth, dashboard, learning, api"],
                ["services/quiz_service.py", "learning.py, api.py"],
                ["services/streak_service.py", "database.py, supabase_client.py"],
                ["static/js/*", "matching templates + /api/* routes"],
                ["tests/test_*.py", "create_app + SQLite database.py"],
                ["docs/supabase_guide.md", "schema + env setup (documentation only)"],
            ],
            st,
            [52 * mm, 118 * mm],
        )
    )

    story.append(Spacer(1, 6 * mm))
    story.append(
        callout_box(
            "<b>Immediate next action:</b> complete the Supabase adapter and Auth switch (steps 1–5). "
            "Until then, keep developing features against SQLite so tests stay fast. "
            "Do not treat LWB or extra Node packages as part of the database migration.",
            st,
        )
    )

    doc = SimpleDocTemplate(
        str(OUT_PATH),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=16 * mm,
        title="Nexus Learn Loop — File Map and Next Steps",
        author="Nexus Learn Loop review",
    )
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    return OUT_PATH


if __name__ == "__main__":
    path = build()
    print(f"Wrote {path}")
