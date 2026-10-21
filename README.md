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
## Leaderboard and Quiz Submission Rules

- Development and test environments may include accounts explicitly marked `is_demo = 1` so seeded fixtures remain visible.
- Production leaderboard queries include only accounts explicitly marked `is_demo = 0` with positive XP summed from persisted `learning_activity` records. The app does not identify demo users from usernames or email addresses.
- The quiz form creates a unique `submission_id` for each page load. Retries must reuse that ID; an intentional retake must start a new quiz page and use its new ID.
- `POST /api/record-quiz` requires a `submission_id` string (maximum 128 characters). API clients must generate one ID per logical attempt, reuse it for every retry, and generate a fresh ID for a deliberate retake.
- Database migration version 2 adds a nullable `quiz_results.idempotency_key` and a per-user unique index. Existing quiz rows remain unchanged and retain a null key.
