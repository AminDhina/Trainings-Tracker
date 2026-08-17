# 🏋️ Trainings-Tracker

Eine Fullstack-Web-App zum Tracken von Lauf- und Krafttraining mit automatischer Pace- und Kalorienberechnung, Bestleistungen, und interaktiven Diagrammen.

![Screenshot](screenshot.png)

## Features

**Lauf-Tracking**
- Automatische Pace-Berechnung (min/km) aus Distanz und Dauer
- Kalorienberechnung nach der ACSM-Formel (American College of Sports Medicine)
- Bestzeiten über Standarddistanzen (5K, 10K, Halbmarathon, Marathon)
- Persönliche Rekorde (längste Distanz, beste Pace, meiste Kalorien)

**Krafttraining-Tracking**
- Einzelne Übungen mit Sätzen, Wiederholungen und Gewicht erfassen
- Kalorienberechnung nach MET-Wert (Metabolic Equivalent of Task)
- Maximalgewicht pro Übung automatisch tracken
- Übungen nachträglich bearbeiten oder ergänzen

**Auswertung & Visualisierung**
- Interaktives Liniendiagramm mit Wochen-/Jahresansicht (Chart.js)
- Wochenstatistik (Distanz, Einheiten, Kalorien)
- Bestleistungen-Dashboard mit persönlichen Rekorden
- Getrennte Ansichten für Lauf- und Krafttraining

**Nutzererfahrung**
- Nutzerprofil (Name, Alter, Gewicht) für personalisierte Berechnungen
- Dynamisches Formular: Felder passen sich der Trainingsart an
- Animierte Erfolgsbestätigung nach dem Speichern
- Premium Dark Theme mit responsivem Design

## Tech Stack

| Technologie | Einsatzbereich |
|-------------|----------------|
| Python | Backend-Logik, Berechnungen |
| Flask | Web-Framework, Routing, Templates |
| SQLite | Datenbank (Trainings, Übungen, Nutzerprofil) |
| JavaScript | Dynamisches UI, Chart.js-Integration |
| Chart.js | Interaktive Diagramme |
| HTML/CSS | Frontend, Premium Dark Theme |

## Projektstruktur

```
Trainings-Tracker/
├── app.py                  # Flask-Backend mit allen Routen und Berechnungen
├── datenbank_setup.py      # Datenbank-Schema (Tabellen erstellen)
├── requirements.txt        # Python-Abhängigkeiten
├── static/
│   └── style.css           # Premium Dark Theme CSS
└── templates/
    ├── formular.html       # Training eintragen (mit Typ-Auswahl-Cards)
    ├── bearbeiten.html     # Training bearbeiten
    ├── profil.html         # Nutzerprofil anlegen
    └── uebersicht.html     # Dashboard mit Stats, Diagramm, Bestleistungen
```

## Verwendete Formeln

**Kalorienverbrauch Laufen (ACSM-Formel)**
```
Geschwindigkeit (m/min) = Distanz (km) × 1000 / Dauer (min)
VO2 = 0.2 × Geschwindigkeit + 3.5
Kalorien/min = (VO2 × Gewicht) / 200
```

**Kalorienverbrauch Krafttraining (MET-basiert)**
```
Kalorien = MET (5.0) × Gewicht (kg) × Dauer (h)
```

## Installation & Setup

**Voraussetzungen:** Python 3.10+

```bash
# Repository klonen
git clone https://github.com/AminDhina/Trainings-Tracker.git
cd Trainings-Tracker

# Abhängigkeiten installieren
pip install -r requirements.txt

# Datenbank erstellen
python datenbank_setup.py

# Server starten
python app.py
```

Danach im Browser öffnen: `http://127.0.0.1:5000`

## Autor

**Amin Dhina** – Informatik-Student an der University of Applied Sciences in Frankfurt

[![GitHub](https://img.shields.io/badge/-AminDhina-181717?style=flat&logo=github&logoColor=white)](https://github.com/AminDhina)
