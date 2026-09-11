from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, date
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import sqlite3
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "trainings-tracker-geheim-2026")

# Flask-Login Setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Bitte melde dich an."


class User(UserMixin):
    def __init__(self, id, email, name, alter_jahre, gewicht_kg, profilbild, garmin_email, garmin_passwort):
        self.id = id
        self.email = email
        self.name = name
        self.alter_jahre = alter_jahre
        self.gewicht_kg = gewicht_kg
        self.profilbild = profilbild
        self.garmin_email = garmin_email
        self.garmin_passwort = garmin_passwort


@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect("trainings.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return User(row[0], row[1], row[3], row[4], row[5], row[6], row[7], row[8])
    return None
def pace_berechnen(dauer_minuten, distanz_km):
    pace_gesamt = dauer_minuten / distanz_km
    minuten = int(pace_gesamt)
    sekunden = round((pace_gesamt - minuten) * 60)
    return f"{minuten}:{sekunden:02d} min/km"


def kalorien_berechnen(dauer_minuten, distanz_km, gewicht_kg):
    """ACSM-Formel für Laufen"""
    geschwindigkeit_m_min = (distanz_km * 1000) / dauer_minuten
    vo2 = 0.2 * geschwindigkeit_m_min + 3.5
    kalorien_pro_minute = (vo2 * gewicht_kg) / 200
    return round(kalorien_pro_minute * dauer_minuten, 1)


def kalorien_krafttraining_berechnen(dauer_minuten, gewicht_kg):
    """MET-basierte Berechnung für Krafttraining"""
    met_wert = 5.0
    dauer_stunden = dauer_minuten / 60
    return round(met_wert * gewicht_kg * dauer_stunden, 1)

@app.route("/registrieren", methods=["GET", "POST"])
def registrieren():
    if request.method == "POST":
        email = request.form["email"]
        passwort = request.form["passwort"]
        passwort2 = request.form["passwort2"]
        name = request.form["name"]
        alter = request.form.get("alter_jahre")
        gewicht = request.form.get("gewicht_kg")

        if passwort != passwort2:
            flash("Passwörter stimmen nicht überein.", "error")
            return redirect("/registrieren")

        if len(passwort) < 6:
            flash("Passwort muss mindestens 6 Zeichen haben.", "error")
            return redirect("/registrieren")

        conn = sqlite3.connect("trainings.db")
        c = conn.cursor()

        c.execute("SELECT id FROM users WHERE email = ?", (email,))
        if c.fetchone():
            flash("Diese E-Mail ist bereits registriert.", "error")
            conn.close()
            return redirect("/registrieren")

        passwort_hash = generate_password_hash(passwort)
        c.execute("""
            INSERT INTO users (email, passwort_hash, name, alter_jahre, gewicht_kg)
            VALUES (?, ?, ?, ?, ?)
        """, (email, passwort_hash, name, alter, gewicht))
        conn.commit()

        user_id = c.lastrowid
        conn.close()

        user = User(user_id, email, name, alter, gewicht, None, None, None)
        login_user(user)

        flash(f"Willkommen, {name}!", "success")
        return redirect("/uebersicht")

    return render_template("registrieren.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        passwort = request.form["passwort"]

        conn = sqlite3.connect("trainings.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = c.fetchone()
        conn.close()

        if row and check_password_hash(row[2], passwort):
            user = User(row[0], row[1], row[3], row[4], row[5], row[6], row[7], row[8])
            login_user(user)
            return redirect("/uebersicht")
        else:
            flash("E-Mail oder Passwort falsch.", "error")
            return redirect("/login")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")

@app.route("/profil", methods=["GET", "POST"])
@login_required
def profil():
    if request.method == "POST":
        name = request.form["name"]
        alter = request.form.get("alter_jahre")
        gewicht = request.form.get("gewicht_kg")
        garmin_email = request.form.get("garmin_email")
        garmin_passwort = request.form.get("garmin_passwort")

        conn = sqlite3.connect("trainings.db")
        c = conn.cursor()
        c.execute("""
            UPDATE users SET name=?, alter_jahre=?, gewicht_kg=?, garmin_email=?, garmin_passwort=?
            WHERE id=?
        """, (name, alter, gewicht, garmin_email, garmin_passwort, current_user.id))
        conn.commit()
        conn.close()

        flash("Profil aktualisiert!", "success")
        return redirect("/profil")

    # Statistiken laden
    conn = sqlite3.connect("trainings.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM trainings WHERE user_id=?", (current_user.id,))
    total_trainings = c.fetchone()[0]
    c.execute("SELECT SUM(distanz_km) FROM trainings WHERE user_id=? AND art='Laufen'", (current_user.id,))
    total_km = c.fetchone()[0] or 0
    c.execute("SELECT SUM(dauer_minuten) FROM trainings WHERE user_id=?", (current_user.id,))
    total_minuten = c.fetchone()[0] or 0
    conn.close()

    return render_template("profil_seite.html",
        total_trainings=total_trainings,
        total_km=round(total_km, 1),
        total_stunden=round(total_minuten / 60, 1)
    )

@app.route("/")
@login_required
def formular_anzeigen():
    return render_template("formular.html")


@app.route("/training-hinzufuegen", methods=["POST"])
@login_required
def training_hinzufuegen():
    datum = request.form["datum"]
    art = request.form["art"]
    dauer = int(request.form["dauer_minuten"])
    distanz = request.form.get("distanz_km")
    notiz = request.form.get("notiz")

    pace = None
    kalorien = None
    gewicht = current_user.gewicht_kg or 70

    if art == "Laufen" and distanz:
        distanz = float(distanz)
        pace = pace_berechnen(dauer, distanz)
        kalorien = kalorien_berechnen(dauer, distanz, gewicht)
    elif art == "Krafttraining":
        distanz = None
        kalorien = kalorien_krafttraining_berechnen(dauer, gewicht)
    else:
        distanz = None

    conn = sqlite3.connect("trainings.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO trainings (datum, art, dauer_minuten, distanz_km, pace_min_km, kalorien, notiz, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (datum, art, dauer, distanz, pace, kalorien, notiz, current_user.id))

    training_id = c.lastrowid

    if art == "Krafttraining":
        namen = request.form.getlist("uebung_name")
        saetze_liste = request.form.getlist("uebung_saetze")
        wdh_liste = request.form.getlist("uebung_wiederholungen")
        gewicht_liste = request.form.getlist("uebung_gewicht")

        for name, saetze, wdh, uebungsgewicht in zip(namen, saetze_liste, wdh_liste, gewicht_liste):
            c.execute("""
                INSERT INTO uebungen (training_id, name, saetze, wiederholungen, gewicht_kg)
                VALUES (?, ?, ?, ?, ?)
            """, (training_id, name, int(saetze), int(wdh), float(uebungsgewicht)))

    conn.commit()
    conn.close()
    return redirect("/uebersicht")

@app.route("/uebersicht")
@login_required
def uebersicht_anzeigen():
    conn = sqlite3.connect("trainings.db")
    c = conn.cursor()
    c.execute("SELECT * FROM trainings WHERE user_id=? ORDER BY datum DESC", (current_user.id,))
    alle_trainings = c.fetchall()

    laufen_trainings = [t for t in alle_trainings if t[2] == "Laufen"]
    kraft_trainings = [t for t in alle_trainings if t[2] == "Krafttraining"]
    andere_trainings = [t for t in alle_trainings if t[2] not in ["Laufen", "Krafttraining"]]

    uebungen_dict = {}
    for t in alle_trainings:
        if t[2] == "Krafttraining":
            c.execute("SELECT name, saetze, wiederholungen, gewicht_kg FROM uebungen WHERE training_id = ?", (t[0],))
            uebungen_dict[t[0]] = c.fetchall()

    heute = datetime.now()
    vor_7_tagen = heute - timedelta(days=7)

    km_diese_woche = 0
    anzahl_diese_woche = 0
    kalorien_diese_woche = 0

    for t in alle_trainings:
        try:
            datum_training = datetime.strptime(t[1], "%Y-%m-%d")
            if datum_training >= vor_7_tagen:
                anzahl_diese_woche += 1
                if t[4]:
                    km_diese_woche += t[4]
                if t[6]:
                    kalorien_diese_woche += t[6]
        except:
            pass

    monatsnamen = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
                   "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
    monat_labels = []
    km_pro_monat = []
    anzahl_laeufe_pro_monat = []

    for i in range(11, -1, -1):
        jahr = heute.year
        monat = heute.month - i
        while monat <= 0:
            monat += 12
            jahr -= 1
        monat_str = f"{jahr}-{monat:02d}"
        monat_labels.append(f"{monatsnamen[monat - 1]} {jahr}")
        km_summe = sum(t[4] for t in laufen_trainings if t[1].startswith(monat_str) and t[4])
        anzahl = sum(1 for t in laufen_trainings if t[1].startswith(monat_str))
        km_pro_monat.append(round(km_summe, 1))
        anzahl_laeufe_pro_monat.append(anzahl)

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

    # Bestleistungen Laufen
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
            minuten_gesamt = bestzeit_training[3]
            stunden = minuten_gesamt // 60
            minuten = minuten_gesamt % 60
            zeit_str = f"{stunden}:{minuten:02d} h" if stunden > 0 else f"{minuten} min"
            bestzeiten[sd["name"]] = {"zeit": zeit_str, "datum": bestzeit_training[1], "pace": bestzeit_training[5]}

    laengste_dauer_kraft = None
    meiste_kalorien_kraft = None
    for t in kraft_trainings:
        if t[3] and (laengste_dauer_kraft is None or t[3] > laengste_dauer_kraft[3]):
            laengste_dauer_kraft = t
        if t[6] and (meiste_kalorien_kraft is None or t[6] > meiste_kalorien_kraft[6]):
            meiste_kalorien_kraft = t

    c.execute("""
        SELECT u.name, MAX(u.gewicht_kg) as max_gewicht, u.saetze, u.wiederholungen, t.datum
        FROM uebungen u
        JOIN trainings t ON u.training_id = t.id
        WHERE t.user_id = ?
        GROUP BY u.name ORDER BY max_gewicht DESC
    """, (current_user.id,))
    max_gewichte = c.fetchall()

    c.execute("SELECT * FROM gesundheit WHERE user_id=? ORDER BY datum DESC LIMIT 1", (current_user.id,))
    gesundheit = c.fetchone()

    conn.close()

    return render_template("uebersicht.html",
        laufen_trainings=laufen_trainings,
        kraft_trainings=kraft_trainings,
        andere_trainings=andere_trainings,
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
        gesundheit=gesundheit
    )

@app.route("/training-bearbeiten/<int:training_id>", methods=["GET"])
@login_required
def bearbeiten_formular_anzeigen(training_id):
    conn = sqlite3.connect("trainings.db")
    c = conn.cursor()
    c.execute("SELECT * FROM trainings WHERE id = ? AND user_id = ?", (training_id, current_user.id))
    training = c.fetchone()
    if not training:
        conn.close()
        return redirect("/uebersicht")
    c.execute("SELECT name, saetze, wiederholungen, gewicht_kg FROM uebungen WHERE training_id = ?", (training_id,))
    uebungen = c.fetchall()
    conn.close()
    return render_template("bearbeiten.html", t=training, uebungen=uebungen)


@app.route("/training-bearbeiten/<int:training_id>", methods=["POST"])
@login_required
def training_bearbeiten(training_id):
    datum = request.form["datum"]
    art = request.form["art"]
    dauer = int(request.form["dauer_minuten"])
    distanz = request.form.get("distanz_km")
    notiz = request.form.get("notiz")

    pace = None
    kalorien = None
    gewicht = current_user.gewicht_kg or 70

    if art == "Laufen" and distanz:
        distanz = float(distanz)
        pace = pace_berechnen(dauer, distanz)
        kalorien = kalorien_berechnen(dauer, distanz, gewicht)
    elif art == "Krafttraining":
        distanz = None
        kalorien = kalorien_krafttraining_berechnen(dauer, gewicht)
    else:
        distanz = None

    conn = sqlite3.connect("trainings.db")
    c = conn.cursor()
    c.execute("""
        UPDATE trainings SET datum=?, art=?, dauer_minuten=?, distanz_km=?, pace_min_km=?, kalorien=?, notiz=?
        WHERE id=? AND user_id=?
    """, (datum, art, dauer, distanz, pace, kalorien, notiz, training_id, current_user.id))

    c.execute("DELETE FROM uebungen WHERE training_id = ?", (training_id,))

    if art == "Krafttraining":
        namen = request.form.getlist("uebung_name")
        saetze_liste = request.form.getlist("uebung_saetze")
        wdh_liste = request.form.getlist("uebung_wiederholungen")
        gewicht_liste = request.form.getlist("uebung_gewicht")
        for name, saetze, wdh, uebungsgewicht in zip(namen, saetze_liste, wdh_liste, gewicht_liste):
            c.execute("INSERT INTO uebungen (training_id, name, saetze, wiederholungen, gewicht_kg) VALUES (?, ?, ?, ?, ?)",
                      (training_id, name, int(saetze), int(wdh), float(uebungsgewicht)))

    conn.commit()
    conn.close()
    return redirect("/uebersicht")


@app.route("/training-loeschen/<int:training_id>", methods=["POST"])
@login_required
def training_loeschen(training_id):
    conn = sqlite3.connect("trainings.db")
    c = conn.cursor()
    c.execute("DELETE FROM trainings WHERE id = ? AND user_id = ?", (training_id, current_user.id))
    conn.commit()
    conn.close()
    return redirect("/uebersicht")

@app.route("/garmin-sync")
@login_required
def garmin_sync():
    try:
        from garminconnect import Garmin

        g_email = current_user.garmin_email
        g_pass = current_user.garmin_passwort

        if not g_email or not g_pass:
            flash("Bitte hinterlege deine Garmin-Zugangsdaten im Profil.", "error")
            return redirect("/profil")

        client = Garmin(g_email, g_pass)
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

        conn = sqlite3.connect("trainings.db")
        c = conn.cursor()

        c.execute("DELETE FROM gesundheit WHERE datum=? AND user_id=?", (heute_str, current_user.id))
        c.execute("""
            INSERT INTO gesundheit (datum, schritte, ruhepuls, stress_level, body_battery, schlaf_dauer_min, schlaf_score, kalorien_gesamt, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (heute_str, stats.get('totalSteps'), stats.get('restingHeartRate'),
              stats.get('averageStressLevel'), stats.get('bodyBatteryMostRecentValue'),
              schlaf_dauer_min, schlaf_score, stats.get('totalKilocalories'), current_user.id))

        # Aktivitäten syncen
        aktivitaeten = client.get_activities(0, 20)
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
        gewicht = current_user.gewicht_kg or 70

        for a in aktivitaeten:
            garmin_id = str(a.get('activityId', ''))
            c.execute("SELECT id FROM trainings WHERE garmin_id = ? AND user_id = ?", (garmin_id, current_user.id))
            if c.fetchone():
                continue

            typ_key = a.get('activityType', {}).get('typeKey', 'other')
            art = typ_zuordnung.get(typ_key, typ_key.replace('_', ' ').title())
            dauer_min = round(a.get('duration', 0) / 60)
            distanz_km = round(a.get('distance', 0) / 1000, 2) if a.get('distance') else None
            avg_hr = a.get('averageHR')
            max_hr = a.get('maxHR')
            datum_a = a.get('startTimeLocal', '')[:10]
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

            c.execute("""
                INSERT INTO trainings (datum, art, dauer_minuten, distanz_km, pace_min_km, kalorien, notiz, garmin_id, avg_hr, max_hr, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (datum_a, art, dauer_min, distanz_km, pace, kalorien, name, garmin_id, avg_hr, max_hr, current_user.id))

        conn.commit()
        conn.close()
        flash("Garmin-Sync erfolgreich!", "success")
        return redirect("/uebersicht")

    except Exception as e:
        flash(f"Garmin-Sync Fehler: {e}", "error")
        return redirect("/uebersicht")

@app.route("/ki-coaching")
@login_required
def ki_coaching():
    import anthropic

    conn = sqlite3.connect("trainings.db")
    c = conn.cursor()

    heute_str = date.today().isoformat()
    c.execute("SELECT antwort FROM coaching WHERE datum=? AND user_id=?", (heute_str, current_user.id))
    bestehende = c.fetchone()

    if bestehende:
        c.execute("SELECT COUNT(*) FROM trainings WHERE user_id=?", (current_user.id,))
        count = c.fetchone()[0]
        conn.close()
        return render_template("coaching.html", antwort=bestehende[0], nutzer=current_user, letzte_trainings_count=count, aus_cache=True)

    c.execute("SELECT * FROM trainings WHERE user_id=? ORDER BY datum DESC LIMIT 15", (current_user.id,))
    letzte_trainings = c.fetchall()

    c.execute("SELECT * FROM gesundheit WHERE user_id=? ORDER BY datum DESC LIMIT 7", (current_user.id,))
    gesundheit_verlauf = c.fetchall()

    c.execute("SELECT MAX(distanz_km) FROM trainings WHERE art='Laufen' AND distanz_km IS NOT NULL AND user_id=?", (current_user.id,))
    max_distanz = c.fetchone()[0]
    c.execute("SELECT MIN(pace_min_km) FROM trainings WHERE art='Laufen' AND pace_min_km IS NOT NULL AND user_id=?", (current_user.id,))
    beste_pace = c.fetchone()[0]

    c.execute("""
        SELECT SUM(CASE WHEN art='Laufen' THEN distanz_km ELSE 0 END),
               COUNT(*), SUM(dauer_minuten),
               SUM(CASE WHEN art='Laufen' THEN 1 ELSE 0 END),
               SUM(CASE WHEN art='Krafttraining' THEN 1 ELSE 0 END)
        FROM trainings WHERE datum >= date('now', '-28 days') AND user_id=?
    """, (current_user.id,))
    volumen = c.fetchone()

    trainings_text = ""
    for t in letzte_trainings:
        trainings_text += f"- {t[1]}: {t[2]}, {t[3]} min"
        if t[4]: trainings_text += f", {t[4]} km"
        if t[5]: trainings_text += f", Pace {t[5]}"
        if t[6]: trainings_text += f", {round(t[6])} kcal"
        if t[9]: trainings_text += f", Ø HR {t[9]} bpm"
        trainings_text += "\n"

    gesundheit_text = ""
    for g in gesundheit_verlauf:
        schlaf_h = round(g[6]/60, 1) if g[6] else "?"
        gesundheit_text += f"- {g[1]}: Schritte {g[2]}, Ruhepuls {g[3]}, Stress {g[4]}, Body Battery {g[5]}, Schlaf {schlaf_h}h\n"

    prompt = f"""Du bist ein Sportwissenschaftler auf Profi-Niveau. Analysiere diese Athletendaten:

PROFIL: {current_user.name}, {current_user.alter_jahre} Jahre, {current_user.gewicht_kg} kg

LETZTE TRAININGS:
{trainings_text}

VOLUMEN (4 Wochen): {round(volumen[0],1) if volumen[0] else 0} km Laufen, {volumen[1] or 0} Einheiten, {volumen[2] or 0} min gesamt

BESTLEISTUNGEN: Max Distanz {max_distanz} km, Beste Pace {beste_pace}

GESUNDHEIT (7 Tage):
{gesundheit_text}

Analyse auf Deutsch: 1) Gesamtbewertung 2) Gesundheits-Check 3) Laufanalyse (80/20, VO2max-Schätzung) 4) Kraftanalyse 5) Regeneration 6) Wochenplan Mo-So 7) 3-6 Monats-Ziele. Konkret, datenbasiert, keine generischen Tipps."""

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    message = client.messages.create(model="claude-sonnet-4-6", max_tokens=3000,
                                     messages=[{"role": "user", "content": prompt}])
    antwort = message.content[0].text

    c.execute("INSERT INTO coaching (datum, antwort, user_id) VALUES (?, ?, ?)",
              (heute_str, antwort, current_user.id))
    conn.commit()
    conn.close()

    return render_template("coaching.html", antwort=antwort, nutzer=current_user,
                          letzte_trainings_count=len(letzte_trainings), aus_cache=False)


@app.route("/ki-coaching-neu")
@login_required
def ki_coaching_neu():
    conn = sqlite3.connect("trainings.db")
    c = conn.cursor()
    c.execute("DELETE FROM coaching WHERE datum=? AND user_id=?", (date.today().isoformat(), current_user.id))
    conn.commit()
    conn.close()
    return redirect("/ki-coaching")


@app.route('/static/service-worker.js')
def service_worker():
    return app.send_static_file('service-worker.js')


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')

