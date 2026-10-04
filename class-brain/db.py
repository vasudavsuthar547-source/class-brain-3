"""PART 1 - DATA. Creates the database tables and fills them with FAKE demo data."""
import os
import random
import sqlite3
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
if not os.access(_HERE, os.W_OK):  # read-only folder (some hosting): use a temporary folder instead
    _HERE = tempfile.gettempdir()
DB_PATH = os.environ.get("CLASSBRAIN_DB", os.path.join(_HERE, "classbrain.db"))


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us read columns by name
    return conn


def init_db():
    conn = connect()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY, name TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL, name TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS assessments (
        id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL, subject TEXT NOT NULL, name TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS assessment_topics (
        id INTEGER PRIMARY KEY, assessment_id INTEGER NOT NULL, topic TEXT NOT NULL, max_marks REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS scores (
        student_id INTEGER NOT NULL, assessment_topic_id INTEGER NOT NULL, marks REAL NOT NULL,
        PRIMARY KEY (student_id, assessment_topic_id));
    """)
    conn.commit()
    conn.close()


def seed_demo():
    """Only runs if the database is empty. All student names and marks are made up.
    Test topics are the real chapter names from the NCERT Accountancy Part I textbook (see syllabus.json)."""
    conn = connect()
    if conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0] > 0:
        conn.close()
        return
    rnd = random.Random(2024)  # fixed seed = same fake data every time
    conn.execute("INSERT INTO classes (id, name) VALUES (1, 'Class 11 Commerce')")
    first = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Isha", "Arjun", "Anaya", "Vihaan", "Saanvi",
             "Aditya", "Kiara", "Reyansh", "Myra", "Ishaan", "Tara", "Dhruv", "Navya", "Krish", "Riya"]
    last = ["Sharma", "Iyer", "Nair", "Patel", "Reddy", "Khan"]
    for i in range(30):
        conn.execute("INSERT INTO students (id, class_id, name) VALUES (?, 1, ?)",
                     (i + 1, f"{first[i % 20]} {last[(i * 7 + i // 20) % 6]}"))
    base = {sid: rnd.uniform(-0.15, 0.15) for sid in range(1, 31)}  # a student's general level
    # (chapter name, max marks, typical % the fake class scores)
    tests = [
        ("Unit Test 1", [("Introduction to Accounting", 8, .82), ("Theory Base of Accounting", 8, .70),
                         ("Recording of Transactions-I", 12, .58), ("Recording of Transactions-II", 12, .50)]),
        ("Unit Test 2", [("Recording of Transactions-I", 12, .64), ("Recording of Transactions-II", 12, .56),
                         ("Bank Reconciliation Statement", 8, .38), ("Trial Balance and Rectification of Errors", 8, .42)]),
    ]
    for test_name, topics in tests:
        a_id = conn.execute("INSERT INTO assessments (class_id, subject, name) VALUES (1, 'Accountancy', ?)",
                            (test_name,)).lastrowid
        for topic, mx, typical in topics:
            t_id = conn.execute("INSERT INTO assessment_topics (assessment_id, topic, max_marks) VALUES (?, ?, ?)",
                                (a_id, topic, mx)).lastrowid
            for sid in range(1, 31):
                pct = min(1.0, max(0.0, typical + base[sid] + rnd.uniform(-0.14, 0.14)))
                conn.execute("INSERT INTO scores (student_id, assessment_topic_id, marks) VALUES (?, ?, ?)",
                             (sid, t_id, round(pct * mx)))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    seed_demo()
    print("Database ready:", DB_PATH)
