import sqlite3

verbindung = sqlite3.connect("trainings.db")
cursor = verbindung.cursor()

# Tabelle für Nutzerdaten (nur ein Eintrag, da Einzelnutzer-App)
cursor.execute("""
CREATE TABLE IF NOT EXISTS nutzer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    alter_jahre INTEGER NOT NULL,
    gewicht_kg REAL NOT NULL
)
""")

# Tabelle für Trainingseinheiten (mit neuen Spalten pace und kalorien)
cursor.execute("""
CREATE TABLE IF NOT EXISTS trainings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    datum TEXT NOT NULL,
    art TEXT NOT NULL,
    dauer_minuten INTEGER,
    distanz_km REAL,
    pace_min_km TEXT,
    kalorien REAL,
    notiz TEXT
)
""")
# Tabelle für einzelne Übungen beim Krafttraining
cursor.execute("""
CREATE TABLE IF NOT EXISTS uebungen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    training_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    saetze INTEGER NOT NULL,
    wiederholungen INTEGER NOT NULL,
    gewicht_kg REAL NOT NULL,
    FOREIGN KEY (training_id) REFERENCES trainings (id) ON DELETE CASCADE
)
""")
# Tabelle für tägliche Gesundheitsdaten von Garmin
cursor.execute("""
CREATE TABLE IF NOT EXISTS gesundheit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    datum TEXT NOT NULL UNIQUE,
    schritte INTEGER,
    ruhepuls INTEGER,
    stress_level INTEGER,
    body_battery INTEGER,
    schlaf_dauer_min INTEGER,
    schlaf_score INTEGER,
    kalorien_gesamt REAL
)
""")

verbindung.commit()
verbindung.close()

print("Datenbank und Tabellen wurden erfolgreich erstellt!")