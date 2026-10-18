# Nexus-learnloop
Nexus Learn Loop is a competitive, gamified learning platform for Nexus learners, inspired by  Duolingo. It helps learners build consistent habits, connect with peers, showcase their  achievements, and grow together.

Key Features 
1. Resources: Personalized YouTube tutorials, useful websites, and learning materials 
based on learners’ interests. 
2. Showcase: A GitHub-inspired profile to display projects, skills, learning goals, streaks, 
and achievements. 
3. Daily Streaks: Build consistent learning habits through streaks, XP points, badges, and 
rewards. 
4. AI Chatbot: Get instant help with doubts, technical queries, and learning concepts. 
5. Questions & Challenges: Practice coding, solve quizzes, and participate in daily 
challenges. 
6. Study Timer: A YPT-inspired timer to track study hours, monitor progress, and study 
alongside friends. 
7. LWB (Learning With Buddies): Voice chat (VC), text chat (TC), and collaborative study 
rooms to learn together. 
8. Leaderboard: A competitive ranking system based on learning consistency, streaks, 
study activity, and achievements. 
Our Vision 
To create a community where Nexus learners learn new skills, stay consistent, collaborate 
with peers, showcase their progress, and compete to become better every day. 
Nexus Learn Loop — Learn together. Compete fairly. Grow endlessly.

Nexus Learn Loop: Tech Stack Guide
A vibe-coding-friendly technology plan for a real-time, social, gamified learning platform.
The app needs a good database, authentication, real-time features, and a few third-party
APIs. This stack is chosen to be easy for AI tools to generate correctly and cheap to start
with.
1. Core stack
Layer Recommendation Why
Framework Next.js (App Router) + TypeScript Frontend and backend in one
project. AI tools know it very
well, so vibe coding works
smoothly.
Styling Tailwind CSS + shadcn/ui Fast, clean UI. Most AI tools
generate this combo by default.
Animations Framer Motion Streak flames, XP pop-ups,
badge unlocks, and other
Duolingo-style touches.
Backend and DB Supabase (Postgres + Auth +
Realtime + Storage)
One service covers most needs,
so no separate backend.
Hosting Vercel One-click deploys from GitHub,
with cron jobs built in.
State and data
fetching
TanStack Query + Zustand Server data caching and small
client state (timer, UI).
Forms and
validation
React Hook Form + Zod Clean forms with safe input
checks.
Nexus Learn Loop: Tech Stack Guide
Page 1 of 5
Nexus Learn Loop: Tech Stack Guide
2. Feature-by-feature mapping
Authentication and profiles
Supabase Auth with Google and GitHub login. Learners already use these, and GitHub
login pairs well with the GitHub-style profile.
Optional: restrict signups to Nexus learners with an invite code or an allowed email
domain.
1. Resources (personalized tutorials)
YouTube Data API v3 to fetch tutorials by interest tags.
Store learners' interests in Postgres and build queries from them.
Seed useful websites manually in a 
them.
2. Showcase (GitHub-style profile)
resources table. Add an admin page to manage
Postgres tables for projects, skills, and achievements.
react-activity-calendar for the GitHub-style contribution heatmap, built from your
own streak and study data.
Optional: the GitHub REST API to import repos.
3. Daily streaks, XP, badges
Postgres tables: 
xp_events , 
streaks , 
badges , 
user_badges .
Database functions or triggers to award XP and badges consistently.
Vercel Cron or Supabase pg_cron to reset or check streaks at midnight. Store each
user's timezone, or streaks will break for people in different time zones.
canvas-confetti for celebration effects.
4. AI chatbot
Claude API (Anthropic) through the Vercel AI SDK for streaming responses.
Always call it from a server route, never from the browser, so your API key stays hidden.
Add a system prompt that makes it a Nexus learning tutor, and rate limiting to control
cost.
Page 2 of 5
Nexus Learn Loop: Tech Stack Guide
5. Questions and challenges
Monaco Editor (the VS Code editor) for in-browser coding.
Judge0 or Piston API to run and test user code safely. Never run user code on your
own server.
Quizzes are simple multiple-choice questions in Postgres.
Daily challenge: a cron job or a 
6. Study timer
daily_challenges table keyed by date.
The timer runs in the browser (Zustand + 
setInterval , using timestamps rather than
counting ticks so it stays accurate in background tabs).
Save sessions to Postgres when they stop.
Supabase Realtime Presence shows which friends are studying right now.
Charts with Recharts for daily and weekly study hours.
7. LWB (voice chat, text chat, study rooms)
Text chat: Supabase Realtime (channels) with messages in Postgres.
Voice chat: LiveKit (best fit), Daily.co, or Agora. All have free tiers and React
components. Don't build WebRTC from scratch.
Study rooms: a 
rooms table combined with a LiveKit room and a Realtime channel.
8. Leaderboard
Start with a Postgres view or materialized view ranked by weekly XP, streak, and study
hours.
If it gets heavy, move to Upstash Redis sorted sets.
Offer weekly, monthly, and all-time tabs.
For "compete fairly" (your tagline), plan some anti-cheating: cap daily XP and validate
timer sessions on the server.
3. Supporting tools
Notifications: Resend for streak reminder emails, plus Web Push (PWA) for browser
notifications.
PWA support: 
next-pwa so the app is installable on phones. Most learners will use it
on mobile.
Page 3 of 5
Nexus Learn Loop: Tech Stack Guide
Rate limiting: Upstash Ratelimit, especially for the chatbot and code runner.
Analytics and error tracking: PostHog and Sentry (both optional, both free tiers).
Image and file storage: Supabase Storage for avatars and project screenshots.
Security: Supabase Row Level Security (RLS) policies on every table. AI tools often
skip this, so ask for it explicitly.
4. Vibe coding tools
Claude Code or Cursor: best for building the main project in your own codebase.
v0.dev: good for generating polished UI components (leaderboard, profile page) that
you paste in.
Lovable or Bolt: fast for prototyping, but you'll outgrow them on a project this big.
GitHub + Vercel: push often so you can roll back when the AI breaks something.
5. Vibe coding tips for this project
1. Write a spec first. Turn your PDF into a 
PROJECT.md or 
CLAUDE.md file with the stack,
features, and rules, and keep it in the repo so the AI keeps context.
2. Design the database schema first. Ask the AI to propose tables, review them, then
build features on top. A bad schema is the hardest thing to fix later.
3. Build one feature at a time, and commit after each working one.
4. Keep secrets in 
.env : API keys for Claude, YouTube, LiveKit, and Judge0 must never
go in client code or GitHub.
5. Test the fairness-critical parts yourself: streak logic, XP awarding, and the
leaderboard are where bugs hurt trust.
6. Suggested build order
1. Phase 1 (MVP): Auth, profiles, Showcase, Resources
2. Phase 2: Study timer, streaks, XP, badges, leaderboard
3. Phase 3: Questions and challenges, AI chatbot
4. Phase 4: LWB (text chat, then voice and study rooms)
5. Phase 5: Notifications, PWA, polish, anti-cheat
Page 4 of 5
Nexus Learn Loop: Tech Stack Guide
LWB with voice chat is the hardest part, so leave it for later. The first three phases already
give you a working, engaging product.
7. Costs
Costs are close to zero at the start, since Supabase, Vercel, LiveKit, and Upstash all have
free tiers. The Claude API is the main paid part, and it is usage-based
