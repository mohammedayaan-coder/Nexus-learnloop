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

## Database

The Flask app initializes the SQLite schema from `database/schema.sql` on startup.
By default, the database is stored at `instance/nexus.db`; set `DATABASE_PATH` to use a
different file. Account passwords are stored as Werkzeug password hashes. Learner
profiles, completed study sessions, quiz results, and XP activity are associated with
their owning user through foreign keys. Set `SECRET_KEY` to a stable, private value
when deploying so signed-in sessions remain valid across restarts.