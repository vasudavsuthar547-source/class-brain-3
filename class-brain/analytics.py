"""PART 2 - ANALYTICS. All the maths lives here. No AI, no guessing: just calculations on stored marks."""
from db import connect

STRONG = 70   # topic average at or above this = strong area
ATTENTION = 55  # topic average below this = needs attention
STUDENT_FLAG = 50  # students scoring below this overall are listed for follow-up


def latest_assessment(class_id):
    """Newest test, even if no marks are entered yet."""
    conn = connect()
    row = conn.execute("SELECT * FROM assessments WHERE class_id=? ORDER BY id DESC LIMIT 1", (class_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_assessments(class_id):
    conn = connect()
    rows = conn.execute("SELECT * FROM assessments WHERE class_id=? ORDER BY id", (class_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


SUBJECT_ORDER = ["English", "Accountancy", "Business Studies", "Economics"]


def subjects(class_id):
    """Subjects that have at least one test, in a friendly order."""
    found = {a["subject"] for a in list_assessments(class_id)}
    return sorted(found, key=lambda x: (SUBJECT_ORDER.index(x) if x in SUBJECT_ORDER else 99, x))


def scored_assessments(class_id, subject=None):
    """Tests (optionally of one subject) that have at least one mark entered, oldest first."""
    sql = """SELECT a.* FROM assessments a WHERE a.class_id=? AND EXISTS (
        SELECT 1 FROM assessment_topics t JOIN scores s ON s.assessment_topic_id=t.id WHERE t.assessment_id=a.id)"""
    params = [class_id]
    if subject:
        sql += " AND a.subject=?"
        params.append(subject)
    conn = connect()
    rows = conn.execute(sql + " ORDER BY a.id", params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def analyze_class(class_id, assessment_id=None, subject=None):
    """Returns a dictionary of facts about one test (default: newest test that has marks), or None."""
    conn = connect()
    cls = conn.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone()
    if assessment_id is None:
        done = scored_assessments(class_id, subject)
        assessment = done[-1] if done else None
    else:
        row = conn.execute("SELECT * FROM assessments WHERE id=? AND class_id=?", (assessment_id, class_id)).fetchone()
        assessment = dict(row) if row else None
    if not cls or not assessment:
        conn.close()
        return None
    topics = conn.execute("SELECT * FROM assessment_topics WHERE assessment_id=?", (assessment["id"],)).fetchall()
    students = conn.execute("SELECT * FROM students WHERE class_id=?", (class_id,)).fetchall()
    scores = {(r["student_id"], r["assessment_topic_id"]): r["marks"]
              for r in conn.execute("""SELECT s.* FROM scores s JOIN assessment_topics t
                                       ON s.assessment_topic_id=t.id WHERE t.assessment_id=?""", (assessment["id"],))}
    conn.close()

    topic_stats = []
    for t in topics:
        pcts = [scores[(s["id"], t["id"])] / t["max_marks"] * 100
                for s in students if (s["id"], t["id"]) in scores]
        if not pcts:
            continue
        topic_stats.append({
            "topic": t["topic"], "average": sum(pcts) / len(pcts), "entered": len(pcts),
            "below_50": sum(1 for p in pcts if p < 50)})

    student_stats = []
    for s in students:
        got = [(scores[(s["id"], t["id"])], t["max_marks"], t["topic"]) for t in topics if (s["id"], t["id"]) in scores]
        if not got:
            continue
        total, mx = sum(g[0] for g in got), sum(g[1] for g in got)
        weakest = min(got, key=lambda g: g[0] / g[1])
        student_stats.append({"id": s["id"], "name": s["name"], "percent": total / mx * 100,
                              "weakest_topic": weakest[2], "weakest_percent": weakest[0] / weakest[1] * 100,
                              "by_topic": {g[2]: (g[0], g[1]) for g in got}})

    if not topic_stats or not student_stats:
        return None
    topic_stats.sort(key=lambda x: x["average"])
    student_stats.sort(key=lambda x: x["percent"])
    return {
        "class_name": cls["name"], "subject": assessment["subject"], "assessment_id": assessment["id"], "assessment_name": assessment["name"], "assessment": f'{assessment["subject"]} - {assessment["name"]}',
        "student_count": len(students), "students_with_marks": len(student_stats),
        "class_average": sum(x["percent"] for x in student_stats) / len(student_stats),
        "topics": topic_stats,  # weakest first
        "strong": [t for t in topic_stats if t["average"] >= STRONG],
        "attention": [t for t in topic_stats if t["average"] < ATTENTION],
        "students": student_stats,  # lowest first
        "students_flagged": [s for s in student_stats if s["percent"] < STUDENT_FLAG],
    }


def revision_plan(facts):
    """Turns the weakest topics into a simple 45-minute plan. This is a suggestion, not a rule."""
    weak = facts["attention"] or facts["topics"][:1]
    plan = []
    if weak:
        plan.append((20, f"Re-teach {weak[0]['topic']}"))
    if len(weak) > 1:
        plan.append((15, f"Worked examples for {weak[1]['topic']}"))
    plan.append((10, "Individual practice questions on the weak topics"))
    return plan


CHANGE_FLAG = 10  # a student is listed as up/down only if their overall % moved by at least this many points


def compare_latest(class_id, subject=None):
    """Compares the newest scored test with the one before it, using ONLY topics both tests covered
    (otherwise a test with easier topics would look like 'improvement')."""
    done = scored_assessments(class_id, subject)
    if len(done) < 2:
        return None
    prev, cur = analyze_class(class_id, done[-2]["id"]), analyze_class(class_id, done[-1]["id"])
    if not prev or not cur:
        return None
    prev_t = {t["topic"]: t["average"] for t in prev["topics"]}
    cur_t = {t["topic"]: t["average"] for t in cur["topics"]}
    shared = [n for n in cur_t if n in prev_t]
    topics = sorted([{"topic": n, "prev": prev_t[n], "cur": cur_t[n], "change": cur_t[n] - prev_t[n]} for n in shared],
                    key=lambda x: x["change"])

    def shared_pct(student):  # a student's % using only the shared topics
        got = [v for k, v in student["by_topic"].items() if k in shared]
        return sum(g[0] for g in got) / sum(g[1] for g in got) * 100 if got else None

    prev_s = {s["id"]: shared_pct(s) for s in prev["students"]}
    moves = []
    for s in cur["students"]:
        now, before = shared_pct(s), prev_s.get(s["id"])
        if now is not None and before is not None:
            moves.append({"id": s["id"], "name": s["name"], "prev": before, "cur": now, "change": now - before})
    return {
        "prev_name": prev["assessment"], "cur_name": cur["assessment"],
        "prev_overall": prev["class_average"], "cur_overall": cur["class_average"],
        "shared_topics": shared,
        "prev_avg": sum(m["prev"] for m in moves) / len(moves) if moves else None,
        "cur_avg": sum(m["cur"] for m in moves) / len(moves) if moves else None,
        "topics": topics,
        "new_topics": [n for n in cur_t if n not in prev_t],
        "dropped_topics": [n for n in prev_t if n not in cur_t],
        "up": sorted([m for m in moves if m["change"] >= CHANGE_FLAG], key=lambda m: -m["change"]),
        "down": sorted([m for m in moves if m["change"] <= -CHANGE_FLAG], key=lambda m: m["change"]),
        "students_compared": len(moves),
    }


def class_overview(class_id):
    """The big picture across all subjects (each subject's newest test with marks)."""
    rows, per_student = [], {}
    for subj in subjects(class_id):
        f = analyze_class(class_id, subject=subj)
        if not f:
            continue
        c = compare_latest(class_id, subj)
        change = c["cur_avg"] - c["prev_avg"] if c and c["shared_topics"] and c["prev_avg"] is not None else None
        rows.append({"subject": subj, "assessment_name": f["assessment_name"], "average": f["class_average"],
                     "weakest": f["topics"][0], "attention_count": len(f["attention"]), "change": change})
        for s in f["students"]:
            d = per_student.setdefault(s["id"], {"id": s["id"], "name": s["name"], "subjects": {}})
            d["subjects"][subj] = s["percent"]
    students = []
    for d in per_student.values():
        vals = list(d["subjects"].values())
        d["average"] = sum(vals) / len(vals)
        d["below_50"] = [k for k, v in d["subjects"].items() if v < STUDENT_FLAG]
        students.append(d)
    students.sort(key=lambda d: d["average"])
    return {"subjects": rows, "students": students,
            "flagged": [d for d in students if len(d["below_50"]) >= 2]}  # below 50% in two or more subjects
