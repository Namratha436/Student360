"""Finds where startup is slow. Run:  python diagnose.py
If it stalls, wait ~20 seconds: it prints exactly which file/line it is stuck on."""
import faulthandler, time, sys, os
faulthandler.dump_traceback_later(20, repeat=True)          # prints the current stack every 20 s if still running
os.chdir(os.path.dirname(os.path.abspath(__file__)))
t0 = time.time()
def step(msg): print(f"[{time.time()-t0:6.1f}s] {msg}", flush=True)
step(f"Python {sys.version.split()[0]} in {os.getcwd()}")
import pandas;   step(f"pandas {pandas.__version__} imported")
import sklearn;  step(f"scikit-learn {sklearn.__version__} imported")
import flask;    step("flask imported")
import joblib;   step("joblib imported")
import analysis; step("analysis.py + CSV loaded")
joblib.load("ann_model.joblib"); step("model file loaded")
import records;  step("records.py loaded")
import app;      step("app.py fully imported - startup is OK")
faulthandler.cancel_dump_traceback_later()
