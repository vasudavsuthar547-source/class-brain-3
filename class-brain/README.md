# Teacher Class Brain - tiny prototype

## Two ways to run it
A) LOCAL, no installs (just Python 3.9+):  python app_local.py   (Mac: python3 app_local.py)  then open http://localhost:8000
B) STREAMLIT (this is what GitHub / Streamlit Cloud runs):
   pip install -r requirements.txt
   streamlit run app.py
Stop either with Ctrl+C.

The first run creates `classbrain.db` (a single-file database) and fills it with FAKE demo data.
To reset everything, stop the app and delete `classbrain.db`.

UPGRADING FROM VERSION 1? Delete your old `classbrain.db` first, so the new demo data (a second test) gets created.

## What each file does
- db.py         Part 1: database tables + fake demo class
- analytics.py  Part 2: all the maths (averages, weak topics, revision plan)
- brain.py      Part 3a: turns the numbers into answers (Known data / Analysis / Suggestion)
- app.py        Part 3b: the website (dashboard, students, enter marks, Ask Class Brain)

## Questions it understands right now
"Why did my class perform poorly?", "What should I revise?", "Which students need attention?",
"What is the class average?", "What changed since the last test?" (also: improved, trend, progress). Anything else gets: "I don't have enough data to determine that."

## Tests and trends (version 2)
- The Tests page lists every test and lets you create a new one (topics, one per line, like `Demand, 15`).
- Reuse the exact same topic names across tests, so they can be compared.
- "Since last test" compares only topics both tests covered, because comparing different topics would be misleading.

## The AI layer (version 3) - optional
Without a key, the app works exactly as before (calculated rules). To turn the AI on:
1. Get an API key from console.anthropic.com (API accounts have age requirements, and usage costs a little money).
2. Set it for ONE terminal session (never write it inside a code file, never share it, never upload it to GitHub):
   - Windows (cmd):  set ANTHROPIC_API_KEY=your-key-here
   - Mac/Linux:      export ANTHROPIC_API_KEY=your-key-here
3. In that same terminal run: python app.py
4. Ask a question. Under "You asked" it says "answered by: AI" or "calculated rules".

If the AI fails for any reason, the app falls back to the calculated answer and tells you why.
Optional: choose another model with the CLASSBRAIN_MODEL environment variable.

How the AI is kept honest and private:
- It receives only numbers calculated by analytics.py, never the database.
- Student names are replaced by codes (S01...) before sending, and swapped back in afterwards.
- Its instructions say: use only the given facts, say "I don't have enough data" when unsure, never label students.

New file: llm.py

## Four subjects (version 4)
Built for Class 11 CBSE Commerce: English, Accountancy, Business Studies (BST) and Economics.
- Dashboard tabs: "All subjects" (overview) plus one tab per subject.
- Every test belongs to a subject. "Since last test" compares a test only with the previous test of the SAME subject.
- "All subjects" shows each subject's weakest topic and students below 50% in two or more subjects.
- Questions can name a subject ("Why is accounts low?", "How is BST doing?") or use the tab you are on.
- The demo chapter names are ILLUSTRATIVE. The CBSE syllabus changes, so use the topic names from your own school's syllabus when you create tests (Tests page).
- UPGRADING? Delete your old classbrain.db first so the four-subject demo data is created.
- The AI now receives all four subjects at once (about 30,000 characters per question), so each AI question uses more of your API allowance than before.

## Accountancy focus + textbook (version 5)
For now the project covers Accountancy only. The other subjects still work in the code and can be added later from the Tests page.
- Demo data: Accountancy only, with the REAL chapter names of the NCERT Accountancy Part I textbook.
- syllabus.json holds the 7 chapters and 142 section titles taken from your uploaded PDFs (titles only, no textbook text).
- Weak topics are matched to their textbook chapter and sections ("From your textbook: ...").
- Syllabus page: every chapter with its latest class result.
- Tests page: tick chapters from a checklist (keeps topic names identical, so comparisons work).
- The AI also receives the chapter and section titles, and may only cite those.
- Not included: Part II of the textbook (bills of exchange, financial statements, etc.). Upload it later and we add its chapters.
- tools/build_syllabus.py shows how syllabus.json was made (optional; needs the PDFs and poppler).
- UPGRADING? Delete your old classbrain.db first.

## Version 6: Streamlit + GitHub
- app.py is now the STREAMLIT version. The old server version is app_local.py (same features).
- requirements.txt must sit next to app.py (it only needs streamlit; pandas comes with it).
- .gitignore keeps your database, secrets, .env and PDFs OUT of GitHub. Do not remove it.
- On Streamlit Cloud: Main file = the path to app.py (for you: class-brain/app.py). Push to GitHub, then open the app; if it does not refresh, use "Reboot app" in Manage app.
- Secrets (app settings > Secrets, never in code):
    ANTHROPIC_API_KEY = "your-key"     # optional, turns on the AI checkbox
    APP_PASSWORD = "choose-a-password" # optional, locks the app behind a password
- The AI is OFF until someone ticks "Use AI for answers", so a public demo does not spend your credits by accident.
- Use FAKE students only on a public app. The database file may reset when the app restarts.
- If the install fails, try Python 3.12 in the app's Advanced settings.
