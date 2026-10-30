import os, io, csv, json, re, sqlite3, secrets, joblib, pandas as pd
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, abort, Response
from werkzeug.security import generate_password_hash, check_password_hash
import analysis, records
from schema import init_db

os.chdir(os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024               # bulk uploads up to 2 MB
KEY = ".secret_key"                      # persistent key so sessions survive restarts
if not os.path.exists(KEY): open(KEY, "w").write(secrets.token_hex(32))
app.secret_key = open(KEY).read()
DB = "users.db"

def load_model():
    """Load the saved ANN. If it is missing, or was saved by a different scikit-learn version, retrain it (one-time)."""
    import warnings
    from sklearn.exceptions import InconsistentVersionWarning
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", InconsistentVersionWarning)       # a version mismatch counts as a failure
            return joblib.load("ann_model.joblib")
    except Exception:
        import subprocess, sys
        print("Training the model for this scikit-learn version (one-time, takes a few seconds)...", flush=True)
        subprocess.run([sys.executable, "train_model.py"], check=True)
        return joblib.load("ann_model.joblib")

model, LABELS = load_model()
df = analysis.df
FEATURES = df.drop(columns=["student_id", "performance_category", "overall_performance_score"]).columns

# ---- on startup: re-apply the latest monthly update of every student on top of the CSV baseline
_c = sqlite3.connect(DB); init_db(_c)
for sid, data in _c.execute("SELECT student_id, data FROM monthly_updates m WHERE month=(SELECT MAX(month) FROM monthly_updates WHERE student_id=m.student_id)"):
    if sid in set(df.student_id): records.apply(sid, json.loads(data), refresh_now=False)
records.refresh(); _c.close()

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB); g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close(_):
    d = g.pop("db", None)
    if d: d.close()

def current_user():
    return db().execute("SELECT * FROM users WHERE id=?", (session["uid"],)).fetchone() if "uid" in session else None

def csrf():
    if "csrf" not in session: session["csrf"] = secrets.token_hex(16)
    return session["csrf"]
app.jinja_env.globals["csrf_token"] = csrf

def check_csrf():
    if not secrets.compare_digest(request.form.get("csrf", "").encode(), session.get("csrf", "x").encode()): abort(400)

def staff_required(f):
    @wraps(f)
    def wrapper(*a, **k):
        u = current_user()
        if not u: return redirect(url_for("login"))
        if u["role"] != "staff": abort(403)
        g.user = u; return f(*a, **k)
    return wrapper

def scope_df(u): return df if u["department"] == "ALL" else df[df.department == u["department"]]
def in_scope(u, sid): return sid in set(scope_df(u).student_id)
def this_month(): return datetime.now().strftime("%Y-%m")
def valid_month(m): return bool(re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", m or "")) and m <= this_month()

def sync_student(sid, refresh_now=True):
    """Make the live data match the student's latest saved month (or the CSV baseline if none)."""
    r = db().execute("SELECT data FROM monthly_updates WHERE student_id=? ORDER BY month DESC LIMIT 1", (sid,)).fetchone()
    records.apply(sid, json.loads(r["data"]) if r else None, refresh_now)

def save_month(sid, month, values, note, uid):
    db().execute("""INSERT INTO monthly_updates(student_id,month,data,note,updated_by,updated_at) VALUES(?,?,?,?,?,?)
        ON CONFLICT(student_id,month) DO UPDATE SET data=excluded.data, note=excluded.note, updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
        (sid, month, json.dumps(values), note, uid, datetime.now().isoformat(timespec="seconds")))

def history(sid):
    rows = db().execute("""SELECT m.*, u.name AS staff_name FROM monthly_updates m LEFT JOIN users u ON u.id=m.updated_by
                           WHERE m.student_id=? ORDER BY m.month DESC""", (sid,)).fetchall()
    out = []
    for r in rows:
        d = json.loads(r["data"])
        out.append(dict(month=r["month"], att=d.get("attendance_percent"), acad=records.acad_avg(d), sgpa=d.get("sgpa"), cgpa=d.get("cgpa"),
                        ach=records.achievements(d), note=r["note"] or "", by=r["staff_name"] or "—", at=(r["updated_at"] or "")[:16]))
    return out

# ------------------------------------------------------------------ auth
@app.route("/")
def home():
    return redirect(url_for("dashboard" if "uid" in session else "login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name, email = request.form["name"].strip(), request.form["email"].strip().lower()
        sid, pw = request.form["student_id"].strip().upper(), request.form["password"]
        if len(pw) < 6: flash("Password must be at least 6 characters.")
        elif pw != request.form["confirm"]: flash("Passwords do not match.")
        elif sid not in set(df.student_id): flash("Student ID not found in the records.")
        else:
            try:
                db().execute("INSERT INTO users(name,email,student_id,password_hash,role) VALUES(?,?,?,?,'student')",
                             (name, email, sid, generate_password_hash(pw)))
                db().commit(); flash("Account created. Please log in."); return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That email or Student ID is already registered.")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    portal = request.values.get("portal", "student")
    if portal not in ("student", "staff"): portal = "student"
    if request.method == "POST":
        u = db().execute("SELECT * FROM users WHERE email=?", (request.form["email"].strip().lower(),)).fetchone()
        if not (u and check_password_hash(u["password_hash"], request.form["password"])):
            flash("Invalid email or password.")
        elif (u["role"] == "staff") != (portal == "staff"):
            flash("This is a staff account. Please use the Staff tab." if u["role"] == "staff" else "This is a student account. Please use the Student tab.")
        else:
            session.clear(); session["uid"] = u["id"]
            return redirect(url_for("staff_home" if u["role"] == "staff" else "dashboard"))
    return render_template("login.html", portal=portal)

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

# ------------------------------------------------------------------ student dashboard
@app.route("/dashboard")
def dashboard():
    if "uid" not in session: return redirect(url_for("login"))
    u = db().execute("SELECT * FROM users WHERE id=?", (session["uid"],)).fetchone()
    if not u: session.clear(); return redirect(url_for("login"))
    if u["role"] == "staff": return redirect(url_for("staff_home"))
    idx = df.index[df.student_id == u["student_id"]][0]
    s = df.loc[idx]
    probs = model.predict_proba(df.loc[[idx], FEATURES])[0]
    pred = LABELS[probs.argmax()]
    scores = analysis.area_scores(idx)
    tips = analysis.suggestions(s, scores)
    co, ex, ld = analysis.activity_items(s)
    tot = lambda L: int(sum(v for _, v in L))
    counts = dict(co=tot(co), ex=tot(ex), ld=tot(ld), awards=int(s.awards_received + s.prizes_won))
    counts["total"] = counts["co"] + counts["ex"] + counts["ld"]
    best = max(scores, key=lambda k: scores[k][0]); worst = min(scores, key=lambda k: scores[k][0])
    summary = (f"The ANN model predicts <b>{pred}</b> performance for you ({probs.max()*100:.0f}% confidence). "
               f"Your strongest area is {best.lower()} ({scores[best][0]}/100) and the area with most room to grow is "
               f"{worst.lower()} ({scores[worst][0]}/100).")
    acts = [(f"{n} × {int(v)}", c) for L, c in ((co, "Co-curricular"), (ex, "Extra-curricular"), (ld, "Leadership & service")) for n, v in L if v]
    hist = history(u["student_id"]); b = records.BASE.loc[idx]
    asc = hist[::-1]
    trend = dict(labels=["Baseline"] + [h["month"] for h in asc],
                 att=[float(b.attendance_percent)] + [h["att"] for h in asc],
                 acad=[records.acad_avg(b.to_dict())] + [h["acad"] for h in asc])
    return render_template("dashboard.html", u=u, s=s, pred=pred, probs=dict(zip(LABELS, (probs*100).round(1))),
        scores=scores, comps=analysis.components(s), counts=counts, summary=summary, acts=acts,
        strengths=[t for t in tips if t[0] == "good"], focus=[t for t in tips if t[0] != "good"],
        initials="".join(w[0] for w in u["name"].split()[:2]).upper(), co=co, ex=ex, ld=ld,
        hist=hist, trend=trend, last_update=hist[0]["month"] if hist else None)

# ------------------------------------------------------------------ staff portal
def staff_ctx(**kw):
    u = g.user
    return dict(u=u, initials="".join(w[0] for w in u["name"].split()[:2]).upper(), cur=this_month(), **kw)

@app.route("/staff")
@staff_required
def staff_home():
    u, cur = g.user, this_month(); sc = scope_df(u)
    last = {r[0]: r[1] for r in db().execute("SELECT student_id, MAX(month) FROM monthly_updates GROUP BY student_id")}
    done = {r[0] for r in db().execute("SELECT student_id FROM monthly_updates WHERE month=?", (cur,))}
    names = {r["student_id"]: r["name"] for r in db().execute("SELECT student_id,name FROM users WHERE role='student'")}
    q, yr, st, dp = (request.args.get(k, "").strip() for k in ("q", "year", "status", "dept"))
    d = sc
    if q: d = d[d.student_id.str.contains(q.upper(), regex=False)]
    if yr.isdigit(): d = d[d.year == int(yr)]
    if dp and u["department"] == "ALL": d = d[d.department == dp]
    if st == "updated": d = d[d.student_id.isin(done)]
    elif st == "pending": d = d[~d.student_id.isin(done)]
    rows = [dict(id=r.student_id, name=names.get(r.student_id), dept=r.department, year=r.year, sem=r.semester, att=r.attendance_percent, cgpa=r.cgpa,
                 score=r.overall_performance_score, cat=r.performance_category, last=last.get(r.student_id), done=r.student_id in done) for r in d.head(300).itertuples()]
    return render_template("staff.html", **staff_ctx(page="list", rows=rows, total=len(sc), shown=len(d), updated=len(set(sc.student_id) & done),
                           avg_att=round(float(sc.attendance_percent.mean()), 1), depts=sorted(df.department.unique()), f=dict(q=q, year=yr, status=st, dept=dp)))

@app.route("/staff/student/<sid>", methods=["GET", "POST"])
@staff_required
def staff_student(sid):
    u, sid = g.user, sid.upper()
    if not in_scope(u, sid): abort(403 if sid in set(df.student_id) else 404)
    month = request.values.get("month") or this_month()
    if not valid_month(month): flash("Choose a valid month that is not in the future.", "err"); month = this_month()
    saved = db().execute("SELECT data, note FROM monthly_updates WHERE student_id=? AND month=?", (sid, month)).fetchone()
    vals = {**records.current_values(sid), **(json.loads(saved["data"]) if saved else {})}; note = saved["note"] if saved else ""
    if request.method == "POST":
        check_csrf()
        clean, errs = records.validate(request.form)
        if errs:
            for e in errs[:6]: flash(e, "err")
            vals.update(request.form.to_dict()); note = request.form.get("note", "")
        else:
            note = request.form.get("note", "").strip()[:300]
            save_month(sid, month, {**vals, **clean}, note, u["id"]); db().commit(); sync_student(sid)
            flash(f"{sid}: {month} record saved. Dashboard and predictions are updated.", "ok")
            return redirect(url_for("staff_student", sid=sid, month=month))
    name = db().execute("SELECT name FROM users WHERE student_id=?", (sid,)).fetchone()
    s = df.loc[df.index[df.student_id == sid][0]]
    return render_template("staff_student.html", **staff_ctx(page="list", sid=sid, s=s, name=name["name"] if name else None, month=month, vals=vals,
                           note=note, groups=records.GROUPS, hist=history(sid)))

@app.route("/staff/student/<sid>/delete/<month>", methods=["POST"])
@staff_required
def staff_delete(sid, month):
    check_csrf(); sid = sid.upper()
    if not in_scope(g.user, sid): abort(403)
    db().execute("DELETE FROM monthly_updates WHERE student_id=? AND month=?", (sid, month)); db().commit(); sync_student(sid)
    flash(f"Removed the {month} record for {sid}.", "ok")
    return redirect(url_for("staff_student", sid=sid))

@app.route("/staff/export.csv")
@staff_required
def staff_export():
    d = scope_df(g.user)[["student_id"] + list(records.SPEC)]
    return Response(d.to_csv(index=False), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=students_current.csv"})

@app.route("/staff/upload", methods=["GET", "POST"])
@staff_required
def staff_upload():
    u, report = g.user, None
    if request.method == "POST":
        check_csrf()
        f, default_month = request.files.get("file"), request.form.get("month") or this_month()
        if not f or not f.filename.lower().endswith(".csv"): flash("Please choose a .csv file.", "err")
        else:
            try: rdr = csv.DictReader(io.StringIO(f.read().decode("utf-8-sig")))
            except UnicodeDecodeError: rdr = None; flash("Could not read the file. Save it as CSV (UTF-8).", "err")
            if rdr is not None:
                ok, errors, touched = 0, [], set()
                if "student_id" not in (rdr.fieldnames or []): flash("The CSV needs a 'student_id' column.", "err")
                else:
                    for n, row in enumerate(rdr, start=2):
                        sid = (row.get("student_id") or "").strip().upper(); month = (row.get("month") or default_month).strip()
                        if sid not in set(df.student_id): errors.append(f"Row {n}: unknown student '{sid}'"); continue
                        if not in_scope(u, sid): errors.append(f"Row {n}: {sid} is outside your department"); continue
                        if not valid_month(month): errors.append(f"Row {n}: invalid month '{month}'"); continue
                        clean, errs = records.validate(row)
                        if errs: errors.append(f"Row {n} ({sid}): " + "; ".join(errs[:3])); continue
                        if not clean: errors.append(f"Row {n} ({sid}): no values to update"); continue
                        save_month(sid, month, {**records.current_values(sid), **clean}, "Bulk upload", u["id"]); touched.add(sid); ok += 1
                    db().commit()
                    for sid in touched: sync_student(sid, refresh_now=False)
                    records.refresh()
                    report = dict(ok=ok, bad=len(errors), errors=errors[:25])
    return render_template("staff_upload.html", **staff_ctx(page="upload", report=report))

if __name__ == "__main__":
    print("Student360 ready: http://127.0.0.1:5000", flush=True)
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
