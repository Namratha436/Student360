"""Create (or reset the password of) a staff account.
Usage: python create_staff.py "Dr. Rao" rao@college.edu Password123 ECE      (department = CSE, ECE, ... or ALL)
Tip: wrap the password in double quotes if it contains symbols such as & ^ % ! $"""
import os, sqlite3, sys, pandas as pd
from werkzeug.security import generate_password_hash
os.chdir(os.path.dirname(os.path.abspath(__file__)))            # always use the project's own users.db
from schema import init_db
if len(sys.argv) != 5: sys.exit(__doc__)
name, email, pw, dept = sys.argv[1:5]; email = email.strip().lower(); dept = dept.upper()
valid = set(pd.read_csv("student_performance_monitoring_dataset.csv").department)
if dept != "ALL" and dept not in valid: sys.exit(f"Unknown department. Use one of {sorted(valid)} or ALL")
if len(pw) < 6: sys.exit("Password must be at least 6 characters")
c = sqlite3.connect("users.db"); init_db(c)
old = c.execute("SELECT role FROM users WHERE email=?", (email,)).fetchone()
if old and old[0] != "staff": sys.exit("That email belongs to a student account. Use a different email.")
if old: c.execute("UPDATE users SET name=?, password_hash=?, department=? WHERE email=?", (name, generate_password_hash(pw), dept, email)); msg = "Staff account UPDATED"
else: c.execute("INSERT INTO users(name,email,password_hash,role,department) VALUES(?,?,?,'staff',?)", (name, email, generate_password_hash(pw), dept)); msg = "Staff account CREATED"
c.commit(); print(f"{msg}: {email} ({dept})\nDatabase file: {os.path.abspath('users.db')}")
