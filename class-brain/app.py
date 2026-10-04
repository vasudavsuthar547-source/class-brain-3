"""Teacher Class Brain - STREAMLIT version (the file Streamlit Community Cloud runs).
Run locally:  streamlit run app.py
All the real work happens in db.py, analytics.py, brain.py, llm.py and syllabus.py.
This file only draws the screens."""
import os

import pandas as pd
import streamlit as st

import analytics
import brain
import db
import llm
import syllabus

CLASS_ID = 1  # the MVP has one class; multiple classes come later

st.set_page_config(page_title="Teacher Class Brain", page_icon="🧠", layout="wide")


def secret(name):
    """Reads a value from Streamlit's secrets (set in the app settings, never in code). None if missing."""
    try:
        return st.secrets.get(name)
    except Exception:
        return None


# --- optional AI key, from secrets -> environment variable (llm.py reads the environment) ---
_key = secret("ANTHROPIC_API_KEY")
if _key and not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = str(_key)

db.init_db()
db.seed_demo()

# --- optional password gate: set APP_PASSWORD in secrets to turn it on ---
_password = secret("APP_PASSWORD")
if _password and not st.session_state.get("unlocked"):
    st.title("Teacher Class Brain")
    typed = st.text_input("Password", type="password")
    if typed and typed == str(_password):
        st.session_state["unlocked"] = True
        st.rerun()
    elif typed:
        st.error("Wrong password.")
    st.stop()


def class_name():
    conn = db.connect()
    row = conn.execute("SELECT name FROM classes WHERE id=?", (CLASS_ID,)).fetchone()
    conn.close()
    return row["name"] if row else "Class"


def show_table(rows, **kwargs):
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, **kwargs)


# ============================ DASHBOARD ============================

def ask_box(subject, use_ai):
    with st.form("ask_form"):
        question = st.text_input("Ask Class Brain", placeholder="e.g. Why did my class perform poorly?")
        asked = st.form_submit_button("Ask")
    if asked and question.strip():
        q = question.strip()[:500]
        st.session_state["answer"] = {"q": q, "a": brain.ask(CLASS_ID, q, subject, use_ai)}
    item = st.session_state.get("answer")
    if item:
        a = item["a"]
        with st.container(border=True):
            st.markdown("**You asked:** " + item["q"])
            for title, key in (("Known data", "data"), ("Analysis", "analysis"), ("Suggestion", "suggestion")):
                if a.get(key):
                    st.markdown("**" + title + "**")
                    for line in a[key]:
                        st.write(line)
            st.caption("Answered by: " + a.get("source", ""))


def subject_view(subject):
    f = analytics.analyze_class(CLASS_ID, subject=subject)
    if not f:
        st.info("No marks yet for " + subject + ". Go to Tests, pick a test, and enter marks.")
        return
    st.subheader(f["assessment"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Students", f["student_count"])
    c2.metric("Class average", "{:.0f}%".format(f["class_average"]))
    c3.metric("Topics needing attention", len(f["attention"]))

    left, right = st.columns(2)
    with left:
        st.markdown("**Strong areas**")
        for t in f["strong"]:
            st.write("✓ " + t["topic"])
        if not f["strong"]:
            st.write("None above 70%")
        st.markdown("**Needs attention**")
        for t in f["attention"]:
            st.write("⚠ " + t["topic"])
        if not f["attention"]:
            st.write("None below 55%")
    with right:
        st.markdown("**Suggested action** (a suggestion, not a rule)")
        for minutes, text in analytics.revision_plan(f):
            st.write("{} min — {}".format(minutes, text))

    c = analytics.compare_latest(CLASS_ID, subject)
    if c and c["shared_topics"] and c["prev_avg"] is not None:
        st.subheader("Since last test")
        st.caption("{} → {} (shared topics only)".format(c["prev_name"], c["cur_name"]))
        st.write("Class average: {:.0f}% → {:.0f}% ({:+.0f})".format(c["prev_avg"], c["cur_avg"], c["cur_avg"] - c["prev_avg"]))
        show_table([{"Topic": t["topic"], "Then %": round(t["prev"]), "Now %": round(t["cur"]), "Change": round(t["change"])}
                    for t in c["topics"]])

    st.subheader("Topic performance")
    rows = []
    for t in f["topics"]:
        ch = syllabus.match_chapter(subject, t["topic"])
        rows.append({"Topic": t["topic"], "Textbook": "Ch {}".format(ch["chapter"]) if ch else "-",
                     "Average %": round(t["average"]), "Students below 50%": t["below_50"]})
    show_table(rows, column_config={"Average %": st.column_config.ProgressColumn("Average %", min_value=0, max_value=100, format="%d")})

    st.subheader("Students below 50% in this test")
    st.caption("One test only: use your own judgement.")
    show_table([{"Name": s["name"], "Overall %": round(s["percent"]), "Lowest topic": s["weakest_topic"]}
                for s in f["students_flagged"]])


def overview_view():
    o = analytics.class_overview(CLASS_ID)
    if not o["subjects"]:
        st.info("No marks yet. Go to Tests, pick a test, and enter marks.")
        return
    st.subheader("Subjects at a glance")
    st.caption("Most recent test in each subject. Change is on topics both tests covered.")
    show_table([{"Subject": r["subject"], "Test": r["assessment_name"], "Average %": round(r["average"]),
                 "Lowest topic": "{} ({:.0f}%)".format(r["weakest"]["topic"], r["weakest"]["average"]),
                 "Change": "-" if r["change"] is None else "{:+.0f}".format(r["change"])} for r in o["subjects"]])
    st.subheader("Students below 50% in two or more subjects")
    st.caption("A starting point, not a verdict.")
    if o["flagged"]:
        show_table([{"Name": d["name"], "Average %": round(d["average"]), "Below 50% in": ", ".join(d["below_50"])} for d in o["flagged"]])
    else:
        st.write("No student is below 50% in two or more subjects.")


def page_dashboard(use_ai):
    available = analytics.subjects(CLASS_ID)
    st.title(class_name())
    subject = None
    if len(available) == 1:
        subject = available[0]
    elif len(available) > 1:
        choice = st.radio("View", ["All subjects"] + available, horizontal=True)
        subject = None if choice == "All subjects" else choice
    ask_box(subject, use_ai)
    if not available:
        st.info("No tests yet. Go to Tests to create one.")
    elif subject:
        subject_view(subject)
    else:
        overview_view()


# ============================ STUDENTS ============================

def page_students():
    st.title("Students")
    with st.form("add_student", clear_on_submit=True):
        name = st.text_input("Student name", placeholder="Use fake names while testing")
        added = st.form_submit_button("Add student")
    if added and name.strip():
        conn = db.connect()
        conn.execute("INSERT INTO students (class_id, name) VALUES (?, ?)", (CLASS_ID, name.strip()[:80]))
        conn.commit()
        conn.close()
        st.rerun()
    conn = db.connect()
    rows = conn.execute("SELECT name FROM students WHERE class_id=? ORDER BY id", (CLASS_ID,)).fetchall()
    conn.close()
    st.write("{} students".format(len(rows)))
    show_table([{"Name": r["name"]} for r in rows])


# ============================ TESTS ============================

def parse_extra_topics(text):
    parsed = []
    for line in text.splitlines():
        if not line.strip():
            continue
        topic, _, mx = line.rpartition(",")
        try:
            mx = float(mx)
        except ValueError:
            mx = 0
        if topic.strip() and mx > 0:
            parsed.append((topic.strip()[:80], mx))
    return parsed


def page_tests():
    st.title("Tests")
    show_table([{"Subject": a["subject"], "Test": a["name"]} for a in analytics.list_assessments(CLASS_ID)])
    st.subheader("Create a new test")
    present = analytics.subjects(CLASS_ID)
    options = present + [s for s in analytics.SUBJECT_ORDER if s not in present]
    chapters = syllabus.chapters("Accountancy")
    with st.form("new_test"):
        subject = st.selectbox("Subject", options)
        name = st.text_input("Test name", placeholder="Unit Test 3")
        ticked = []
        if chapters:
            st.markdown("**Accountancy chapters**: tick the chapters in this test and set the maximum marks for each.")
            for ch in chapters:
                col1, col2 = st.columns([3, 1])
                tick = col1.checkbox("Ch {}. {}".format(ch["chapter"], ch["title"]), key="ch_{}".format(ch["chapter"]))
                mx = col2.number_input("Max marks", min_value=1.0, value=10.0, step=1.0,
                                       key="mx_{}".format(ch["chapter"]), label_visibility="collapsed")
                if tick:
                    ticked.append((ch["title"], float(mx)))
        extra = st.text_area("Other topics (optional), one per line, like: Project work, 10")
        created = st.form_submit_button("Create test")
    if created:
        topics = ticked if subject == "Accountancy" else []
        topics = topics + [p for p in parse_extra_topics(extra) if p[0] not in [t[0] for t in topics]]
        if not (name.strip() and topics):
            st.error("Please give a test name and at least one chapter or topic with maximum marks.")
            return
        conn = db.connect()
        cur = conn.execute("INSERT INTO assessments (class_id, subject, name) VALUES (?, ?, ?)", (CLASS_ID, subject, name.strip()[:60]))
        for topic, mx in topics:
            conn.execute("INSERT INTO assessment_topics (assessment_id, topic, max_marks) VALUES (?, ?, ?)", (cur.lastrowid, topic, mx))
        conn.commit()
        conn.close()
        st.session_state["marks_test"] = cur.lastrowid
        st.success("Test created. Open 'Enter marks' in the left menu to type in the marks.")


# ============================ ENTER MARKS ============================

def page_marks():
    st.title("Enter marks")
    tests = analytics.list_assessments(CLASS_ID)
    if not tests:
        st.info("No tests yet. Create one on the Tests page.")
        return
    labels = {a["id"]: "{} - {}".format(a["subject"], a["name"]) for a in tests}
    ids = list(labels)
    wanted = st.session_state.get("marks_test", ids[-1])
    aid = st.selectbox("Test", ids, index=ids.index(wanted) if wanted in ids else len(ids) - 1, format_func=lambda i: labels[i])

    conn = db.connect()
    topics = conn.execute("SELECT * FROM assessment_topics WHERE assessment_id=? ORDER BY id", (aid,)).fetchall()
    students = conn.execute("SELECT * FROM students WHERE class_id=? ORDER BY id", (CLASS_ID,)).fetchall()
    existing = {}
    for r in conn.execute("SELECT s.* FROM scores s JOIN assessment_topics t ON s.assessment_topic_id=t.id WHERE t.assessment_id=?", (aid,)):
        existing[(r["student_id"], r["assessment_topic_id"])] = r["marks"]
    conn.close()

    columns = {}  # column label -> topic row
    for t in topics:
        label = "{} (/{:g})".format(t["topic"], t["max_marks"])
        if label in columns:
            label += " #{}".format(t["id"])
        columns[label] = t
    table = pd.DataFrame(index=[s["id"] for s in students])
    table["Student"] = [s["name"] for s in students]
    for label, t in columns.items():
        table[label] = pd.to_numeric(pd.Series([existing.get((s["id"], t["id"])) for s in students], index=table.index), errors="coerce")
    config = {label: st.column_config.NumberColumn(label, min_value=0.0, max_value=float(t["max_marks"]), step=0.5)
              for label, t in columns.items()}
    edited = st.data_editor(table, column_config=config, disabled=["Student"], key="marks_editor_{}".format(aid))
    if st.button("Save marks"):
        saved = 0
        conn = db.connect()
        for student_id, row in edited.iterrows():
            for label, t in columns.items():
                value = row[label]
                if pd.isna(value):
                    continue
                value = float(value)
                if 0 <= value <= t["max_marks"]:  # reject impossible marks
                    conn.execute("INSERT OR REPLACE INTO scores (student_id, assessment_topic_id, marks) VALUES (?, ?, ?)",
                                 (int(student_id), t["id"], value))
                    saved += 1
        conn.commit()
        conn.close()
        st.success("Saved {} marks. The dashboard now uses the newest test with marks.".format(saved))


# ============================ SYLLABUS ============================

def page_syllabus():
    st.title("Syllabus")
    st.caption("Chapter and section titles from your uploaded textbook (NCERT Accountancy Part I). Test topics are matched to these chapters by name.")
    subjects = [s for s in analytics.subjects(CLASS_ID) if syllabus.chapters(s)] or ["Accountancy"]
    for subject in subjects:
        st.subheader(subject)
        for row in syllabus.chapter_status(CLASS_ID, subject):
            ch, res = row["chapter"], row["result"]
            if res:
                status = "{:.0f}% in {} ({} of {} below 50%)".format(res["average"], res["test"], res["below_50"], res["entered"])
            else:
                status = "not tested yet"
            with st.expander("Ch {}. {}  |  {}".format(ch["chapter"], ch["title"], status)):
                st.caption("{} sections, {} pages in the PDF".format(len(ch["sections"]), ch["pdf_pages"]))
                for s in ch["sections"]:
                    if s["level"] == 2:
                        st.text("      " + s["no"] + " " + s["title"])
                    else:
                        st.markdown("**" + s["no"] + " " + s["title"] + "**")


# ============================ MENU ============================

st.sidebar.title("Teacher Class Brain")
page = st.sidebar.radio("Go to", ["Dashboard", "Students", "Tests", "Enter marks", "Syllabus"])
use_ai = False
if llm.available():
    use_ai = st.sidebar.checkbox("Use AI for answers", value=False,
                                 help="Sends only calculated numbers to the AI, with student names replaced by codes.")
else:
    st.sidebar.caption("AI is off (no API key set). Answers use calculated rules.")
st.sidebar.caption("The demo uses FAKE students only.")

if page == "Dashboard":
    page_dashboard(use_ai)
elif page == "Students":
    page_students()
elif page == "Tests":
    page_tests()
elif page == "Enter marks":
    page_marks()
else:
    page_syllabus()
