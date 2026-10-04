"""LOCAL VERSION of the web app (Python's built-in web server, no installs needed).
Run:  python app_local.py   then open  http://localhost:8000
The Streamlit version (for GitHub / Streamlit Cloud) is app.py."""
import html
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import analytics
import brain
import db
import syllabus

CLASS_ID = 1  # the MVP has one class; multiple classes come later

CSS = """body{font-family:system-ui,sans-serif;max-width:940px;margin:24px auto;padding:0 16px;color:#222}
.card{border:1px solid #ddd;border-radius:10px;padding:16px;margin:14px 0}
.good{color:#1a7f37}.warn{color:#b35900}h1{margin-bottom:0}nav a{margin-right:14px}
.tabs{margin:14px 0}.tab{display:inline-block;padding:6px 12px;border:1px solid #ccc;border-radius:16px;margin:0 6px 6px 0;text-decoration:none;color:#333}
.tab.on{background:#222;color:#fff;border-color:#222}
input[type=text]{width:70%;padding:8px}input[type=number]{width:60px}button{padding:8px 14px}
table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:4px 8px;font-size:14px}
.bar{background:#eee;border-radius:4px;height:10px;width:160px;display:inline-block}
.bar i{display:block;height:10px;border-radius:4px}"""


def e(x):
    return html.escape(str(x))


def page(body):
    nav = '<nav><a href="/">Dashboard</a><a href="/students">Students</a><a href="/tests">Tests</a><a href="/marks">Enter marks</a><a href="/syllabus">Syllabus</a></nav>'
    return "<!doctype html><meta charset=utf-8><title>Teacher Class Brain</title><style>" + CSS + "</style>" + nav + body


def class_name():
    conn = db.connect()
    row = conn.execute("SELECT name FROM classes WHERE id=?", (CLASS_ID,)).fetchone()
    conn.close()
    return row["name"] if row else "Class"


def subject_link(subject):
    return "/?s=" + urllib.parse.quote(subject)


def tabs(current):
    items = [("All subjects", None)] + [(s, s) for s in analytics.subjects(CLASS_ID)]
    out = ""
    for label, value in items:
        href = "/" if value is None else subject_link(value)
        css = "tab on" if value == current else "tab"
        out += '<a class="' + css + '" href="' + href + '">' + e(label) + "</a>"
    return '<div class="tabs">' + out + "</div>"


def ask_card(question, subject):
    hidden = '<input type=hidden name=s value="' + e(subject or "") + '">'
    hint = "Ask about " + (subject if subject else "any subject") + ", e.g. Why did my class perform poorly?"
    return ('<div class=card><b>Ask Class Brain</b><form method=post action=/ask style="margin-top:8px">' + hidden +
            '<input type=text name=q placeholder="' + e(hint) + '" value="' + e(question) + '"> <button>Ask</button></form></div>')


def answer_card(answer, question):
    if not answer:
        return ""

    def section(title, items):
        return ("<h4>" + title + "</h4>" + "".join("<p>" + e(i) + "</p>" for i in items)) if items else ""
    source = e(answer.get("source", ""))
    return ("<div class=card><b>You asked:</b> " + e(question) + " <small>(answered by: " + source + ")</small>" +
            section("Known data", answer["data"]) + section("Analysis", answer["analysis"]) +
            section("Suggestion", answer["suggestion"]) + "</div>")


def overview_view():
    o = analytics.class_overview(CLASS_ID)
    if not o["subjects"]:
        return "<p>No marks yet. Go to Tests, pick a test, and enter marks.</p>"
    rows = ""
    for r in o["subjects"]:
        if r["change"] is None:
            change = "-"
        else:
            change = "{:+.0f}".format(r["change"])
        w = r["weakest"]
        rows += ("<tr><td><a href=\"" + subject_link(r["subject"]) + "\">" + e(r["subject"]) + "</a></td><td>" + e(r["assessment_name"]) +
                 "</td><td>{:.0f}%</td><td>".format(r["average"]) + e(w["topic"]) + " ({:.0f}%)</td><td>".format(w["average"]) +
                 change + "</td></tr>")
    flagged = "".join("<tr><td>" + e(d["name"]) + "</td><td>{:.0f}%</td><td>".format(d["average"]) + e(", ".join(d["below_50"])) + "</td></tr>"
                      for d in o["flagged"]) or "<tr><td colspan=3>No student is below 50% in two or more subjects.</td></tr>"
    return ('<div class=card><b>Subjects at a glance</b> (most recent test in each)<table><tr><th>Subject</th><th>Test</th><th>Average</th>'
            "<th>Lowest topic</th><th>Change since last test*</th></tr>" + rows + "</table>"
            "<small>*On topics both tests covered. Click a subject for details.</small></div>"
            '<div class=card><b>Students below 50% in two or more subjects</b> (a starting point, not a verdict)'
            "<table><tr><th>Name</th><th>Average across subjects</th><th>Below 50% in</th></tr>" + flagged + "</table></div>")


def chapter_cell(subject, topic):
    ch = syllabus.match_chapter(subject, topic)
    return "Textbook Ch {}".format(ch["chapter"]) if ch else "-"


def subject_view(subject):
    f = analytics.analyze_class(CLASS_ID, subject=subject)
    if not f:
        return "<p>No marks yet for " + e(subject) + ".</p>"
    rows = ""
    for t in f["topics"]:
        if t["average"] >= analytics.STRONG:
            colour = "#1a7f37"
        elif t["average"] < analytics.ATTENTION:
            colour = "#b35900"
        else:
            colour = "#888"
        rows += ("<tr><td>" + e(t["topic"]) + "</td><td>{:.0f}%</td>".format(t["average"]) +
                 '<td><span class=bar><i style="width:{:.0f}%;background:{}"></i></span></td>'.format(t["average"], colour) +
                 "<td>{} below 50%</td><td>".format(t["below_50"]) + chapter_cell(subject, t["topic"]) + "</td></tr>")
    strong = "".join('<div class=good>&#10003; ' + e(t["topic"]) + "</div>" for t in f["strong"]) or "<div>None above 70%</div>"
    attn = "".join('<div class=warn>&#9888; ' + e(t["topic"]) + "</div>" for t in f["attention"]) or "<div>None below 55%</div>"
    plan = "".join("<div>{} min &mdash; ".format(m) + e(s) + "</div>" for m, s in analytics.revision_plan(f))
    flagged = "".join("<tr><td>" + e(s["name"]) + "</td><td>{:.0f}%</td><td>".format(s["percent"]) + e(s["weakest_topic"]) + "</td></tr>"
                      for s in f["students_flagged"])
    change = ""
    c = analytics.compare_latest(CLASS_ID, subject)
    if c and c["shared_topics"] and c["prev_avg"] is not None:
        lines = ""
        for t in c["topics"]:
            css = "good" if t["change"] >= 5 else ("warn" if t["change"] <= -5 else "")
            lines += ('<div class="' + css + '">' + e(t["topic"]) + ": {:.0f}% &rarr; {:.0f}% ({:+.0f})</div>".format(t["prev"], t["cur"], t["change"]))
        change = ("<div class=card><b>Since last test</b> (" + e(c["prev_name"]) + " &rarr; " + e(c["cur_name"]) + ", shared topics only)" +
                  "<div>Class average: {:.0f}% &rarr; {:.0f}% ({:+.0f})</div>".format(c["prev_avg"], c["cur_avg"], c["cur_avg"] - c["prev_avg"]) +
                  lines + "</div>")
    return ("<p>" + e(f["assessment"]) + " &middot; Students: {} &middot; Average: <b>{:.0f}%</b></p>".format(f["student_count"], f["class_average"]) +
            "<div class=card><b>Strong areas</b>" + strong + "<br><b>Needs attention</b>" + attn +
            "<br><b>Suggested action</b> (a suggestion, not a rule)" + plan + "</div>" + change +
            '<div class=card><b>Topic performance</b><table>' + rows + "</table></div>"
            '<div class=card><b>Students below 50% in this test</b> (one test only: use your own judgement)'
            "<table><tr><th>Name</th><th>Overall</th><th>Lowest topic</th></tr>" + flagged + "</table></div>")


def dashboard(answer=None, question="", subject=None):
    available = analytics.subjects(CLASS_ID)
    if subject not in available:
        subject = available[0] if len(available) == 1 else None
    title = e(class_name().upper()) + (" &middot; " + e(subject) if subject else "")
    body = subject_view(subject) if subject else overview_view()
    return page("<h1>" + title + "</h1>" + (tabs(subject) if len(available) > 1 else "") + ask_card(question, subject) + answer_card(answer, question) + body)


def syllabus_page():
    subjects = [s for s in analytics.subjects(CLASS_ID) if syllabus.chapters(s)] or ["Accountancy"]
    body = ""
    for subj in subjects:
        rows = ""
        for r in syllabus.chapter_status(CLASS_ID, subj):
            ch, res = r["chapter"], r["result"]
            if res:
                status = "{:.0f}% in {} ({} of {} below 50%)".format(res["average"], e(res["test"]), res["below_50"], res["entered"])
            else:
                status = "not tested yet"
            sections = ""
            for s in ch["sections"]:
                pad = "20px" if s["level"] == 2 else "0"
                weight = "normal" if s["level"] == 2 else "bold"
                sections += '<div style="margin-left:{};font-weight:{}">{} {}</div>'.format(pad, weight, e(s["no"]), e(s["title"]))
            rows += ("<tr><td>{}</td><td>".format(ch["chapter"]) + e(ch["title"]) + "<details><summary>{} sections, {} pages</summary>".format(len(ch["sections"]), ch["pdf_pages"]) +
                     sections + "</details></td><td>" + status + "</td></tr>")
        body += ("<h3>" + e(subj) + "</h3><table><tr><th>Ch.</th><th>Chapter</th><th>Latest class result</th></tr>" + rows + "</table>")
    return page("<h1>Syllabus</h1><p>Chapter and section titles from your uploaded textbook (NCERT Accountancy Part I). "
                "Topics in tests are matched to these chapters by name.</p>" + body)


def students_page(msg=""):
    conn = db.connect()
    rows = conn.execute("SELECT name FROM students WHERE class_id=? ORDER BY id", (CLASS_ID,)).fetchall()
    conn.close()
    lis = "".join("<li>" + e(r["name"]) + "</li>" for r in rows)
    return page("<h1>Students</h1><p>" + e(msg) + "</p>"
                '<form method=post action=/students/add><input type=text name=name placeholder="Student name (use fake names while testing)"> <button>Add</button></form>'
                "<p>{} students</p><ul>".format(len(rows)) + lis + "</ul>")


def tests_page(msg=""):
    tests = analytics.list_assessments(CLASS_ID)
    rows = "".join("<tr><td>" + e(a["subject"]) + "</td><td>" + e(a["name"]) + '</td><td><a href="/marks?a={}">Enter / edit marks</a></td></tr>'.format(a["id"])
                   for a in tests)
    present = analytics.subjects(CLASS_ID)
    options = "".join("<option>" + e(s) + "</option>" for s in present + [x for x in analytics.SUBJECT_ORDER if x not in present])
    chapter_block = ""
    if syllabus.chapters("Accountancy"):
        crow = "".join('<tr><td><input type=checkbox name="ch_{0}"></td><td>Ch {0}. {1}</td><td><input type=number step=any min=1 name="mx_{0}" value=10></td></tr>'.format(
            c["chapter"], e(c["title"])) for c in syllabus.chapters("Accountancy"))
        chapter_block = ("<p><b>Accountancy chapters</b>: tick the chapters in this test and set the maximum marks for each</p>"
                         "<table><tr><th></th><th>Chapter</th><th>Max marks</th></tr>" + crow + "</table>"
                         "<p><small>Used when the subject is Accountancy. Picking chapters here keeps topic names identical across tests.</small></p>")
    return page("<h1>Tests</h1><p>" + e(msg) + "</p><table><tr><th>Subject</th><th>Test</th><th></th></tr>" + rows + "</table>"
                "<div class=card><b>Create a new test</b><form method=post action=/tests/add>"
                "<p>Subject: <select name=subject>" + options + '</select> Test name: <input type=text name=name placeholder="Unit Test 3" style="width:200px"></p>'
                + chapter_block +
                "<p>Other topics (optional), one per line, like <code>Project work, 10</code><br>"
                '<textarea name=topics rows=6 cols=44 placeholder="Project work, 10"></textarea></p>'
                "<button>Create test</button></form>"
                "<p><small>Tip: use the exact same topic names as earlier tests of the same subject so the Class Brain can compare them. "
                "Use the topic names from your school's own syllabus.</small></p></div>")


def marks_page(msg="", aid=None):
    conn = db.connect()
    tests = analytics.list_assessments(CLASS_ID)
    a = next((x for x in tests if x["id"] == aid), None) or analytics.latest_assessment(CLASS_ID)
    topics = conn.execute("SELECT * FROM assessment_topics WHERE assessment_id=?", (a["id"],)).fetchall()
    students = conn.execute("SELECT * FROM students WHERE class_id=? ORDER BY id", (CLASS_ID,)).fetchall()
    existing = {}
    for r in conn.execute("SELECT s.* FROM scores s JOIN assessment_topics t ON s.assessment_topic_id=t.id WHERE t.assessment_id=?", (a["id"],)):
        existing[(r["student_id"], r["assessment_topic_id"])] = r["marks"]
    conn.close()
    head = "".join("<th>" + e(t["topic"]) + "<br>/{:g}</th>".format(t["max_marks"]) for t in topics)
    body = ""
    for s in students:
        cells = ""
        for t in topics:
            key = (s["id"], t["id"])
            value = "{:g}".format(existing[key]) if key in existing else ""
            cells += '<td><input type=number step=any min=0 max={:g} name="m_{}_{}" value="{}"></td>'.format(t["max_marks"], s["id"], t["id"], value)
        body += "<tr><td>" + e(s["name"]) + "</td>" + cells + "</tr>"
    picker = "".join('<a class="tab{}" href="/marks?a={}">{}</a>'.format(" on" if x["id"] == a["id"] else "", x["id"], e(x["subject"] + " - " + x["name"])) for x in tests)
    return page("<h1>Enter marks</h1><p>" + e(msg) + "</p><div class=tabs>" + picker + "</div>"
                '<form method=post action=/marks/save><input type=hidden name=a value="{}">'.format(a["id"]) +
                "<table><tr><th>Student</th>" + head + "</tr>" + body + "</table><br><button>Save marks</button></form>")


class Handler(BaseHTTPRequestHandler):
    def send(self, content, status=200):
        data = content.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, where):
        self.send_response(303)
        self.send_header("Location", where)
        self.end_headers()

    def form(self):
        n = int(self.headers.get("Content-Length", 0))
        return {k: v[0] for k, v in urllib.parse.parse_qs(self.rfile.read(n).decode()).items()}

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(url.query)
        if url.path == "/":
            self.send(dashboard(subject=query.get("s", [""])[0] or None))
        elif url.path == "/students":
            self.send(students_page())
        elif url.path == "/tests":
            self.send(tests_page())
        elif url.path == "/syllabus":
            self.send(syllabus_page())
        elif url.path == "/marks":
            try:
                aid = int(query.get("a", [""])[0])
            except ValueError:
                aid = None
            self.send(marks_page(aid=aid))
        else:
            self.send(page("<h1>Not found</h1>"), 404)

    def do_POST(self):
        data = self.form()
        if self.path == "/ask":
            q = data.get("q", "").strip()[:500]
            subject = data.get("s") or None
            self.send(dashboard(brain.ask(CLASS_ID, q, subject), q, subject) if q else dashboard(subject=subject))
        elif self.path == "/students/add":
            name = data.get("name", "").strip()[:80]
            if name:
                conn = db.connect()
                conn.execute("INSERT INTO students (class_id, name) VALUES (?, ?)", (CLASS_ID, name))
                conn.commit()
                conn.close()
            self.redirect("/students")
        elif self.path == "/tests/add":
            subject, name = data.get("subject", "").strip()[:60], data.get("name", "").strip()[:60]
            parsed = []
            for line in data.get("topics", "").splitlines():
                if not line.strip():
                    continue
                topic, _, mx = line.rpartition(",")
                try:
                    mx = float(mx)
                except ValueError:
                    mx = 0
                if topic.strip() and mx > 0:
                    parsed.append((topic.strip()[:80], mx))
            if subject == "Accountancy":
                by_no = {c["chapter"]: c for c in syllabus.chapters("Accountancy")}
                ticked = sorted(int(k[3:]) for k in data if k.startswith("ch_") and k[3:].isdigit())
                chosen = []
                for n in ticked:
                    try:
                        mx = float(data.get("mx_" + str(n), "0"))
                    except ValueError:
                        mx = 0
                    if n in by_no and mx > 0:
                        chosen.append((by_no[n]["title"], mx))
                parsed = chosen + [p for p in parsed if p[0] not in [c[0] for c in chosen]]
            if not (subject and name and parsed):
                self.send(tests_page("Please give a subject, a test name, and at least one chapter or topic with maximum marks."))
                return
            conn = db.connect()
            cur = conn.execute("INSERT INTO assessments (class_id, subject, name) VALUES (?, ?, ?)", (CLASS_ID, subject, name))
            for topic, mx in parsed:
                conn.execute("INSERT INTO assessment_topics (assessment_id, topic, max_marks) VALUES (?, ?, ?)", (cur.lastrowid, topic, mx))
            conn.commit()
            conn.close()
            self.redirect("/marks?a={}".format(cur.lastrowid))
        elif self.path == "/marks/save":
            try:
                aid = int(data.get("a", ""))
            except ValueError:
                aid = None
            a = next((x for x in analytics.list_assessments(CLASS_ID) if x["id"] == aid), None) or analytics.latest_assessment(CLASS_ID)
            conn = db.connect()
            maxes = {r["id"]: r["max_marks"] for r in conn.execute(
                "SELECT id, max_marks FROM assessment_topics WHERE assessment_id=?", (a["id"],))}
            for key, val in data.items():
                if not key.startswith("m_") or val.strip() == "":
                    continue
                try:
                    _, sid, tid = key.split("_")
                    marks = float(val)
                    sid, tid = int(sid), int(tid)
                except ValueError:
                    continue
                if tid in maxes and 0 <= marks <= maxes[tid]:  # reject impossible marks
                    conn.execute("INSERT OR REPLACE INTO scores (student_id, assessment_topic_id, marks) VALUES (?,?,?)", (sid, tid, marks))
            conn.commit()
            conn.close()
            self.redirect(subject_link(a["subject"]))
        else:
            self.send(page("<h1>Not found</h1>"), 404)

    def log_message(self, *args):
        pass  # keep the terminal quiet


if __name__ == "__main__":
    db.init_db()
    db.seed_demo()
    print("Teacher Class Brain running. Open http://localhost:8000 in your browser. Press Ctrl+C to stop.")
    HTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
