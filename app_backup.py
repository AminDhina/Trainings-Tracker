from flask import Flask, render_template, request, redirect
from  datetime import datetime, timedelta
import sqlite3
from dotenv import load_dotenv
import os
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

app = Flask(__name__)

def hat_nutzer_profil():
    verbindung = sqlite3.connect("trainings.db")
    cursor = verbindung.cursor()
    cursor.execute("SELECT COUNT(*) FROM nutzer")
    anzahl = cursor.fetchone()[0]
    verbindung.close()
    return anzahl > 0

def gewicht_holen():
    verbindung = sqlite3.connect("trainings.db")
    cursor = verbindung.cursor()
    cursor.execute("SELECT gewicht_kg FROM nutzer LIMIT 1")
    ergebnis = cursor.fetchone()
    verbindung.close()
    return ergebnis[0]

def pace_berechnen(dauer_minuten, distanz_km):
    # Pace = Minuten pro Kilometer
    pace_gesamt = dauer_minuten / distanz_km
    minuten = int(pace_gesamt)
    sekunden = round((pace_gesamt - minuten) * 60)
    return f"{minuten}:{sekunden:02d} min/km"

def kalorien_berechnen(dauer_minuten, distanz_km, gewicht_kg):
    # ACSM-Formel für Laufen (wissenschaftlich anerkannte Schätzung)
    geschwindigkeit_m_min = (distanz_km * 1000) / dauer_minuten
    vo2 = 0.2 * geschwindigkeit_m_min + 3.5  # Sauerstoffverbrauch
    kalorien_pro_minute = (vo2 * gewicht_kg) / 200
    return round(kalorien_pro_minute * dauer_minuten, 1)

def kalorien_krafttraining_berechnen(dauer_minuten, gewicht_kg):
    """
    Schätzt den Kalorienverbrauch beim Krafttraining mithilfe des MET-Werts
    (Metabolic Equivalent of Task). MET 5.0 entspricht moderate bis intensivem
    Krafttraining laut gängigen Bewegungs-Kompendien.
    """
    met_wert = 5.0
    dauer_stunden = dauer_minuten / 60
    return round(met_wert * gewicht_kg * dauer_stunden, 1)

@app.route("/")
def formular_anzeigen():
    if not hat_nutzer_profil():
        return redirect("/profil")
    return render_template("formular.html")

@app.route("/profil")
def profil_anzeigen():
    return render_template("profil.html")

@app.route("/profil-anlegen", methods=["POST"])
def profil_anlegen():
    name = request.form["name"]
    alter = request.form["alter_jahre"]
    gewicht = request.form["gewicht_kg"]

    verbindung = sqlite3.connect("trainings.db")
    cursor = verbindung.cursor()
    cursor.execute("INSERT INTO nutzer (name, alter_jahre, gewicht_kg) VALUES (?, ?, ?)",
                   (name, alter, gewicht))
    verbindung.commit()
    verbindung.close()

    return redirect("/")

@app.route("/training-hinzufuegen", methods=["POST"])
def training_hinzufuegen():
    datum = request.form["datum"]
    art = request.form["art"]
    dauer = int(request.form["dauer_minuten"])
    distanz = request.form.get("distanz_km")
    notiz = request.form.get("notiz")

    pace = None
    kalorien = None
    gewicht = gewicht_holen()

    if art == "Laufen" and distanz:
        distanz = float(distanz)
        pace = pace_berechnen(dauer, distanz)
        kalorien = kalorien_berechnen(dauer, distanz, gewicht)
    elif art == "Krafttraining":
        distanz = None
        kalorien = kalorien_krafttraining_berechnen(dauer, gewicht)
    else:
        distanz = None

    verbindung = sqlite3.connect("trainings.db")
    cursor = verbindung.cursor()
    cursor.execute("""
        INSERT INTO trainings (datum, art, dauer_minuten, distanz_km, pace_min_km, kalorien, notiz)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (datum, art, dauer, distanz, pace, kalorien, notiz))

    training_id = cursor.lastrowid

    # Falls Krafttraining: einzelne Übungen speichern
    if art == "Krafttraining":
        namen = request.form.getlist("uebung_name")
        saetze_liste = request.form.getlist("uebung_saetze")
        wdh_liste = request.form.getlist("uebung_wiederholungen")
        gewicht_liste = request.form.getlist("uebung_gewicht")

        for name, saetze, wdh, uebungsgewicht in zip(namen, saetze_liste, wdh_liste, gewicht_liste):
            cursor.execute("""
                INSERT INTO uebungen (training_id, name, saetze, wiederholungen, gewicht_kg)
                VALUES (?, ?, ?, ?, ?)
            """, (training_id, name, int(saetze), int(wdh), float(uebungsgewicht)))

    verbindung.commit()
    verbindung.close()

    return redirect("/")

from datetime import datetime, timedelta

@app.route("/uebersicht")
def uebersicht_anzeigen():
    verbindung = sqlite3.connect("trainings.db")
    cursor = verbindung.cursor()
    cursor.execute("SELECT * FROM trainings ORDER BY datum DESC")
    alle_trainings = cursor.fetchall()

    # Übungen pro Krafttraining laden
    uebungen_dict = {}
    for t in alle_trainings:
        if t[2] == "Krafttraining":
            cursor.execute("SELECT name, saetze, wiederholungen, gewicht_kg FROM uebungen WHERE training_id = ?", (t[0],))
            uebungen_dict[t[0]] = cursor.fetchall()

    verbindung.close()

    # Trainings nach Art aufteilen
    laufen_trainings = [t for t in alle_trainings if t[2] == "Laufen"]
    kraft_trainings = [t for t in alle_trainings if t[2] == "Krafttraining"]
    andere_trainings = [t for t in alle_trainings if t[2] not in ["Laufen", "Krafttraining"]]

    # Wochenstatistik berechnen (letzte 7 Tage, über alle Trainings)
    heute = datetime.now()
    vor_7_tagen = heute - timedelta(days=7)

    km_diese_woche = 0
    anzahl_diese_woche = 0
    kalorien_diese_woche = 0

    for t in alle_trainings:
        datum_training = datetime.strptime(t[1], "%Y-%m-%d")
        if datum_training >= vor_7_tagen:
            anzahl_diese_woche += 1
            if t[4]:
                km_diese_woche += t[4]
            if t[6]:
                kalorien_diese_woche += t[6]

    # Daten für das Monats-Diagramm vorbereiten (letzte 12 Monate, Laufen)
    monat_labels = []
    km_pro_monat = []
    anzahl_laeufe_pro_monat = []

    monatsnamen = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
                   "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]

    for i in range(11, -1, -1):
        jahr = heute.year
        monat = heute.month - i
        while monat <= 0:
            monat += 12
            jahr -= 1

        monat_str = f"{jahr}-{monat:02d}"  # wird weiterhin für den Datenbank-Vergleich gebraucht
        monat_label = f"{monatsnamen[monat - 1]} {jahr}"  # z.B. "Aug 2026"
        monat_labels.append(monat_label)

        km_summe = sum(t[4] for t in laufen_trainings if t[1].startswith(monat_str) and t[4])
        anzahl = sum(1 for t in laufen_trainings if t[1].startswith(monat_str))

        km_pro_monat.append(round(km_summe, 1))
        anzahl_laeufe_pro_monat.append(anzahl)

    # Daten für die Wochenansicht vorbereiten (aktuelle Kalenderwoche, Montag bis Sonntag)
    wochentage_namen = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    woche_labels = []
    km_pro_tag = []

    montag_dieser_woche = heute - timedelta(days=heute.weekday())

    for i in range(7):
        tag = montag_dieser_woche + timedelta(days=i)
        tag_str = tag.strftime("%Y-%m-%d")
        woche_labels.append(wochentage_namen[tag.weekday()])

        km_summe = sum(t[4] for t in laufen_trainings if t[1] == tag_str and t[4])
        km_pro_tag.append(round(km_summe, 1))

    # ===== BESTLEISTUNGEN BERECHNEN =====

    # --- Laufen: Allgemeine Rekorde ---
    laengste_distanz = None
    beste_pace = None
    laengste_dauer_laufen = None
    meiste_kalorien_laufen = None

    for t in laufen_trainings:
        if t[4] and (laengste_distanz is None or t[4] > laengste_distanz[4]):
            laengste_distanz = t
        if t[5] and (beste_pace is None or t[5] < beste_pace[5]):
            beste_pace = t
        if t[3] and (laengste_dauer_laufen is None or t[3] > laengste_dauer_laufen[3]):
            laengste_dauer_laufen = t
        if t[6] and (meiste_kalorien_laufen is None or t[6] > meiste_kalorien_laufen[6]):
            meiste_kalorien_laufen = t

    # --- Laufen: Bestzeiten über Standarddistanzen ---
    standard_distanzen = [
        {"name": "5 km", "min": 4.8, "max": 5.2},
        {"name": "10 km", "min": 9.5, "max": 10.5},
        {"name": "Halbmarathon", "min": 20.5, "max": 21.5},
        {"name": "Marathon", "min": 41.0, "max": 42.5}
    ]

    bestzeiten = {}
    for sd in standard_distanzen:
        bestzeit_training = None
        for t in laufen_trainings:
            if t[4] and sd["min"] <= t[4] <= sd["max"]:
                if bestzeit_training is None or t[3] < bestzeit_training[3]:
                    bestzeit_training = t
        if bestzeit_training:
            # Dauer in Stunden:Minuten:Sekunden formatieren
            minuten_gesamt = bestzeit_training[3]
            stunden = minuten_gesamt // 60
            minuten = minuten_gesamt % 60
            if stunden > 0:
                zeit_str = f"{stunden}:{minuten:02d} h"
            else:
                zeit_str = f"{minuten} min"
            bestzeiten[sd["name"]] = {
                "zeit": zeit_str,
                "datum": bestzeit_training[1],
                "pace": bestzeit_training[5]
            }

    # --- Krafttraining: Rekorde ---
    laengste_dauer_kraft = None
    meiste_kalorien_kraft = None

    for t in kraft_trainings:
        if t[3] and (laengste_dauer_kraft is None or t[3] > laengste_dauer_kraft[3]):
            laengste_dauer_kraft = t
        if t[6] and (meiste_kalorien_kraft is None or t[6] > meiste_kalorien_kraft[6]):
            meiste_kalorien_kraft = t

    # --- Krafttraining: Max-Gewicht pro Übung ---
    verbindung = sqlite3.connect("trainings.db")
    cursor = verbindung.cursor()
    cursor.execute("""
        SELECT u.name, MAX(u.gewicht_kg) as max_gewicht, u.saetze, u.wiederholungen, t.datum
        FROM uebungen u
        JOIN trainings t ON u.training_id = t.id
        GROUP BY u.name
        ORDER BY max_gewicht DESC
    """)
    max_gewichte = cursor.fetchall()
    verbindung.close()

        # Garmin Gesundheitsdaten für heute laden
    verbindung_g = sqlite3.connect("trainings.db")
    cursor_g = verbindung_g.cursor()
    cursor_g.execute("SELECT * FROM gesundheit ORDER BY datum DESC LIMIT 1")
    gesundheit = cursor_g.fetchone()
    verbindung_g.close()

    return render_template(
        "uebersicht.html",
        laufen_trainings=laufen_trainings,
        kraft_trainings=kraft_trainings,
        uebungen_dict=uebungen_dict,
        km_diese_woche=round(km_diese_woche, 1),
        anzahl_diese_woche=anzahl_diese_woche,
        kalorien_diese_woche=round(kalorien_diese_woche),
        monat_labels=monat_labels,
        km_pro_monat=km_pro_monat,
        anzahl_laeufe_pro_monat=anzahl_laeufe_pro_monat,
        woche_labels=woche_labels,
        km_pro_tag=km_pro_tag,
        laengste_distanz=laengste_distanz,
        beste_pace=beste_pace,
        laengste_dauer_laufen=laengste_dauer_laufen,
        meiste_kalorien_laufen=meiste_kalorien_laufen,
        bestzeiten=bestzeiten,
        standard_distanzen=standard_distanzen,
        laengste_dauer_kraft=laengste_dauer_kraft,
        meiste_kalorien_kraft=meiste_kalorien_kraft,
        max_gewichte=max_gewichte,
        andere_trainings=andere_trainings,
        gesundheit=gesundheit
    )
    
@app.route("/training-bearbeiten/<int:training_id>", methods=["GET"])
def bearbeiten_formular_anzeigen(training_id):
    verbindung = sqlite3.connect("trainings.db")
    cursor = verbindung.cursor()
    cursor.execute("SELECT * FROM trainings WHERE id = ?", (training_id,))
    training = cursor.fetchone()

    cursor.execute("SELECT name, saetze, wiederholungen, gewicht_kg FROM uebungen WHERE training_id = ?", (training_id,))
    uebungen = cursor.fetchall()
    verbindung.close()

    return render_template("bearbeiten.html", t=training, uebungen=uebungen)

@app.route("/training-bearbeiten/<int:training_id>", methods=["POST"])
def training_bearbeiten(training_id):
    datum = request.form["datum"]
    art = request.form["art"]
    dauer = int(request.form["dauer_minuten"])
    distanz = request.form.get("distanz_km")
    notiz = request.form.get("notiz")

    pace = None
    kalorien = None
    gewicht = gewicht_holen()

    if art == "Laufen" and distanz:
        distanz = float(distanz)
        pace = pace_berechnen(dauer, distanz)
        kalorien = kalorien_berechnen(dauer, distanz, gewicht)
    elif art == "Krafttraining":
        distanz = None
        kalorien = kalorien_krafttraining_berechnen(dauer, gewicht)
    else:
        distanz = None

    verbindung = sqlite3.connect("trainings.db")
    cursor = verbindung.cursor()
    cursor.execute("""
        UPDATE trainings
        SET datum = ?, art = ?, dauer_minuten = ?, distanz_km = ?, pace_min_km = ?, kalorien = ?, notiz = ?
        WHERE id = ?
    """, (datum, art, dauer, distanz, pace, kalorien, notiz, training_id))

    # Alte Übungen löschen und neue speichern
    cursor.execute("DELETE FROM uebungen WHERE training_id = ?", (training_id,))

    if art == "Krafttraining":
        namen = request.form.getlist("uebung_name")
        saetze_liste = request.form.getlist("uebung_saetze")
        wdh_liste = request.form.getlist("uebung_wiederholungen")
        gewicht_liste = request.form.getlist("uebung_gewicht")

        for name, saetze, wdh, uebungsgewicht in zip(namen, saetze_liste, wdh_liste, gewicht_liste):
            cursor.execute("""
                INSERT INTO uebungen (training_id, name, saetze, wiederholungen, gewicht_kg)
                VALUES (?, ?, ?, ?, ?)
            """, (training_id, name, int(saetze), int(wdh), float(uebungsgewicht)))

    verbindung.commit()
    verbindung.close()

    return redirect("/uebersicht")

@app.route("/training-loeschen/<int:training_id>", methods=["POST"])
def training_loeschen(training_id):
    verbindung = sqlite3.connect("trainings.db")
    cursor = verbindung.cursor()
    cursor.execute("DELETE FROM trainings WHERE id = ?", (training_id,))
    verbindung.commit()
    verbindung.close()

    return redirect("/uebersicht")

@app.route('/static/service-worker.js')
def service_worker():
    return app.send_static_file('service-worker.js')

@app.route("/garmin-sync")
def garmin_sync():
    try:
        from garminconnect import Garmin
        from datetime import date

        email = os.getenv("GARMIN_EMAIL")
        passwort = os.getenv("GARMIN_PASSWORT")

        client = Garmin(email, passwort)
        client.login()

        heute_str = date.today().isoformat()

        # Tägliche Stats abrufen
        stats = client.get_stats_and_body(heute_str)
        
        # Schlaf abrufen
        schlaf = client.get_sleep_data(heute_str)
        schlaf_dauer_min = None
        schlaf_score = None
        if schlaf:
            schlaf_daten = schlaf.get('dailySleepDTO', {})
            schlaf_sekunden = schlaf_daten.get('sleepTimeSeconds', 0)
            if schlaf_sekunden:
                schlaf_dauer_min = schlaf_sekunden // 60
            scores = schlaf_daten.get('sleepScores', {})
            if scores:
                schlaf_score = scores.get('overall', {}).get('value')

        # In Datenbank speichern
        verbindung = sqlite3.connect("trainings.db")
        cursor = verbindung.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO gesundheit 
            (datum, schritte, ruhepuls, stress_level, body_battery, schlaf_dauer_min, schlaf_score, kalorien_gesamt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            heute_str,
            stats.get('totalSteps'),
            stats.get('restingHeartRate'),
            stats.get('averageStressLevel'),
            stats.get('bodyBatteryMostRecentValue'),
            schlaf_dauer_min,
            schlaf_score,
            stats.get('totalKilocalories')
        ))

                # ===== AKTIVITÄTEN SYNC (letzte 20) =====
        aktivitaeten = client.get_activities(0, 20)

        typ_zuordnung = {
            'running': 'Laufen',
            'trail_running': 'Laufen',
            'treadmill_running': 'Laufen',
            'track_running': 'Laufen',
            'strength_training': 'Krafttraining',
            'cycling': 'Radfahren',
            'indoor_cycling': 'Radfahren',
            'mountain_biking': 'Radfahren',
            'gravel_cycling': 'Radfahren',
            'swimming': 'Schwimmen',
            'pool_swimming': 'Schwimmen',
            'open_water_swimming': 'Schwimmen',
            'walking': 'Gehen',
            'hiking': 'Wandern',
            'yoga': 'Yoga',
            'pilates': 'Pilates',
            'elliptical': 'Crosstrainer',
            'stair_climbing': 'Treppensteigen',
            'indoor_cardio': 'Cardio',
            'cardio': 'Cardio',
            'breathwork': 'Atemübung',
            'meditation': 'Meditation',
            'other': 'Sonstiges'
        }

        distanz_typen = ['Laufen', 'Radfahren', 'Schwimmen', 'Wandern', 'Gehen']

        gewicht = gewicht_holen()

        for a in aktivitaeten:
            garmin_id = str(a.get('activityId', ''))

            cursor.execute("SELECT id FROM trainings WHERE garmin_id = ?", (garmin_id,))
            if cursor.fetchone():
                continue

            typ_key = a.get('activityType', {}).get('typeKey', 'other')
            art = typ_zuordnung.get(typ_key, typ_key.replace('_', ' ').title())

            dauer_min = round(a.get('duration', 0) / 60)
            distanz_km = round(a.get('distance', 0) / 1000, 2) if a.get('distance') else None
            avg_hr = a.get('averageHR')
            max_hr = a.get('maxHR')
            datum = a.get('startTimeLocal', '')[:10]
            name = a.get('activityName', '')

            pace = None
            kalorien = None

            if art in distanz_typen and distanz_km and distanz_km > 0 and dauer_min > 0:
                pace = pace_berechnen(dauer_min, distanz_km)

            if art == "Laufen" and distanz_km and distanz_km > 0 and dauer_min > 0:
                kalorien = kalorien_berechnen(dauer_min, distanz_km, gewicht)
            elif art == "Krafttraining":
                kalorien = kalorien_krafttraining_berechnen(dauer_min, gewicht)
            elif a.get('calories'):
                kalorien = a.get('calories')

            cursor.execute("""
                INSERT INTO trainings (datum, art, dauer_minuten, distanz_km, pace_min_km, kalorien, notiz, garmin_id, avg_hr, max_hr)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (datum, art, dauer_min, distanz_km, pace, kalorien, name, garmin_id, avg_hr, max_hr))
        verbindung.commit()
        verbindung.close()

        return redirect("/uebersicht")

    except Exception as e:
        return f"Garmin-Sync Fehler: {e}", 500

@app.route("/ki-coaching")
def ki_coaching():
    import anthropic

    verbindung = sqlite3.connect("trainings.db")
    cursor = verbindung.cursor()

    cursor.execute("SELECT * FROM nutzer LIMIT 1")
    nutzer = cursor.fetchone()

    cursor.execute("SELECT * FROM trainings ORDER BY datum DESC LIMIT 15")
    letzte_trainings = cursor.fetchall()

    cursor.execute("SELECT * FROM gesundheit ORDER BY datum DESC LIMIT 7")
    gesundheit_verlauf = cursor.fetchall()

    cursor.execute("SELECT MAX(distanz_km) FROM trainings WHERE art='Laufen' AND distanz_km IS NOT NULL")
    max_distanz = cursor.fetchone()[0]
    cursor.execute("SELECT MIN(pace_min_km) FROM trainings WHERE art='Laufen' AND pace_min_km IS NOT NULL")
    beste_pace = cursor.fetchone()[0]

    cursor.execute("""
        SELECT SUM(CASE WHEN art='Laufen' THEN distanz_km ELSE 0 END),
               COUNT(*), SUM(dauer_minuten),
               SUM(CASE WHEN art='Laufen' THEN 1 ELSE 0 END),
               SUM(CASE WHEN art='Krafttraining' THEN 1 ELSE 0 END)
        FROM trainings WHERE datum >= date('now', '-28 days')
    """)
    volumen = cursor.fetchone()

    cursor.execute("""
        SELECT u.name, MAX(u.gewicht_kg), u.saetze, u.wiederholungen
        FROM uebungen u GROUP BY u.name ORDER BY MAX(u.gewicht_kg) DESC LIMIT 5
    """)
    top_uebungen = cursor.fetchall()

    verbindung.close()

    # Trainings formatieren
    trainings_text = ""
    for t in letzte_trainings:
        trainings_text += f"- {t[1]}: {t[2]}, {t[3]} min"
        if t[4]: trainings_text += f", {t[4]} km"
        if t[5]: trainings_text += f", Pace {t[5]}"
        if t[6]: trainings_text += f", {round(t[6])} kcal"
        if t[9]: trainings_text += f", Ø HR {t[9]} bpm"
        if t[10]: trainings_text += f", Max HR {t[10]} bpm"
        if t[7]: trainings_text += f" ({t[7]})"
        trainings_text += "\n"

    # Gesundheitsverlauf formatieren
    gesundheit_text = ""
    for g in gesundheit_verlauf:
        schlaf_h = round(g[6]/60, 1) if g[6] else "?"
        gesundheit_text += f"- {g[1]}: Schritte {g[2]}, Ruhepuls {g[3]} bpm, Stress {g[4]}, Body Battery {g[5]}, Schlaf {schlaf_h}h (Score {g[7]})\n"

    # Top Kraftübungen formatieren
    kraft_text = ""
    for u in top_uebungen:
        kraft_text += f"- {u[0]}: Max {u[1]} kg ({u[2]}×{u[3]})\n"

    prompt = f"""Du bist ein Sportwissenschaftler mit Expertise in Trainingssteuerung, Regeneration und Leistungsdiagnostik. Du arbeitest auf dem Niveau eines Trainers im Profisport. Analysiere die folgenden echten Athletendaten und erstelle eine umfassende, personalisierte Trainingsanalyse.

ATHLETENPROFIL:
- Name: {nutzer[1] if nutzer else 'Unbekannt'}
- Alter: {nutzer[2] if nutzer else '?'} Jahre
- Gewicht: {nutzer[3] if nutzer else '?'} kg

LETZTE 15 TRAININGSEINHEITEN:
{trainings_text}

TRAININGSVOLUMEN (letzte 4 Wochen):
- Lauf-Kilometer gesamt: {round(volumen[0], 1) if volumen[0] else 0} km
- Gesamte Einheiten: {volumen[1] if volumen[1] else 0} (davon {volumen[3] if volumen[3] else 0} Laufen, {volumen[4] if volumen[4] else 0} Kraft)
- Gesamte Trainingsdauer: {volumen[2] if volumen[2] else 0} Minuten

BESTLEISTUNGEN:
- Längste Laufdistanz: {max_distanz if max_distanz else 'Keine Daten'} km
- Beste Pace: {beste_pace if beste_pace else 'Keine Daten'}

TOP KRAFTÜBUNGEN (nach Maximalgewicht):
{kraft_text if kraft_text else 'Noch keine Übungen erfasst'}

GESUNDHEITSDATEN DER LETZTEN 7 TAGE (Garmin):
{gesundheit_text if gesundheit_text else 'Keine Garmin-Daten vorhanden'}

Erstelle eine umfassende Analyse auf höchstem sportwissenschaftlichem Niveau. Geh auf folgende Punkte ein:

1. GESAMTBEWERTUNG
Bewerte den aktuellen Fitnesszustand, das Trainingsvolumen und die Trainingsbalance (Verhältnis Ausdauer zu Kraft). Vergleiche mit Referenzwerten für das Alter und Fitnesslevel.

2. GESUNDHEITS-CHECK
Analysiere die Garmin-Gesundheitsdaten: Ist der Ruhepuls im gesunden Bereich? Sind Schlafqualität und -dauer optimal für die Trainingsbelastung? Gibt es Anzeichen von Übertraining (steigender Ruhepuls, sinkende Body Battery, erhöhter Stress)?

3. LAUFANALYSE
Bewerte die Pace-Entwicklung, das Wochenvolumen und die Intensitätsverteilung. Empfehle eine optimale Aufteilung nach der 80/20-Regel (80% lockere Läufe, 20% intensive Einheiten). Schätze die aktuelle VO2max und Laktatschwelle basierend auf den Pace-Daten.

4. KRAFTTRAINING-ANALYSE
Bewerte die Übungsauswahl, das Volumen und die Progression. Fehlen wichtige Muskelgruppen? Stimmt das Verhältnis von Push/Pull/Beine?

5. REGENERATION & RECOVERY
Basierend auf den Gesundheitsdaten: Wie gut erholt sich der Athlet? Empfehlungen für Schlaf, Ernährung und aktive Regeneration.

6. WOCHENPLAN-EMPFEHLUNG
Erstelle einen konkreten Trainingsplan für die nächste Woche (Mo-So) basierend auf dem aktuellen Zustand. Berücksichtige Belastung und Erholung.

7. LANGFRIST-STRATEGIE
Wo kann der Athlet in 3-6 Monaten stehen, wenn er optimal trainiert? Setze realistische Leistungsziele.

Antworte auf Deutsch. Sei direkt, konkret und nutze die echten Daten. Keine generischen Tipps – alles muss auf die vorhandenen Daten bezogen sein."""

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    antwort = message.content[0].text

    return render_template("coaching.html", antwort=antwort, nutzer=nutzer, letzte_trainings_count=len(letzte_trainings))

def auto_garmin_sync():
    """Wird alle 30 Minuten automatisch ausgeführt"""
    try:
        from garminconnect import Garmin
        from datetime import date

        email = os.getenv("GARMIN_EMAIL")
        passwort = os.getenv("GARMIN_PASSWORT")
        if not email or not passwort:
            return

        client = Garmin(email, passwort)
        client.login()

        heute_str = date.today().isoformat()

        stats = client.get_stats_and_body(heute_str)

        schlaf = client.get_sleep_data(heute_str)
        schlaf_dauer_min = None
        schlaf_score = None
        if schlaf:
            schlaf_daten = schlaf.get('dailySleepDTO', {})
            schlaf_sekunden = schlaf_daten.get('sleepTimeSeconds', 0)
            if schlaf_sekunden:
                schlaf_dauer_min = schlaf_sekunden // 60
            scores = schlaf_daten.get('sleepScores', {})
            if scores:
                schlaf_score = scores.get('overall', {}).get('value')

        verbindung = sqlite3.connect("trainings.db")
        cursor = verbindung.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO gesundheit
            (datum, schritte, ruhepuls, stress_level, body_battery, schlaf_dauer_min, schlaf_score, kalorien_gesamt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            heute_str,
            stats.get('totalSteps'),
            stats.get('restingHeartRate'),
            stats.get('averageStressLevel'),
            stats.get('bodyBatteryMostRecentValue'),
            schlaf_dauer_min,
            schlaf_score,
            stats.get('totalKilocalories')
        ))

        # Aktivitäten syncen
        aktivitaeten = client.get_activities(0, 10)

        typ_zuordnung = {
            'running': 'Laufen', 'trail_running': 'Laufen',
            'treadmill_running': 'Laufen', 'track_running': 'Laufen',
            'strength_training': 'Krafttraining',
            'cycling': 'Radfahren', 'indoor_cycling': 'Radfahren',
            'mountain_biking': 'Radfahren', 'gravel_cycling': 'Radfahren',
            'swimming': 'Schwimmen', 'pool_swimming': 'Schwimmen',
            'open_water_swimming': 'Schwimmen',
            'walking': 'Gehen', 'hiking': 'Wandern',
            'yoga': 'Yoga', 'pilates': 'Pilates',
            'elliptical': 'Crosstrainer', 'indoor_cardio': 'Cardio',
            'cardio': 'Cardio', 'other': 'Sonstiges'
        }
        distanz_typen = ['Laufen', 'Radfahren', 'Schwimmen', 'Wandern', 'Gehen']
        gewicht = gewicht_holen()

        for a in aktivitaeten:
            garmin_id = str(a.get('activityId', ''))
            cursor.execute("SELECT id FROM trainings WHERE garmin_id = ?", (garmin_id,))
            if cursor.fetchone():
                continue

            typ_key = a.get('activityType', {}).get('typeKey', 'other')
            art = typ_zuordnung.get(typ_key, typ_key.replace('_', ' ').title())
            dauer_min = round(a.get('duration', 0) / 60)
            distanz_km = round(a.get('distance', 0) / 1000, 2) if a.get('distance') else None
            avg_hr = a.get('averageHR')
            max_hr = a.get('maxHR')
            datum = a.get('startTimeLocal', '')[:10]
            name = a.get('activityName', '')

            pace = None
            kalorien = None

            if art in distanz_typen and distanz_km and distanz_km > 0 and dauer_min > 0:
                pace = pace_berechnen(dauer_min, distanz_km)
            if art == "Laufen" and distanz_km and distanz_km > 0 and dauer_min > 0:
                kalorien = kalorien_berechnen(dauer_min, distanz_km, gewicht)
            elif art == "Krafttraining":
                kalorien = kalorien_krafttraining_berechnen(dauer_min, gewicht)
            elif a.get('calories'):
                kalorien = a.get('calories')

            cursor.execute("""
                INSERT INTO trainings (datum, art, dauer_minuten, distanz_km, pace_min_km, kalorien, notiz, garmin_id, avg_hr, max_hr)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (datum, art, dauer_min, distanz_km, pace, kalorien, name, garmin_id, avg_hr, max_hr))

        verbindung.commit()
        verbindung.close()
        print(f"✅ Auto-Sync erfolgreich: {heute_str}")

    except Exception as e:
        print(f"⚠️ Auto-Sync Fehler: {e}")

if __name__ == "__main__":
    # Auto-Sync Scheduler starten
    scheduler = BackgroundScheduler()
    scheduler.add_job(auto_garmin_sync, 'interval', minutes=30)
    scheduler.start()
    print("📡 Auto-Sync gestartet (alle 30 Minuten)")

    # Einmal direkt beim Start syncen
    auto_garmin_sync()

    app.run(debug=True, host='0.0.0.0', use_reloader=False)