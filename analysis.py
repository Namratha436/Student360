"""Scores the 5 areas, benchmarks against the dataset and writes suggestions."""
import pandas as pd

df = pd.read_csv("student_performance_monitoring_dataset.csv")
ACAD = ["internal_marks", "assignment_average", "quiz_average", "midterm_marks", "final_exam_marks"]
SOFT = ["teamwork_score", "communication_score", "presentation_score",
        "problem_solving_score", "technical_skill_score", "leadership_score"]

def _areas(d):
    o = pd.DataFrame(index=d.index)
    o["Academics"] = d[ACAD].mean(axis=1)
    o["Attendance"] = d["attendance_percent"]
    o["Co-curricular"] = (d.paper_presentations*3 + d.seminars_attended + d.workshops_attended*2 +
        d.quizzes_participated + d.conferences_attended*2 + d.hackathons_participated*3 +
        d.certifications*3 + d.technical_competitions*3 + d.awards_received*4 + d.prizes_won*4)
    o["Extra-curricular"] = (d[["sports","music","painting","dance","drama"]].sum(axis=1)*2 +
        d.volunteering_activities + d.clubs_participated + d.leadership_positions*3 + d.events_organized*2)
    o["Soft skills"] = d[SOFT].mean(axis=1) * 10
    return o

ALL = _areas(df)
PCT = ALL.rank(pct=True) * 100          # percentile among all students -> 0-100 score

def area_scores(row_idx):
    """Return {area: (score 0-100, dept average)} for one student."""
    dept = df.loc[row_idx, "department"]
    mask = df.department == dept
    res = {}
    for a in ALL.columns:
        score = ALL.loc[row_idx, a] if a in ("Academics", "Attendance", "Soft skills") else PCT.loc[row_idx, a]
        base = ALL[a][mask].mean() if a in ("Academics", "Attendance", "Soft skills") else PCT[a][mask].mean()
        res[a] = (round(float(score), 1), round(float(base), 1))
    return res

def suggestions(s, scores):
    t = []  # (level, area, text)  level: bad / warn / good
    att = s.attendance_percent
    if att < 75: t.append(("bad", "Attendance", f"Attendance is {att:.0f}%, below the usual 75% eligibility limit. Prioritise attending every class this month."))
    elif att < 85: t.append(("warn", "Attendance", f"Attendance is {att:.0f}%. Aim for 85%+ to build a safety margin."))
    else: t.append(("good", "Attendance", f"Great attendance ({att:.0f}%). Keep it up."))

    comp = {"internal marks": s.internal_marks, "assignments": s.assignment_average, "quizzes": s.quiz_average,
            "mid-term": s.midterm_marks, "final exam": s.final_exam_marks}
    weakest = min(comp, key=comp.get)
    if comp[weakest] < 65: t.append(("bad", "Academics", f"Your weakest component is {weakest} ({comp[weakest]:.0f}). Revise those topics and ask faculty for practice papers."))
    elif comp[weakest] < 75: t.append(("warn", "Academics", f"Lowest academic area is {weakest} ({comp[weakest]:.0f}). A little extra practice there will lift your SGPA."))
    else: t.append(("good", "Academics", "Marks are consistent across all components. Aim for top-grade targets next."))
    if s.final_exam_marks + 8 < s.internal_marks: t.append(("warn", "Academics", "Exam marks are well below internal marks: work on time management and previous-year papers."))
    if s.study_hours_per_day < 2.5: t.append(("warn", "Study habits", f"You study {s.study_hours_per_day:.1f} h/day. Try a fixed 3-4 h routine with short breaks."))
    elif s.study_hours_per_day > 6: t.append(("warn", "Study habits", "Very long study hours: add sleep and breaks, quality matters more than quantity."))
    if s.sgpa < s.cgpa - 0.3: t.append(("bad", "Academics", f"SGPA ({s.sgpa}) dropped below your CGPA ({s.cgpa}). Find which subjects pulled it down."))

    cc = scores["Co-curricular"][0]
    if cc < 40:
        t.append(("warn", "Co-curricular", "Low technical activity. Join a workshop, earn one certification and try a hackathon this semester."))
        if s.certifications == 0: t.append(("warn", "Co-curricular", "You have no certifications yet: a course in your department's core area strengthens your profile."))
        if s.paper_presentations == 0: t.append(("warn", "Co-curricular", "Present a paper or project at a seminar to build research experience."))
    elif cc >= 70: t.append(("good", "Co-curricular", "Strong co-curricular record. Aim for a competition win or publication."))

    ex = scores["Extra-curricular"][0]
    arts = s.sports + s.music + s.painting + s.dance + s.drama
    if ex < 40 or (arts == 0 and s.clubs_participated == 0):
        t.append(("warn", "Extra-curricular", "Little extra-curricular involvement. Join a club, sport or volunteering drive for balance and stress relief."))
    elif ex >= 70: t.append(("good", "Extra-curricular", "Excellent all-round involvement."))
    if s.leadership_positions == 0 and s.events_organized == 0: t.append(("warn", "Leadership", "Organise an event or take a club role to build leadership."))

    soft = {"teamwork": s.teamwork_score, "communication": s.communication_score, "presentation": s.presentation_score,
            "problem solving": s.problem_solving_score, "technical skills": s.technical_skill_score, "leadership": s.leadership_score}
    ws = min(soft, key=soft.get)
    if soft[ws] < 6: t.append(("warn", "Soft skills", f"Your lowest skill is {ws} ({soft[ws]:.1f}/10). Practise it through group projects and mock interviews."))
    return t

COMPS = [("Internal", "internal_marks"), ("Assignments", "assignment_average"), ("Quizzes", "quiz_average"),
         ("Mid-term", "midterm_marks"), ("Final exam", "final_exam_marks")]

def components(s):
    d = df[df.department == s.department]
    return [(l, round(float(s[c]), 1), round(float(d[c].mean()), 1)) for l, c in COMPS]

def activity_items(s):
    co = [("Paper presentations", s.paper_presentations), ("Seminars attended", s.seminars_attended), ("Workshops attended", s.workshops_attended),
          ("Quizzes participated", s.quizzes_participated), ("Conferences attended", s.conferences_attended), ("Hackathons", s.hackathons_participated),
          ("Certifications", s.certifications), ("Technical competitions", s.technical_competitions)]
    ex = [(n.title(), s[n]) for n in ("sports", "music", "painting", "dance", "drama")] + [("Clubs", s.clubs_participated)]
    ld = [("Volunteering", s.volunteering_activities), ("Leadership positions", s.leadership_positions), ("Events organized", s.events_organized)]
    return co, ex, ld
