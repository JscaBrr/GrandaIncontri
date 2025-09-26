# filename: app.py

# =============================================================================
# IMPORT E CONFIGURAZIONE BASE
# =============================================================================
import os
import datetime
import random
#import smtplib
from functools import wraps
from types import SimpleNamespace
from email.message import EmailMessage
import re
import html as ihtml
# sostituisci l'uso di smtplib per l'invio
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email



from flask import (
    Flask, render_template, request, redirect, url_for, session, flash
)

import profiles_dao

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # disattiva cache statici in dev
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "7cfd9f2e6b3d41a8a3e1f59c64b95d76")

# =============================================================================
# CONFIGURAZIONE SMTP
# =============================================================================
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
MAIL_FROM = os.getenv("MAIL_FROM", SMTP_USERNAME or "no-reply@localhost")
MAIL_TO = os.getenv("MAIL_TO", "sito@grandaincontri.com")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

# =============================================================================
# SICUREZZA SEMPLICE (PASSCODE)
# =============================================================================
ADMIN_PASSCODE = os.getenv("ADMIN_PASSCODE", "0990")

# =============================================================================
# UTILITY: PROFILI PUBBLICATI
# =============================================================================
def get_published_profiles_with_status():
    rows = profiles_dao.get_all_profiles()

    def is_published(val):
        if val is None:
            return True
        if isinstance(val, (int, bool)):
            return bool(val)
        return str(val).strip().lower() not in ("0", "false", "no", "n")

    list_profiles = []
    for r in rows:
        keys = r.keys() if hasattr(r, "keys") else r.keys()
        val = r["is_active"] if ("is_active" in keys) else None
        if is_published(val):
            profile = {k: r[k] for k in keys}
            # Flag decorativo solo per lo slider "chi è online ora"
            profile["is_online"] = random.choice([True, False])
            list_profiles.append(profile)
    return list_profiles

# =============================================================================
# CONTEXT PROCESSOR: CURRENT USER FINTO
# =============================================================================
@app.context_processor
def inject_current_user():
    class CurrentUserStub:
        def __init__(self, is_auth, role="admin"):
            self.is_authenticated = is_auth
            self.role = role
    return dict(current_user=CurrentUserStub(session.get("is_authenticated", False)))

# =============================================================================
# DECORATOR: PROTEZIONE ROTTE RISERVATE
# =============================================================================
def require_auth(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("is_authenticated"):
            flash("Devi inserire il codice per accedere.", "warning")
            return redirect(url_for("accedi"))
        return view_func(*args, **kwargs)
    return wrapper

# =============================================================================
# ROTTE PUBBLICHE: HOME, CHI SIAMO, PROFILO
# =============================================================================
@app.route("/")
def home():
    listObjProfiles = get_published_profiles_with_status()

    def norm_gender(p):
        return (p.get("gender") or "").strip().lower()

    available_women_count = sum(
        1 for p in listObjProfiles if norm_gender(p) in ("female", "f", "donna")
    )
    available_men_count = sum(
        1 for p in listObjProfiles if norm_gender(p) in ("male", "m", "uomo")
    )

    def sort_key(p):
        return p.get("created_at") or "1970-01-01 00:00:00"

    latest_profiles = sorted(
        listObjProfiles,
        key=sort_key,
        reverse=True
    )[:10]

    return render_template(
        "home.html",
        listObjProfiles=listObjProfiles,
        latest_profiles=latest_profiles,
        available_women_count=available_women_count,
        available_men_count=available_men_count,
        current_year=datetime.date.today().year
    )


@app.route("/chisiamo")
def chisiamo():
    return render_template("chisiamo.html")

# =============================================================================
# AUTH: ACCEDI / ESCI / AREA RISERVATA
# =============================================================================
@app.route("/accedi")
def accedi():
    dictValues = session.pop("form_data", {})
    dictErrors = session.pop("form_errors", {})
    return render_template("accedi.html", dictValues=dictValues, dictErrors=dictErrors)


@app.route("/accedi", methods=["POST"])
def process_login():
    password = (request.form.get("txt_password") or "").strip()
    if password == ADMIN_PASSCODE:
        session["is_authenticated"] = True
        session.pop("form_data", None)
        session.pop("form_errors", None)
        flash("Accesso effettuato.", "success")
        return redirect(url_for("annunci"))
    else:
        session["form_data"] = {"txt_password": ""}
        session["form_errors"] = {"txt_password": "Password errata."}
        flash("Codice errato.", "danger")
        return redirect(url_for("accedi"))


@app.route("/esci")
@require_auth
def esci():
    session.clear()
    flash("Sei uscito dall'area riservata.", "info")
    return redirect(url_for("home"))


@app.route("/area-riservata")
def area_riservata():
    if session.get("is_authenticated"):
        flash("Sei già autenticato.", "info")
        return redirect(url_for("annunci"))
    else:
        return redirect(url_for("accedi"))

# =============================================================================
# ANNUNCI (EX POSTS)
# =============================================================================
@app.route("/annunci")
def annunci():
    gender_in  = (request.args.get("gender") or "").strip().lower() or None
    age_range  = (request.args.get("age_range") or "").strip() or None
    hair_color = (request.args.get("hair_color") or "").strip().lower() or None
    eyes_color = (request.args.get("eyes_color") or "").strip().lower() or None

    # Filtri extra SOLO se autenticato
    name_q = None
    id_q = None
    if session.get("is_authenticated"):
        name_q = (request.args.get("name") or "").strip().lower() or None
        raw = (request.args.get("id") or "").strip()  # niente lower()
        id_q = int(raw) if raw.isdigit() else None

    gender = _norm_gender_val(gender_in)
    all_profiles = get_published_profiles_with_status()

    listObjProfiles = [
        p for p in all_profiles
        if _profile_matches_filters(p, gender, age_range, hair_color, eyes_color, name_q, id_q)
    ]

    # Normalizza nomi per la presentazione
    def cap(val: str | None) -> str:
        s = (val or "").strip()
        return (s[:1].upper() + s[1:].lower()) if s else ""

    listObjProfiles = [
        {
            **p,
            "first_name": cap(p.get("first_name")),
            "last_name":  cap(p.get("last_name")),
        }
        for p in listObjProfiles
    ]

    # Supporto apertura modale Modifica
    profile_to_edit = None
    to_edit = False
    profile_id = request.args.get("profile_id")
    if profile_id and session.get("is_authenticated"):
        row = profiles_dao.get_profile_by_id(int(profile_id))
        if row is not None:
            d = {k: row[k] for k in row.keys()}
            profile_to_edit = SimpleNamespace(**d)
            to_edit = True

    return render_template(
        "annunci.html",
        listObjProfiles=listObjProfiles,
        profile_to_edit=profile_to_edit,
        to_edit=to_edit,
        current_year=datetime.date.today().year
    )

# =============================================================================
# REDIRECT DI COMPATIBILITÀ (301)
# =============================================================================
@app.route("/posts")
def posts_legacy():
    return redirect(url_for("annunci"), code=301)

@app.route("/about")
def about_legacy():
    return redirect(url_for("chisiamo"), code=301)

@app.route("/login")
def login_legacy():
    return redirect(url_for("accedi"), code=301)

@app.route("/logout")
def logout_legacy():
    return redirect(url_for("esci"), code=301)

# =============================================================================
# HELPER COMUNI
# =============================================================================
def _to_int(v):
    try:
        return int(v) if v not in (None, "", "None") else None
    except Exception:
        return None


def _cb_to_int(v):
    return 1 if v in ("on", "1", 1, True, "true") else 0


# Filtri annunci
AGE_BUCKETS = {
    "25-35": (25, 35),
    "35-45": (35, 45),
    "45-55": (45, 55),
    "55+":   (55, 150),
}

_GENDER_MAP = {
    "male": "male", "m": "male", "uomo": "male",
    "female": "female", "f": "female", "donna": "female",
}


def _norm_gender_val(val) -> str | None:
    v = (val or "").strip().lower()
    return _GENDER_MAP.get(v)


def _profile_matches_filters(p: dict,
                             gender: str | None,
                             age_range: str | None,
                             hair_color: str | None,
                             eyes_color: str | None,
                             name_q: str | None,
                             id_q: int | None) -> bool:
    # ID (solo se autenticato)
    if id_q is not None:
        try:
            if int(p.get("id")) != id_q:
                return False
        except (TypeError, ValueError):
            return False

    # GENDER
    if gender:
        pg = _norm_gender_val(p.get("gender"))
        if pg != gender:
            return False

    # HAIR / EYES
    if hair_color:
        if (p.get("hair_color") or "").strip().lower() != hair_color:
            return False

    if eyes_color:
        if (p.get("eyes_color") or "").strip().lower() != eyes_color:
            return False

    # AGE RANGE
    if age_range in AGE_BUCKETS:
        min_age, max_age = AGE_BUCKETS[age_range]
        by = p.get("birth_year")
        try:
            by = int(by)
        except (TypeError, ValueError):
            return False
        age = datetime.date.today().year - by
        if not (min_age <= age <= max_age):
            return False

    # NAME (solo se autenticato)
    if name_q:
        fn = (p.get("first_name") or "").strip().lower()
        ln = (p.get("last_name") or "").strip().lower()
        full = f"{fn} {ln}".strip()
        if name_q not in fn and name_q not in ln and name_q not in full:
            return False

    return True

# =============================================================================
# CREA / AGGIORNA / ELIMINA PROFILO
# =============================================================================
@app.route("/create_or_update_profile", methods=["POST"])
@require_auth
def create_or_update_profile():
    form = request.form
    profile_id = form.get("profile_id")
    action = form.get("action")

    # === DELETE ===
    if profile_id and action == "delete":
        profiles_dao.delete_profile(int(profile_id))
        flash("Profilo eliminato con successo!", "success")
        return redirect(url_for("annunci"))

    # === LETTURA CAMPI ===
    first_name = (form.get("first_name") or "").strip()
    last_name  = (form.get("last_name") or "").strip()
    gender     = (form.get("gender") or "").strip().lower()
    birth_year = _to_int(form.get("birth_year"))
    city       = (form.get("city") or "").strip()
    occupation = (form.get("occupation") or "").strip()
    eyes_color = (form.get("eyes_color") or "").strip()
    hair_color = (form.get("hair_color") or "").strip()
    zodiac_sign = (form.get("zodiac_sign") or "").strip()

    # Altezza in metri → DB in cm
    def _to_float(v):
        try:
            if v is None or str(v).strip() == "":
                return None
            return float(str(v).replace(",", "."))
        except Exception:
            return None

    height_m = _to_float(form.get("height_m"))
    if height_m is not None:
        height_cm = int(round(height_m * 100))
    else:
        height_cm = _to_int(form.get("height_cm"))

    # se update, non sovrascrivere con None
    if profile_id and height_cm is None:
        old = profiles_dao.get_profile_by_id(int(profile_id))
        if old and old.get("height_cm") is not None:
            height_cm = int(old["height_cm"])

    weight_kg       = _to_int(form.get("weight_kg"))
    marital_status  = (form.get("marital_status") or "").strip()
    smoker          = _cb_to_int(form.get("smoker"))
    bio             = (form.get("bio") or "").strip()
    is_active       = 1

    # === VALIDAZIONE ===
    errors = []
    if not first_name: errors.append("Il nome è obbligatorio.")
    if not gender: errors.append("Il genere è obbligatorio.")
    if not bio: errors.append("La bio è obbligatoria.")
    if height_m is not None and not (1.00 <= height_m <= 2.50):
        errors.append("L’altezza deve essere tra 1.00 m e 2.50 m.")

    if errors:
        for e in errors:
            flash(e, "danger")
        # Solo in caso di errore su un update, mantieni l’ID
        if profile_id:
            return redirect(url_for("annunci", profile_id=profile_id))
        else:
            return redirect(url_for("annunci"))

    # === UPDATE o INSERT ===
    if profile_id:
        profiles_dao.update_profile(
            profile_id=int(profile_id),
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            birth_year=birth_year,
            city=city,
            occupation=occupation,
            eyes_color=eyes_color,
            hair_color=hair_color,
            height_cm=height_cm,
            smoker=smoker,
            bio=bio,
            is_active=is_active,
            weight_kg=weight_kg,
            marital_status=marital_status,
            zodiac_sign=zodiac_sign,
        )
        flash("Profilo aggiornato con successo!", "success")
    else:
        profiles_dao.insert_profile(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            birth_year=birth_year,
            city=city,
            occupation=occupation,
            eyes_color=eyes_color,
            hair_color=hair_color,
            height_cm=height_cm,
            smoker=smoker,
            bio=bio,
            is_active=is_active,
            weight_kg=weight_kg,
            marital_status=marital_status,
            zodiac_sign=zodiac_sign,
            created_at=datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        )
        flash("Profilo creato e pubblicato!", "success")

    # Redirect pulito (nessun profile_id) così “Inserisci profilo” parte vuoto
    return redirect(url_for("annunci"))
# =============================================================================
# INVIO EMAIL (con SSL 465 o STARTTLS 587/25) + timeout
# =============================================================================
import ssl

SMTP_TIMEOUT = int(os.getenv("SMTP_TIMEOUT", "12"))

def send_email(subject: str,
               text_body: str,
               html_body: str | None = None,
               reply_to: str | None = None) -> tuple[bool, str | None]:
    """
    Invia email tramite SendGrid API.
    Richiede:
      - SENDGRID_API_KEY in env
      - MAIL_FROM verificato su SendGrid (Single Sender o domain auth)
    """
    try:
        if not SENDGRID_API_KEY:
            return False, "SENDGRID_API_KEY mancante"

        message = Mail(
            from_email=MAIL_FROM,
            to_emails=MAIL_TO,
            subject=subject,
            plain_text_content=text_body,
            html_content=html_body or text_body.replace("\n", "<br>")
        )
        if reply_to:
            message.reply_to = Email(reply_to)

        sg = SendGridAPIClient(SENDGRID_API_KEY)
        resp = sg.send(message)
        ok = 200 <= resp.status_code < 300
        return (ok, None if ok else f"SendGrid status {resp.status_code}")
    except Exception as e:
        return False, str(e)


# =============================================================================
# ROUTE: INVIO MESSAGGIO
# =============================================================================
from traceback import format_exc

@app.route("/send_message", methods=["POST"])
def send_message():
    try:
        form = request.form

        profile_id   = form.get("profile_id", "")
        pid = int(profile_id) if str(profile_id).isdigit() else None
        profile_name = form.get("profile_name", "")

        sender_name   = (form.get("sender_name") or "").strip()
        sender_phone  = (form.get("sender_phone") or "").strip()
        sender_email  = (form.get("sender_email") or "").strip()
        sender_job    = (form.get("sender_job") or "").strip() or "—"
        sender_age    = (form.get("sender_age") or "").strip()
        sender_city   = (form.get("sender_city") or "").strip()
        sender_msg    = (form.get("sender_message") or "").strip() or "—"
        agree_privacy = form.get("agree_privacy")

        errors = []
        if not sender_name:
            errors.append("Il nome è obbligatorio.")
        if not sender_phone:
            errors.append("Il cellulare è obbligatorio.")
        if not sender_email or "@" not in sender_email:
            errors.append("Email non valida.")
        if not sender_age:
            errors.append("L'età è obbligatoria.")
        elif not sender_age.isdigit():
            errors.append("L'età deve essere un numero.")
        if not sender_city:
            errors.append("La città è obbligatoria.")
        if not agree_privacy:
            errors.append("Devi accettare l'informativa privacy.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return redirect(request.referrer or url_for("annunci"))

        subject = f"Nuovo contatto per {profile_name or 'profilo'}{f' (ID {profile_id})' if profile_id else ''}"

        # --- corpi email ---
        text_body = f"""Hai ricevuto un nuovo contatto per il profilo {profile_name or '(senza nome)'}.

Dettagli mittente:
- Nome: {sender_name}
- Email: {sender_email}
- Cellulare: {sender_phone}
- Lavoro: {sender_job}
- Età: {sender_age}
- Città: {sender_city}

Messaggio:
{sender_msg}
"""
        html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height:1.5;">
  <p>Hai ricevuto un nuovo contatto per il profilo <b>{profile_name or '(senza nome)'}</b>.</p>
  <p><b>Nome:</b> {sender_name}</p>
  <p><b>Email:</b> <a href="mailto:{sender_email}">{sender_email}</a></p>
  <p><b>Cellulare:</b> <a href="tel:{sender_phone}">{sender_phone}</a></p>
  <p><b>Lavoro:</b> {sender_job}</p>
  <p><b>Età:</b> {sender_age}</p>
  <p><b>Città:</b> {sender_city}</p>
  <p><b>Messaggio:</b><br>{sender_msg}</p>
</body>
</html>
"""

        # ----- invio email tramite helper con SSL/STARTTLS -----
        ok, err = send_email(
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            reply_to=sender_email
        )
        if not ok:
            app.logger.error("Errore invio email: %s", err)

        # ----- DB INSERT -----
        try:
            profiles_dao.insert_message(
                sender_name=sender_name,
                sender_phone=sender_phone,
                sender_email=sender_email,
                sender_job=sender_job,
                sender_age=int(sender_age),   # validato numerico sopra
                sender_city=sender_city,
                sender_message=sender_msg,
                profile_id=pid
            )
            saved_ok = True
        except Exception as e:
            saved_ok = False
            app.logger.exception("Errore salvataggio messaggio su DB")
            flash(f"Errore nel salvataggio del messaggio nel database: {e}", "danger")

        if ok and saved_ok:
            flash("Messaggio inviato e salvato con successo!", "success")
        elif ok and not saved_ok:
            flash("Messaggio inviato via email, ma non salvato nel database.", "warning")
        elif not ok and saved_ok:
            flash(f"Email non inviata (salvata nel database): {err}", "warning")
        else:
            flash(f"Errore nell'invio email e nel salvataggio: {err}", "danger")

        return redirect(request.referrer or url_for("annunci"))

    except Exception:
        app.logger.error("Eccezione non gestita in /send_message:\n%s", format_exc())
        flash("Si è verificato un errore interno durante l'invio del messaggio.", "danger")
        return redirect(url_for("annunci"))
