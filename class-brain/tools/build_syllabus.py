import re, json, subprocess
CH = [(1,"keac101","Introduction to Accounting"),(2,"keac102","Theory Base of Accounting"),
      (3,"keac103","Recording of Transactions-I"),(4,"keac104","Recording of Transactions-II"),
      (5,"keac105","Bank Reconciliation Statement"),(6,"keac106","Trial Balance and Rectification of Errors"),
      (7,"keac107","Depreciation, Provisions and Reserves")]
OVERRIDES = {3: [("3.1", "Business Transactions and Source Document")], 7: [("7.1", "Depreciation")]}
PAT = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})(?:\.(\d{1,2}))?\.?[\s\t]+([A-Z][^\n]{2,100}?)\s*$")
out, gaps = [], []
for num, f, title in CH:
    txt = subprocess.run(["pdftotext", "-layout", f + ".pdf", "-"], capture_output=True, text=True).stdout
    pages = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", f + ".pdf"], capture_output=True, text=True).stdout).group(1))
    secs, seen = [], set()
    for line in txt.splitlines():
        m = PAT.match(line)
        if not m or int(m.group(1)) != num:
            continue
        a, b, c, t = int(m.group(2)), m.group(3), m.group(3), re.sub(r"\s+", " ", m.group(4)).strip(" .")
        if t.endswith((",", ";")) or len(t.split()) > 14 or re.search(r"\.\s+[A-Z]", t):
            continue  # looks like a sentence, not a heading
        key = f"{num}.{a}" + (f".{c}" if c else "")
        if key in seen:
            continue
        seen.add(key)
        secs.append({"no": key, "title": t, "level": 2 if c else 1})
    for no, t in OVERRIDES.get(num, []):  # headings printed beside the objectives box, verified by hand
        if no not in seen:
            secs.append({"no": no, "title": t, "level": 1})
    secs.sort(key=lambda x: [int(p) for p in x["no"].split(".")])
    l1 = sorted(int(s["no"].split(".")[1]) for s in secs if s["level"] == 1)
    missing = [n for n in range(1, (max(l1) if l1 else 0) + 1) if n not in l1]
    gaps.append((num, missing))
    out.append({"chapter": num, "title": title, "file": f + ".pdf", "pdf_pages": pages, "sections": secs})
json.dump({"subject": "Accountancy", "book": "NCERT Accountancy - Financial Accounting Part I (Class XI)",
           "chapters": out}, open("syllabus.json", "w"), indent=1)
for ch in out:
    print(ch["chapter"], ch["title"], "| pdf pages:", ch["pdf_pages"], "| sections:", len(ch["sections"]), "| level-1:", sum(1 for s in ch["sections"] if s["level"] == 1))
print("missing level-1 numbers:", gaps)
