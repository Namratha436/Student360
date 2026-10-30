"""Shows every account in the database. Optional: test a login.
Usage: python check_users.py                      (list accounts)
       python check_users.py email password       (test that email + password)"""
import os, sqlite3, sys
from werkzeug.security import check_password_hash
os.chdir(os.path.dirname(os.path.abspath(__file__)))
print("Database file:", os.path.abspath("users.db"))
if not os.path.exists("users.db"): sys.exit("users.db does not exist yet. Create a staff account first.")
rows = sqlite3.connect("users.db").execute("SELECT email, role, department, student_id, password_hash FROM users").fetchall()
print(f"{len(rows)} account(s):")
for e, r, d, s, _ in rows: print(f"  {e:35} role={r}  dept={d}  student_id={s}")
if len(sys.argv) == 3:
    m = [x for x in rows if x[0] == sys.argv[1].strip().lower()]
    print("\nLOGIN TEST:", "no account with that email" if not m else ("password CORRECT" if check_password_hash(m[0][4], sys.argv[2]) else "email found but password is WRONG"))
