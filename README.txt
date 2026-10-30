STUDENT360 - setup
1. pip install -r requirements.txt
2. python app.py        (first start trains the model automatically, a few seconds)
3. python create_staff.py "Dr. Rao" rao@college.edu Rao12345 CSE      (department or ALL)
4. Open http://127.0.0.1:5000  ->  Student tab (register with an ID like S100001) or Staff tab.
Troubleshooting: python diagnose.py (finds slow startup)   |   python check_users.py (lists accounts)
