"""PART 3a - CLASS BRAIN. Turns analytics facts into an answer.
Every answer has three clearly separated parts: KNOWN DATA, ANALYSIS, SUGGESTION.
Right now it uses simple keyword rules (no AI model yet). Later an LLM can write the
wording, but it will still be handed these same facts, so it can't invent marks."""
import re

import analytics
import syllabus

NO_DATA = "I don't have enough data to determine that."

SUBJECT_WORDS = {"English": ["english"], "Accountancy": ["accountancy", "accounts", "accounting"],
                 "Business Studies": ["bst", "business studies", "business"], "Economics": ["economics", "eco"]}


def detect_subject(question, available):
    q = question.lower()
    for subject, words in SUBJECT_WORDS.items():
        if subject in available and any(re.search(r"\b" + re.escape(w) + r"\b", q) for w in words):
            return subject
    return None


def _hints(subject, topics, limit=2):
    """Textbook lines for the first few topics that match a chapter in syllabus.json."""
    out = []
    for t in topics[:limit]:
        h = syllabus.hint(subject, t["topic"])
        if h:
            out.append("From your textbook: " + h)
    return out


def _answer(data, analysis, suggestion):
    return {"data": data, "analysis": analysis, "suggestion": suggestion}


def _subject_answer(class_id, question, subject):
    facts = analytics.analyze_class(class_id, subject=subject)
    if not facts:
        return _answer([NO_DATA + f" No marks have been entered for {subject} yet."], [], [])
    q = question.lower()
    if any(w in q for w in ["change", "improv", "trend", "progress", "compar", "since", "last test", "better", "worse"]):
        return _trend_answer(class_id, subject)
    head = f'{facts["class_name"]}, {facts["assessment"]}, {facts["students_with_marks"]} of {facts["student_count"]} students have marks.'
    weak = facts["attention"]

    if any(w in q for w in ["weak", "struggl", "poor", "why", "worst", "difficult", "bad"]):
        if not weak:
            return _answer([head, f'Class average: {facts["class_average"]:.0f}%.'],
                           ["No topic fell below the 55% attention line."], [])
        data = [head, f'Class average: {facts["class_average"]:.0f}%.']
        for t in weak:
            data.append(f'{t["topic"]}: average {t["average"]:.0f}%, {t["below_50"]} of {t["entered"]} students scored below 50%.')
        data += _hints(subject, weak)
        analysis = [f'Based on this assessment, {weak[0]["topic"]} was the weakest area. '
                    f'Strongest areas were {", ".join(t["topic"] for t in facts["strong"]) or "not clearly identified"}.',
                    "This is one test only, so it shows how the class did on this paper, not a long-term trend."]
        return _answer(data, analysis, [f"{m} min: {s}" for m, s in analytics.revision_plan(facts)])

    if any(w in q for w in ["student", "attention", "practice"]):
        flagged = facts["students_flagged"]
        if not flagged:
            return _answer([head], ["No student scored below 50% overall in this assessment."], [])
        data = [head] + [f'{s["name"]}: {s["percent"]:.0f}% overall; lowest topic was {s["weakest_topic"]} ({s["weakest_percent"]:.0f}%).'
                         for s in flagged]
        return _answer(data,
                       [f'{len(flagged)} students scored below 50% overall. One test is limited evidence, so check against what you see in class.'],
                       ["Consider short targeted practice on each student's lowest topic, then re-check."])

    if any(w in q for w in ["revis", "plan", "tomorrow", "lesson", "next"]):
        plan = analytics.revision_plan(facts)
        return _answer([head] + [f'{t["topic"]}: average {t["average"]:.0f}%.' for t in (weak or facts["topics"][:1])]
                       + _hints(subject, weak or facts["topics"][:1], 1),
                       ["The plan targets the lowest-scoring topics from this assessment."],
                       [f"{m} min: {s}" for m, s in plan])

    if any(w in q for w in ["average", "mean", "overall", "how is", "how did"]):
        return _answer([head, f'Class average: {facts["class_average"]:.0f}%.'], [], [])

    return _answer([NO_DATA + " I can currently answer questions about weak topics, students needing attention, "
                    "revision plans, and the class average."], [], [])


def _trend_answer(class_id, subject=None):
    c = analytics.compare_latest(class_id, subject)
    if not c:
        return _answer([NO_DATA + " I need marks from at least two tests to compare."], [], [])
    if not c["shared_topics"]:
        return _answer([f'{c["prev_name"]} and {c["cur_name"]} have no topics in common, so I cannot compare them fairly.'], [], [])
    data = [f'Comparing {c["prev_name"]} with {c["cur_name"]}, using only the topics both tests covered: {", ".join(c["shared_topics"])}.',
            f'Class average on those topics: {c["prev_avg"]:.0f}% then, {c["cur_avg"]:.0f}% now ({c["cur_avg"] - c["prev_avg"]:+.0f} points).']
    for t in c["topics"]:
        data.append(f'{t["topic"]}: {t["prev"]:.0f}% then, {t["cur"]:.0f}% now ({t["change"]:+.0f} points).')
    if c["new_topics"]:
        data.append("Only in the newer test (not compared): " + ", ".join(c["new_topics"]) + ".")
    if c["dropped_topics"]:
        data.append("Only in the older test (not compared): " + ", ".join(c["dropped_topics"]) + ".")
    if c["new_topics"] or c["dropped_topics"]:
        data.append(f'Overall averages were {c["prev_overall"]:.0f}% then and {c["cur_overall"]:.0f}% now, but the tests covered different topics, '
                    "so the shared-topic figures above are the fairer comparison.")
    data.append(f'On the shared topics, {len(c["up"])} of {c["students_compared"]} students scored 10+ points higher '
                f'and {len(c["down"])} scored 10+ points lower.')
    analysis = ["Two tests are two data points, and different papers can differ in difficulty, so treat this as a signal rather than proof.",
                "The data shows scores moved; it does not show why (for example, whether a revision session caused it)."]
    suggestion = []
    if c["topics"]:
        worst = c["topics"][0]
        if worst["change"] <= -5:
            suggestion.append(f'{worst["topic"]} went down the most ({worst["change"]:+.0f} points). It may be worth a quick check-in.')
        low = [t for t in c["topics"] if t["cur"] < analytics.ATTENTION]
        if low:
            suggestion.append("Still below the 55% attention line: " +
                              ", ".join(f'{t["topic"]} ({t["cur"]:.0f}%)' for t in low) + ".")
    if c["down"]:
        suggestion.append("Students who scored 10+ points lower on the shared topics: " +
                          ", ".join(f'{m["name"]} ({m["change"]:+.0f})' for m in c["down"][:8]) +
                          ". A quick conversation may help you find out what happened.")
    return _answer(data, analysis, suggestion)


def _overview_answer(class_id, question):
    """Questions that name no subject: look across all subjects."""
    o = analytics.class_overview(class_id)
    if not o["subjects"]:
        return _answer([NO_DATA + " No marks have been entered yet."], [], [])
    q = question.lower()
    names = ", ".join(r["subject"] for r in o["subjects"])
    head = f"Looking across {len(o['subjects'])} subjects with marks: {names} (each subject's most recent test)."

    if any(w in q for w in ["change", "improv", "trend", "progress", "compar", "since", "last test", "better", "worse"]):
        data = [head]
        for r in o["subjects"]:
            c = analytics.compare_latest(class_id, r["subject"])
            if c and c["shared_topics"] and c["prev_avg"] is not None:
                best, worst = c["topics"][-1], c["topics"][0]
                data.append(f'{r["subject"]}: {c["prev_avg"]:.0f}% then, {c["cur_avg"]:.0f}% now on shared topics '
                            f'({c["cur_avg"] - c["prev_avg"]:+.0f}). Biggest rise: {best["topic"]} ({best["change"]:+.0f}); '
                            f'lowest movement: {worst["topic"]} ({worst["change"]:+.0f}).')
            else:
                data.append(f'{r["subject"]}: not enough comparable tests yet.')
        return _answer(data, ["Each subject is compared only with its own previous test, on topics both tests covered.",
                              "Scores moved, but the data does not show why."], ["Name a subject to see its full comparison."])

    if any(w in q for w in ["weak", "struggl", "poor", "why", "worst", "difficult", "bad"]):
        data = [head] + [f'{r["subject"]}: average {r["average"]:.0f}%; lowest topic {r["weakest"]["topic"]} '
                         f'({r["weakest"]["average"]:.0f}%, {r["weakest"]["below_50"]} of {r["weakest"]["entered"]} students below 50%).'
                         for r in o["subjects"]]
        lowest = min(o["subjects"], key=lambda r: r["average"])
        return _answer(data, [f'{lowest["subject"]} has the lowest class average in these tests ({lowest["average"]:.0f}%). '
                              "Each figure comes from a single test."],
                       ["Name a subject (for example 'Why is Accountancy low?') for a topic-by-topic breakdown."])

    if any(w in q for w in ["student", "attention", "practice"]):
        flagged = o["flagged"]
        if not flagged:
            return _answer([head], ["No student scored below 50% in two or more subjects."], [])
        data = [head] + [f'{d["name"]}: {d["average"]:.0f}% average across subjects; below 50% in {", ".join(d["below_50"])}.'
                         for d in flagged]
        return _answer(data, [f'{len(flagged)} students scored below 50% in two or more subjects. '
                              "This is based on one recent test per subject, so treat it as a starting point."],
                       ["Consider a quick, supportive check-in, and look at whether the pattern is shared across subjects or specific to one."])

    if any(w in q for w in ["revis", "plan", "tomorrow", "lesson", "next"]):
        lowest = min(o["subjects"], key=lambda r: r["average"])
        sub = _subject_answer(class_id, "revision plan", lowest["subject"])
        sub["analysis"].insert(0, f'No subject was named, so I used {lowest["subject"]}, which has the lowest class average ({lowest["average"]:.0f}%).')
        return sub

    if any(w in q for w in ["average", "mean", "overall", "how is", "how did"]):
        return _answer([head] + [f'{r["subject"]}: class average {r["average"]:.0f}% ({r["assessment_name"]}).' for r in o["subjects"]], [], [])

    return _answer([NO_DATA + " I can answer questions about weak topics, students needing attention, revision plans, "
                    "averages, and changes since the last test. Mention a subject (English, Accountancy, BST, Economics) to go deeper."], [], [])


def ask_rules(class_id, question, subject=None):
    """The calculated, keyword-based answer. Always works, needs no internet.
    `subject` is the tab the teacher is viewing; a subject named in the question wins."""
    available = analytics.subjects(class_id)
    chosen = detect_subject(question, available) or (subject if subject in available else None)
    if not chosen and len(available) == 1:
        chosen = available[0]  # only one subject so far: no need to ask which
    if chosen:
        return _subject_answer(class_id, question, chosen)
    return _overview_answer(class_id, question)

def ask(class_id, question, subject=None, use_ai=True):
    """Uses the AI layer if an API key is set; otherwise (or if anything fails) uses the rule-based answer."""
    import llm
    if use_ai and llm.available():
        try:
            answer = llm.ask(class_id, question, subject)
            answer["source"] = "AI (student names hidden from the AI)"
            return answer
        except Exception as err:  # never crash the dashboard because the AI had a problem
            fallback = ask_rules(class_id, question, subject)
            fallback["source"] = f"calculated rules (AI unavailable: {type(err).__name__})"
            return fallback
    result = ask_rules(class_id, question, subject)
    result["source"] = "calculated rules"
    return result
