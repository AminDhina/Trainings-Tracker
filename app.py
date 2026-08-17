from flask import Flask, render_template, request, redirect
from  datetime import datetime, timedelta
import sqlite3

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
        max_gewichte=max_gewichte
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


if __name__ == "__main__":
    app.run(debug=True)