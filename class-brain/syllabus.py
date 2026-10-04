"""PART 5 - SYLLABUS / TEXTBOOK KNOWLEDGE. Reads syllabus.json (chapter and section TITLES taken from the
NCERT Accountancy Part I PDFs). Used to connect a weak topic to its textbook chapter and sections."""
import json
import os
import re
import difflib

import analytics

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "syllabus.json")


def _load():
    try:
        with open(PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def chapters(subject):
    data = _load()
    return data["chapters"] if data and data.get("subject") == subject else []


def _norm(text):
    t = re.sub(r"[-_/,]", " ", text.lower())
    t = re.sub(r"\bii\b", "2", t)  # "Transactions-II" and "Transactions 2" should match; I vs II must stay different
    t = re.sub(r"\bi\b", "1", t)
    return re.sub(r"[^a-z0-9]", "", t)


def match_chapter(subject, topic):
    """Returns the textbook chapter (dict) that a test topic refers to, or None. Exact match first, then a close match."""
    chs = chapters(subject)
    want = _norm(topic)
    for ch in chs:
        if _norm(ch["title"]) == want:
            return ch
    close = difflib.get_close_matches(want, [_norm(c["title"]) for c in chs], n=1, cutoff=0.85)
    if close:
        ch = next(c for c in chs if _norm(c["title"]) == close[0])
        if re.findall(r"\d+$", want) == re.findall(r"\d+$", close[0]):  # never confuse part 1 with part 2
            return ch
    if len(want) >= 8:  # a short name that starts exactly ONE chapter title, e.g. "Depreciation"
        starts = [c for c in chs if _norm(c["title"]).startswith(want)]
        if len(starts) == 1:
            return starts[0]
    return None


def main_sections(ch):
    return [s["no"] + " " + s["title"] for s in ch["sections"] if s["level"] == 1]


def hint(subject, topic):
    """One short sentence connecting a topic to its textbook chapter (or None)."""
    ch = match_chapter(subject, topic)
    if not ch:
        return None
    return (f'{topic} matches Chapter {ch["chapter"]} of your textbook ({ch["pdf_pages"]} pages). '
            "Main sections: " + "; ".join(main_sections(ch)) + ".")


def compact(subject):
    """Small version of the syllabus for the AI: chapter numbers, titles and main section titles only."""
    return [{"chapter": c["chapter"], "title": c["title"], "main_sections": main_sections(c)} for c in chapters(subject)]


def chapter_status(class_id, subject):
    """For each chapter: how the class did the most recent time it was tested (None if never tested)."""
    rows = []
    tests = list(reversed(analytics.scored_assessments(class_id, subject)))  # newest first
    results = []
    for a in tests:
        f = analytics.analyze_class(class_id, assessment_id=a["id"])
        if f:
            results.append((a["name"], f["topics"]))
    for ch in chapters(subject):
        found = None
        for test_name, topics in results:
            for t in topics:
                m = match_chapter(subject, t["topic"])
                if m and m["chapter"] == ch["chapter"]:
                    found = {"test": test_name, "average": t["average"], "below_50": t["below_50"], "entered": t["entered"]}
                    break
            if found:
                break
        rows.append({"chapter": ch, "result": found})
    return rows
