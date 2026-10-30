"""Monthly record updates: editable fields, validation, and applying updates to the in-memory dataset."""
import numpy as np, pandas as pd
from sklearn.linear_model import LinearRegression
import analysis

df = analysis.df
BASE = df.copy()                       # the original CSV values; monthly updates are applied on top of this

# (key, label, min, max, kind)  kind: f = decimal, i = whole number
GROUPS = {
 "Academics & attendance": [("attendance_percent", "Attendance %", 0, 100, "f"), ("internal_marks", "Internal marks", 0, 100, "f"),
    ("assignment_average", "Assignment average", 0, 100, "f"), ("quiz_average", "Quiz average", 0, 100, "f"),
    ("midterm_marks", "Mid-term marks", 0, 100, "f"), ("final_exam_marks", "Final exam marks", 0, 100, "f"),
    ("sgpa", "SGPA", 0, 10, "f"), ("cgpa", "CGPA", 0, 10, "f"), ("study_hours_per_day", "Study hours / day", 0, 16, "f"),
    ("year", "Year", 1, 4, "i"), ("semester", "Semester", 1, 8, "i")],
 "Co-curricular achievements (running totals)": [("paper_presentations", "Paper presentations", 0, 50, "i"), ("seminars_attended", "Seminars attended", 0, 100, "i"),
    ("workshops_attended", "Workshops attended", 0, 100, "i"), ("quizzes_participated", "Quizzes participated", 0, 100, "i"),
    ("conferences_attended", "Conferences attended", 0, 50, "i"), ("hackathons_participated", "Hackathons", 0, 50, "i"),
    ("certifications", "Certifications", 0, 50, "i"), ("technical_competitions", "Technical competitions", 0, 50, "i"),
    ("awards_received", "Awards received", 0, 50, "i"), ("prizes_won", "Prizes won", 0, 50, "i")],
 "Extra-curricular & leadership": [("sports", "Sports (0/1)", 0, 1, "i"), ("music", "Music (0/1)", 0, 1, "i"), ("painting", "Painting (0/1)", 0, 1, "i"),
    ("dance", "Dance (0/1)", 0, 1, "i"), ("drama", "Drama (0/1)", 0, 1, "i"), ("volunteering_activities", "Volunteering", 0, 100, "i"),
    ("clubs_participated", "Clubs", 0, 20, "i"), ("leadership_positions", "Leadership positions", 0, 20, "i"), ("events_organized", "Events organized", 0, 50, "i")],
 "Skill ratings (1-10)": [("teamwork_score", "Teamwork", 1, 10, "f"), ("communication_score", "Communication", 1, 10, "f"),
    ("presentation_score", "Presentation", 1, 10, "f"), ("problem_solving_score", "Problem solving", 1, 10, "f"),
    ("technical_skill_score", "Technical skill", 1, 10, "f"), ("leadership_score", "Leadership", 1, 10, "f")],
}
SPEC = {k: (label, lo, hi, kind) for g in GROUPS.values() for k, label, lo, hi, kind in g}
CO_KEYS = [k for k, *_ in GROUPS["Co-curricular achievements (running totals)"]]

_NUM = [c for c in df.columns if c not in ("student_id", "department", "performance_category", "overall_performance_score")]
_lr = LinearRegression().fit(df[_NUM], df["overall_performance_score"])     # used only to ESTIMATE score changes

def category(score): return "High" if score >= 80 else ("Medium" if score >= 68 else "Low")

def validate(raw):
    """raw: dict of strings. Blank/missing keys are skipped. Returns (clean values, error messages)."""
    clean, errs = {}, []
    for k, (label, lo, hi, kind) in SPEC.items():
        v = raw.get(k)
        if v is None or str(v).strip() == "": continue
        try: x = float(v)
        except ValueError: errs.append(f"{label}: '{v}' is not a number"); continue
        if not (lo <= x <= hi): errs.append(f"{label}: {v} must be between {lo} and {hi}"); continue
        if kind == "i":
            if x != int(x): errs.append(f"{label}: must be a whole number"); continue
            x = int(x)
        clean[k] = x
    return clean, errs

def current_values(sid):
    s = df.loc[df.index[df.student_id == sid][0]]
    return {k: (int(s[k]) if SPEC[k][3] == "i" else round(float(s[k]), 2)) for k in SPEC}

def acad_avg(d):
    v = [d[k] for k in analysis.ACAD if k in d]
    return round(sum(v) / len(v), 1) if v else None

def achievements(d): return int(sum(d.get(k, 0) for k in CO_KEYS))

def refresh():
    analysis.ALL = analysis._areas(df); analysis.PCT = analysis.ALL.rank(pct=True) * 100

def apply(sid, values=None, refresh_now=True):
    """Reset the student's row to the CSV baseline, then apply `values` (the latest monthly update, if any)."""
    idx = df.index[df.student_id == sid][0]
    for c in BASE.columns: df.at[idx, c] = BASE.at[idx, c]
    if values:
        row = BASE.loc[idx].copy()
        for k, v in values.items(): row[k] = v
        delta = _lr.predict(pd.DataFrame([row[_NUM]]).astype(float))[0] - _lr.predict(BASE.loc[[idx], _NUM])[0]
        score = float(np.clip(BASE.at[idx, "overall_performance_score"] + delta, 0, 100))
        for k, v in values.items(): df.at[idx, k] = v
        df.at[idx, "overall_performance_score"] = round(score, 1); df.at[idx, "performance_category"] = category(score)
    if refresh_now: refresh()
