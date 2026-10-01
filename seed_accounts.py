# =============================================================================
# seed_accounts.py — ZamFarm Climate
# Creates default Admin + 2 Extension Officer accounts.
#
# RUN ONCE from your project folder:
#   cd C:\xampp\htdocs\AI-Farming-System
#   venv\Scripts\activate
#   python seed_accounts.py
# =============================================================================

import MySQLdb
from werkzeug.security import generate_password_hash

conn = MySQLdb.connect(
    host="127.0.0.1", user="root", passwd="S1@mudaLa", db="ai_farming_db", charset="utf8mb4"
)
cur = conn.cursor()

# ── Admin ─────────────────────────────────────────────────────────────────────
ADMIN = {"username": "admin", "password": "admin123", "email": "admin@zamfarmclimate.zm"}

cur.execute("SELECT id FROM admins WHERE username=%s", (ADMIN["username"],))
if cur.fetchone():
    cur.execute("UPDATE admins SET password=%s, email=%s WHERE username=%s",
                (generate_password_hash(ADMIN["password"]), ADMIN["email"], ADMIN["username"]))
    print("✅ Admin account updated.")
else:
    cur.execute("INSERT INTO admins (username, password, email) VALUES (%s,%s,%s)",
                (ADMIN["username"], generate_password_hash(ADMIN["password"]), ADMIN["email"]))
    print("✅ Admin account created.")

# ── Extension Officers ────────────────────────────────────────────────────────
OFFICERS = [
    {
        "fullname": "Alice Banda",
        "email":    "alice.banda@zamfarmclimate.zm",
        "password": "officer123",
        "zone":     "Choma",
        "phone":    "+260971000001",
    },
    {
        "fullname": "James Phiri",
        "email":    "james.phiri@zamfarmclimate.zm",
        "password": "officer123",
        "zone":     "Lusaka",
        "phone":    "+260971000002",
    },
]

for o in OFFICERS:
    cur.execute("SELECT id FROM extension_officers WHERE email=%s", (o["email"],))
    if cur.fetchone():
        cur.execute("UPDATE extension_officers SET password=%s, zone=%s WHERE email=%s",
                    (generate_password_hash(o["password"]), o["zone"], o["email"]))
        print(f"✅ Officer '{o['fullname']}' updated.")
    else:
        cur.execute("""
            INSERT INTO extension_officers (fullname, email, password, zone, phone)
            VALUES (%s,%s,%s,%s,%s)
        """, (o["fullname"], o["email"],
              generate_password_hash(o["password"]), o["zone"], o["phone"]))
        print(f"✅ Officer '{o['fullname']}' created.")

conn.commit()
conn.close()

print()
print("=" * 55)
print("  LOGIN CREDENTIALS")
print("=" * 55)
print()
print("  ADMIN")
print("  ─────────────────────────────────────────────")
print("  Dropdown  : Admin")
print(f"  Username  : {ADMIN['username']}")
print(f"  Password  : {ADMIN['password']}")
print()
print("  EXTENSION OFFICER 1")
print("  ─────────────────────────────────────────────")
print("  Dropdown  : Officer")
print(f"  Email     : {OFFICERS[0]['email']}")
print(f"  Password  : {OFFICERS[0]['password']}")
print(f"  Zone      : {OFFICERS[0]['zone']}")
print()
print("  EXTENSION OFFICER 2")
print("  ─────────────────────────────────────────────")
print("  Dropdown  : Officer")
print(f"  Email     : {OFFICERS[1]['email']}")
print(f"  Password  : {OFFICERS[1]['password']}")
print(f"  Zone      : {OFFICERS[1]['zone']}")
print()
print("  FARMER")
print("  ─────────────────────────────────────────────")
print("  Dropdown  : Farmer")
print("  Use your registered phone/email + password")
print()
print("=" * 55)
print("  ⚠️  Change these passwords after first login!")
print("=" * 55)