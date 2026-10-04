"""PART 4 - THE AI LAYER.
The AI never touches the database. It is handed ONLY the facts that analytics.py already calculated,
with student names replaced by codes (S01, S02...). We swap the real names back in afterwards.
Needs an API key in the environment variable ANTHROPIC_API_KEY (never type a key into the code)."""
import json
import os
import re
import urllib.request

import analytics
import syllabus

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("CLASSBRAIN_MODEL", "claude-sonnet-5-5")

SYSTEM = """You are the analysis engine inside "Teacher Class Brain", a tool that helps a school teacher understand a class.
You are given FACTS as JSON. Follow these rules strictly:
1. Use ONLY numbers and names found in the FACTS. Never invent marks, students, topics or trends. The class has several subjects (such as English, Accountancy, Business Studies, Economics); never mix up their numbers.
2. If the FACTS cannot answer the question, say exactly: "I don't have enough data to determine that."
3. Keep three things separate: "data" (facts copied from the FACTS), "analysis" (your interpretation, using words like
   'appears' or 'may'), and "suggestion" (ideas for the teacher, phrased as options, not orders).
4. Never label a student negatively (no 'weak student', 'lazy'). Describe scores instead, e.g. 'scored 38% on Elasticity'.
5. One test is limited evidence; say so when relevant. Never claim to know WHY scores changed.
6. Refer to students only by their codes (S01...). Be concise.
7. If "textbook_chapters" is present you may point the teacher to those chapters and section titles when suggesting what to revise. Use only chapter numbers and section titles that appear there; never invent page numbers or textbook content.
Reply with ONLY a JSON object, no other text:
{"data": ["..."], "analysis": ["..."], "suggestion": ["..."]}"""


def available():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def build_facts(class_id):
    """Returns (facts_for_ai, code_to_name). Names are replaced by codes before anything leaves this computer.
    Codes use the student's id, so two students with the same name still get different codes."""
    overview = analytics.class_overview(class_id)
    if not overview["subjects"]:
        return None, {}
    code, code_to_name = {}, {}
    for d in overview["students"]:
        code[d["id"]] = f"S{d['id']:02d}"
        code_to_name[code[d["id"]]] = d["name"]
    subjects = {}
    for r in overview["subjects"]:
        f = analytics.analyze_class(class_id, subject=r["subject"])
        entry = {
            "test": f["assessment_name"], "students_with_marks": f["students_with_marks"],
            "class_average_percent": round(f["class_average"], 1),
            "topics_weakest_first": [{"topic": t["topic"], "average_percent": round(t["average"], 1),
                                      "students_below_50": t["below_50"], "students_counted": t["entered"]} for t in f["topics"]],
            "students": [{"code": code[s["id"]], "overall_percent": round(s["percent"], 1),
                          "topic_percent": {k: round(v[0] / v[1] * 100) for k, v in s["by_topic"].items()}}
                         for s in f["students"]],
        }
        book = syllabus.compact(r["subject"])
        if book:
            entry["textbook_chapters"] = book
        c = analytics.compare_latest(class_id, r["subject"])
        if c and c["shared_topics"]:
            entry["comparison_with_previous_test"] = {
                "previous_test": c["prev_name"], "compared_on_shared_topics_only": c["shared_topics"],
                "class_average_then": round(c["prev_avg"], 1), "class_average_now": round(c["cur_avg"], 1),
                "topic_changes": [{"topic": t["topic"], "then": round(t["prev"]), "now": round(t["cur"]), "change": round(t["change"])}
                                  for t in c["topics"]],
                "students_up_10plus": [code[m["id"]] for m in c["up"]],
                "students_down_10plus": [code[m["id"]] for m in c["down"]],
            }
        subjects[r["subject"]] = entry
    facts = {
        "class": analytics.analyze_class(class_id)["class_name"],
        "students_total": analytics.analyze_class(class_id)["student_count"],
        "note": "Each subject's figures come from its most recent test with marks. Subjects are never compared with each other's tests.",
        "subjects": subjects,
        "students_across_subjects": [{"code": code[d["id"]], "average_percent": round(d["average"], 1),
                                      "subject_percent": {k: round(v) for k, v in d["subjects"].items()},
                                      "below_50_in": d["below_50"]} for d in overview["students"]],
    }
    return facts, code_to_name


def call_api(system, user_text):
    """Sends one request to the API and returns the reply text. Separate function so tests can replace it."""
    body = json.dumps({"model": MODEL, "max_tokens": 1000, "system": system,
                       "messages": [{"role": "user", "content": user_text}]}).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "content-type": "application/json", "x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=40) as resp:
        data = json.load(resp)
    return "".join(b.get("text", "") for b in data["content"])


def _restore_names(text, code_to_name):
    return re.sub(r"\bS\d{2,4}\b", lambda m: code_to_name.get(m.group(0), m.group(0)), text)


def ask(class_id, question, subject=None):
    """Returns {'data','analysis','suggestion'} lists, or raises an exception if anything goes wrong
    (the caller then falls back to the rule-based answer)."""
    facts, code_to_name = build_facts(class_id)
    if facts is None:
        raise ValueError("no data")
    viewing = f"The teacher is currently viewing the {subject} tab.\n" if subject else "The teacher is viewing the all-subjects overview.\n"
    prompt = f"FACTS:\n{json.dumps(facts)}\n\n{viewing}TEACHER'S QUESTION: {question[:500]}"
    raw = call_api(SYSTEM, prompt).strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    parsed = json.loads(raw)
    out = {}
    for key in ("data", "analysis", "suggestion"):
        items = parsed.get(key, [])
        if not isinstance(items, list):
            raise ValueError("bad format")
        out[key] = [_restore_names(str(i), code_to_name) for i in items]
    if not any(out.values()):
        raise ValueError("empty answer")
    return out
