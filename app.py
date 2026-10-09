"""
PYQOO Pro — your HTML quiz app inside Streamlit.

Who can open the app is controlled by Streamlit itself:
  Streamlit Cloud → your app → Share → "Only specific people can view this app"
  → add each buyer's email as a viewer after payment.
This file only shows the quiz (quiz_template.html) with the questions from the private data file.
"""
import html
import json
import re
from pathlib import Path

import streamlit as st

# ═══════════════════════════════════════════════════════════════════════════
#  SETTINGS — edit these
# ═══════════════════════════════════════════════════════════════════════════
APP_TITLE = "PYQOO Pro"
TITLE = "PYQOO Pro — UGC NET Paper 1 PYQ Practice (2015–2025)"          # browser-tab title of the quiz
EXAM_LABEL = "UGC NET · Paper 1 · Previous year papers 2015 – 2025"               # small line above the heading
EXAM_SHORT = "UGC NET Paper 1 · PYQ 2015–2025"                      # shown in the exam top bar
# One line per question file: (file, category). Files that do not exist yet are simply skipped,
# so you can add the MCQ and AI files whenever they are ready.
# A question's own "category" field, if present, wins over the file's category.
# The combined file holds every past paper (Dec 2023, Jun 2025 and 2015-2021). Put it at data/ugcnet-all-combined.json
# (the name may use "_" or "-"). Questions repeated across files are shown only once (matched by their "id").
DATA_FILES = [
    ("data/ugcnet-all-combined.json", "PYQ"),   # previous year questions - ALL papers in one file
    ("data/ugcnet-dec2023.json", "PYQ"),     # old single-paper file; only used for questions not already in the combined file
    ("data/ugcnet-mcq.json", "MCQ"),         # MCQ simulated from PYQ
    ("data/ugcnet-ai.json", "AI"),           # AI predicted questions
    ("data/ugcnet-repeated.json", "REP"),    # most repeated questions (same question or same answer across papers)
]
DI_FILE = "data/ugcnet-di.json"          # data-interpretation sets (tables, graphs, charts). Optional.
TEMPLATE = "quiz_template.html"
# ═══════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title=APP_TITLE, page_icon="📖", layout="wide", initial_sidebar_state="collapsed")
e = lambda x: html.escape("" if x is None else str(x))

# Streamlit's top bar is left visible on purpose: the owner needs its "Share" button to invite viewers.
CSS = """
<style>
/* top padding keeps the quiz BELOW Streamlit's own toolbar (Share / ⋮), so no buttons are covered */
.block-container{padding:3.8rem .8rem 0 !important;max-width:100% !important}
iframe{border:0 !important;border-radius:10px;height:calc(100vh - 96px) !important;min-height:520px}
</style>
"""



def _norm(name):
    """'ugcnet_all_combined.json' and 'ugcnet-all-combined.json' count as the same file name."""
    return re.sub(r"[-_ ]+", "", name.lower())


def find_file(base, rel):
    """Exact path first; otherwise any file with the same name (ignoring - _ and spaces) anywhere in the repo."""
    p = base / rel
    if p.exists():
        return p
    name = _norm(Path(rel).name)
    for f in sorted(base.rglob("*")):
        if f.is_file() and _norm(f.name) == name and ".git" not in f.parts:
            return f
    return None


def find_template(base):
    """quiz_template.html — also finds renamed copies (e.g. 'quiz template.html') by their content."""
    p = find_file(base, TEMPLATE)
    if p:
        return p
    for f in sorted(base.rglob("*.htm*")):
        if ".git" in f.parts:
            continue
        try:
            if "__QUESTIONS_JSON__" in f.read_text(encoding="utf-8"):
                return f
        except Exception:
            pass
    return None


def list_repo_files(base):
    return sorted(str(f.relative_to(base)) for f in base.rglob("*")
                  if f.is_file() and ".git" not in f.parts and "__pycache__" not in f.parts)

def signature():
    """Changes whenever a file or a setting changes, so Streamlit never serves an outdated cached page."""
    base = Path(__file__).parent
    paths = [find_template(base), find_file(base, "data/sample-questions.json"), find_file(base, DI_FILE)]
    paths += [find_file(base, f) for f, _ in DATA_FILES]
    files = tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in paths if p)
    return files + (TITLE, EXAM_LABEL, EXAM_SHORT)


@st.cache_data(show_spinner="Loading questions…")
def build_page(sig):
    """Reads the question file(s) and bakes them into the HTML quiz template."""
    base = Path(__file__).parent
    tpl = find_template(base)
    if tpl is None:
        return None, 0, False
    data, seen_ids, seen_files = [], set(), set()
    for f, cat in DATA_FILES:
        p = find_file(base, f)
        if p and p.resolve() not in seen_files:
            seen_files.add(p.resolve())
            for q in json.loads(p.read_text(encoding="utf-8")):
                if isinstance(q, dict):
                    qid = q.get("id")
                    if qid is not None and qid in seen_ids:      # same question already loaded from an earlier file
                        continue
                    if qid is not None:
                        seen_ids.add(qid)
                    q.setdefault("category", cat)
                    data.append(q)
    sample = False
    if not data:
        sp = find_file(base, "data/sample-questions.json")
        if sp:
            data, sample = json.loads(sp.read_text(encoding="utf-8")), True
    data = [q for q in data if isinstance(q, dict) and q.get("options") and q.get("correct")]
    di = []
    dp = find_file(base, DI_FILE)
    if dp:
        try:
            di = [x for x in json.loads(dp.read_text(encoding="utf-8")) if isinstance(x, dict) and x.get("questions")]
        except Exception:
            di = []
    di_payload = json.dumps(di, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    # '<' is written as \u003c so nothing inside a question can ever close the <script> tag
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    page = tpl.read_text(encoding="utf-8")
    for key, val in (("__TITLE__", e(TITLE)), ("__EXAM_LABEL__", e(EXAM_LABEL)), ("__EXAM_SHORT__", e(EXAM_SHORT))):
        page = page.replace(key, val)
    page = page.replace("__DI_JSON__", di_payload)
    page = page.replace("__QUESTIONS_JSON__", payload)      # last: question text can never be re-substituted
    return page, len(data), sample


def embed(page):
    height = 900
    if hasattr(st, "iframe"):            # newer Streamlit
        st.iframe(page, height=height)
    else:                                # older Streamlit
        import streamlit.components.v1 as components
        components.html(page, height=height, scrolling=True)


def main():
    st.markdown(CSS, unsafe_allow_html=True)
    page, n, sample = build_page(signature())
    if page is None:
        st.error("The quiz design file **quiz_template.html** was not found in this app's GitHub repository.")
        st.markdown("**Fix:** upload `quiz_template.html` to the same place as `app.py` (the main folder of the repo), "
                    "then reboot the app. These are the files the app can see right now:")
        st.code("\n".join(list_repo_files(Path(__file__).parent)) or "(none)")
        st.stop()
    if n == 0:
        st.error("No questions found. Put your JSON file in the **data/** folder (for example data/ugcnet-dec2023.json).")
        st.code("\n".join(list_repo_files(Path(__file__).parent)))
        st.stop()
    if sample:
        st.warning("Showing the small SAMPLE question set. Put your real question file at data/ugcnet-dec2023.json.")
    embed(page)


main()
