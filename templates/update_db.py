import sqlite3

conn = sqlite3.connect("trainings.db")
c = conn.cursor()

# Users Tabelle
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    passwort_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    alter_jahre INTEGER,
    gewicht_kg REAL,
    profilbild TEXT,
    garmin_email TEXT,
    garmin_passwort TEXT,
    erstellt_am TEXT DEFAULT (date('now'))
)
""")
print("Users Tabelle erstellt")

# user_id zu trainings
try:
    c.execute("ALTER TABLE trainings ADD COLUMN user_id INTEGER")
    print("user_id zu trainings hinzugefuegt")
except:
    print("user_id in trainings existiert bereits")

# user_id zu gesundheit
try:
    c.execute("ALTER TABLE gesundheit ADD COLUMN user_id INTEGER")
    print("user_id zu gesundheit hinzugefuegt")
except:
    print("user_id in gesundheit existiert bereits")

# user_id zu coaching
try:
    c.execute("ALTER TABLE coaching ADD COLUMN user_id INTEGER")
    print("user_id zu coaching hinzugefuegt")
except:
    print("user_id in coaching existiert bereits")

conn.commit()
conn.close()
print("\nAlle Tabellen aktualisiert!")