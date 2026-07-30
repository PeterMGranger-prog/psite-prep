from __future__ import annotations

import csv
import io
import json
import os
import secrets
import sqlite3
from datetime import date, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, flash, g, jsonify, make_response, redirect, render_template, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

BASE = Path(__file__).resolve().parent
DB = Path(os.getenv("DATABASE_PATH", str(BASE / "psite_prep.db")))
APP_NAME = os.getenv("APP_NAME", "PSITE Prep")
INVITE_CODE = os.getenv("INVITE_CODE", "").strip()

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "dev-change-me"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


def db() -> sqlite3.Connection:
    if "db" not in g:
        DB.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(DB, timeout=30)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA busy_timeout=30000")
    return g.db


@app.teardown_appcontext
def close_db(_: object | None = None) -> None:
    connection = g.pop("db", None)
    if connection:
        connection.close()


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if "uid" not in session:
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)

    return wrapped


def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


def valid_csrf() -> bool:
    supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
    return bool(supplied and secrets.compare_digest(supplied, session.get("csrf", "")))


@app.before_request
def protect_writes():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.endpoint not in {"health"}:
        if not valid_csrf():
            return jsonify(error="Your session expired. Refresh and try again."), 400


@app.context_processor
def template_globals():
    user = None
    if session.get("uid"):
        user = db().execute("SELECT * FROM users WHERE id=?", (session["uid"],)).fetchone()
    return {"user": user, "csrf_token": csrf_token, "app_name": APP_NAME}


@app.get("/health")
def health():
    db().execute("SELECT 1").fetchone()
    return jsonify(status="ok")


@app.get("/")
def home():
    return redirect(url_for("dashboard")) if session.get("uid") else render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        invite = request.form.get("invite_code", "").strip()
        if INVITE_CODE and not secrets.compare_digest(invite, INVITE_CODE):
            flash("That program invite code is not valid.", "error")
        elif not name or "@" not in email or len(password) < 10:
            flash("Enter a name, valid email, and password of at least 10 characters.", "error")
        else:
            try:
                cursor = db().execute(
                    "INSERT INTO users(email,password_hash,display_name) VALUES(?,?,?)",
                    (email, generate_password_hash(password), name),
                )
                db().commit()
                session.clear()
                session.permanent = True
                session["uid"] = cursor.lastrowid
                csrf_token()
                return redirect(url_for("dashboard"))
            except sqlite3.IntegrityError:
                flash("That email is already registered.", "error")
    return render_template("auth.html", mode="register", invite_required=bool(INVITE_CODE))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session.permanent = True
            session["uid"] = user["id"]
            csrf_token()
            destination = request.args.get("next", "")
            return redirect(destination if destination.startswith("/") else url_for("dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("auth.html", mode="login", invite_required=False)


@app.post("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.get("/dashboard")
@login_required
def dashboard():
    uid = session["uid"]
    connection = db()
    total = connection.execute("SELECT COUNT(*) n FROM attempts WHERE user_id=?", (uid,)).fetchone()["n"]
    correct = connection.execute("SELECT COALESCE(SUM(is_correct),0) n FROM attempts WHERE user_id=?", (uid,)).fetchone()["n"]
    sections = connection.execute(
        """SELECT q.section,COUNT(a.id) attempts,COALESCE(SUM(a.is_correct),0) correct,
        ROUND(100.0*SUM(a.is_correct)/NULLIF(COUNT(a.id),0),1) accuracy
        FROM questions q LEFT JOIN attempts a ON a.question_id=q.id AND a.user_id=?
        GROUP BY q.section ORDER BY q.section""",
        (uid,),
    ).fetchall()
    due = connection.execute(
        """SELECT COUNT(*) n FROM flashcard_templates f
        LEFT JOIN card_progress p ON p.card_id=f.id AND p.user_id=?
        WHERE COALESCE(p.due_date,?)<=?""",
        (uid, date.today().isoformat(), date.today().isoformat()),
    ).fetchone()["n"]
    recent = connection.execute(
        """SELECT s.*,COUNT(a.id) answered,COALESCE(SUM(a.is_correct),0) correct
        FROM study_sessions s LEFT JOIN attempts a ON a.session_token=s.token
        WHERE s.user_id=? GROUP BY s.token ORDER BY s.started_at DESC LIMIT 5""",
        (uid,),
    ).fetchall()
    return render_template(
        "dashboard.html", total=total, accuracy=round(100 * correct / total) if total else 0,
        sections=sections, due=due, recent=recent,
    )


@app.get("/practice/setup")
@login_required
def practice_setup():
    taxonomy = db().execute(
        "SELECT section,subsection,COUNT(*) count FROM questions GROUP BY section,subsection ORDER BY section,subsection"
    ).fetchall()
    return render_template("practice_setup.html", taxonomy=taxonomy)


@app.post("/practice/start")
@login_required
def practice_start():
    section = request.form.get("section", "")
    subsection = request.form.get("subsection", "")
    try:
        count = max(1, min(int(request.form.get("count", 10)), 100))
    except ValueError:
        count = 10
    where, params = [], []
    if section:
        where.append("section=?")
        params.append(section)
    if subsection:
        where.append("subsection=?")
        params.append(subsection)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    rows = db().execute(f"SELECT id FROM questions{clause} ORDER BY RANDOM() LIMIT ?", (*params, count)).fetchall()
    if not rows:
        flash("No questions match those filters.", "error")
        return redirect(url_for("practice_setup"))
    token = secrets.token_urlsafe(12)
    ids = [row["id"] for row in rows]
    db().execute(
        "INSERT INTO study_sessions(token,user_id,section,subsection,requested_count,question_ids) VALUES(?,?,?,?,?,?)",
        (token, session["uid"], section, subsection, len(ids), json.dumps(ids)),
    )
    db().commit()
    return redirect(url_for("quiz", token=token, n=1))


@app.get("/practice/<token>/<int:n>")
@login_required
def quiz(token: str, n: int):
    study_session = db().execute(
        "SELECT * FROM study_sessions WHERE token=? AND user_id=?", (token, session["uid"])
    ).fetchone()
    if not study_session:
        return redirect(url_for("practice_setup"))
    ids = json.loads(study_session["question_ids"])
    if n > len(ids):
        db().execute(
            "UPDATE study_sessions SET completed_at=COALESCE(completed_at,CURRENT_TIMESTAMP) WHERE token=?", (token,)
        )
        db().commit()
        return redirect(url_for("results", token=token))
    question = db().execute("SELECT * FROM questions WHERE id=?", (ids[n - 1],)).fetchone()
    previous = db().execute(
        "SELECT * FROM attempts WHERE user_id=? AND session_token=? AND question_id=? ORDER BY id DESC LIMIT 1",
        (session["uid"], token, question["id"]),
    ).fetchone()
    return render_template("quiz.html", q=question, token=token, n=n, total=len(ids), previous=previous)


@app.post("/api/answer")
@login_required
def answer():
    payload = request.get_json() or {}
    question = db().execute("SELECT * FROM questions WHERE id=?", (payload.get("question_id"),)).fetchone()
    study_session = db().execute(
        "SELECT * FROM study_sessions WHERE token=? AND user_id=?", (payload.get("token"), session["uid"])
    ).fetchone()
    if not question or not study_session:
        return jsonify(error="Invalid session"), 400
    selected = payload.get("selected", "")
    valid = [letter for letter in "ABCDE" if question["option_" + letter.lower()]]
    if selected not in valid:
        return jsonify(error="Choose an answer"), 400
    already = db().execute(
        "SELECT id FROM attempts WHERE user_id=? AND session_token=? AND question_id=?",
        (session["uid"], study_session["token"], question["id"]),
    ).fetchone()
    if already:
        return jsonify(error="This question was already answered."), 409
    is_correct = int(selected == question["correct_option"])
    db().execute(
        "INSERT INTO attempts(user_id,question_id,session_token,selected_option,is_correct,elapsed_ms) VALUES(?,?,?,?,?,?)",
        (session["uid"], question["id"], study_session["token"], selected, is_correct, int(payload.get("elapsed_ms", 0))),
    )
    db().commit()
    return jsonify(correct=bool(is_correct), correct_option=question["correct_option"], explanation=question["explanation"])


@app.get("/results/<token>")
@login_required
def results(token: str):
    study_session = db().execute(
        "SELECT * FROM study_sessions WHERE token=? AND user_id=?", (token, session["uid"])
    ).fetchone()
    if not study_session:
        return redirect(url_for("dashboard"))
    rows = db().execute(
        """SELECT a.*,q.stem,q.section,q.subsection,q.correct_option,q.explanation
        FROM attempts a JOIN questions q ON q.id=a.question_id
        WHERE a.user_id=? AND a.session_token=? ORDER BY a.id""",
        (session["uid"], token),
    ).fetchall()
    return render_template("results.html", s=study_session, rows=rows, correct=sum(row["is_correct"] for row in rows))


@app.get("/analytics")
@login_required
def analytics():
    rows = db().execute(
        """SELECT q.section,q.subsection,COUNT(a.id) attempts,SUM(a.is_correct) correct,
        ROUND(100.0*SUM(a.is_correct)/COUNT(a.id),1) accuracy,
        ROUND(AVG(a.elapsed_ms)/1000.0,1) seconds
        FROM attempts a JOIN questions q ON q.id=a.question_id
        WHERE a.user_id=? GROUP BY q.section,q.subsection ORDER BY accuracy,attempts DESC""",
        (session["uid"],),
    ).fetchall()
    return render_template("analytics.html", rows=rows)


@app.get("/cohort")
@login_required
def cohort():
    stats = db().execute(
        """SELECT COUNT(DISTINCT u.id) residents, COUNT(a.id) attempts,
        ROUND(100.0*SUM(a.is_correct)/NULLIF(COUNT(a.id),0),1) accuracy
        FROM users u LEFT JOIN attempts a ON a.user_id=u.id"""
    ).fetchone()
    sections = db().execute(
        """SELECT q.section,COUNT(a.id) attempts,
        ROUND(100.0*SUM(a.is_correct)/NULLIF(COUNT(a.id),0),1) accuracy
        FROM questions q LEFT JOIN attempts a ON a.question_id=q.id
        GROUP BY q.section ORDER BY q.section"""
    ).fetchall()
    return render_template("cohort.html", stats=stats, sections=sections)


@app.get("/flashcards")
@login_required
def flashcards():
    section = request.args.get("section", "")
    subsection = request.args.get("subsection", "")
    where = ["COALESCE(p.due_date,?)<=?"]
    filter_params: list[str] = []
    if section:
        where.append("f.section=?")
        filter_params.append(section)
    if subsection:
        where.append("f.subsection=?")
        filter_params.append(subsection)
    card = db().execute(
        f"""SELECT f.*,p.repetitions,p.interval_days,p.ease_factor,p.due_date
        FROM flashcard_templates f LEFT JOIN card_progress p ON p.card_id=f.id AND p.user_id=?
        WHERE {' AND '.join(where)} ORDER BY RANDOM() LIMIT 1""",
        (session["uid"], date.today().isoformat(), date.today().isoformat(), *filter_params),
    ).fetchone()
    taxonomy = db().execute(
        "SELECT section,subsection,COUNT(*) n FROM flashcard_templates GROUP BY section,subsection ORDER BY section,subsection"
    ).fetchall()
    return render_template("flashcards.html", card=card, taxonomy=taxonomy, section=section, subsection=subsection)


@app.post("/api/cards/<int:card_id>/review")
@login_required
def review_card(card_id: int):
    quality = max(0, min(int((request.get_json() or {}).get("quality", 3)), 5))
    progress = db().execute(
        "SELECT * FROM card_progress WHERE user_id=? AND card_id=?", (session["uid"], card_id)
    ).fetchone()
    repetitions = progress["repetitions"] if progress else 0
    interval = progress["interval_days"] if progress else 0
    ease = progress["ease_factor"] if progress else 2.5
    if quality < 3:
        repetitions, interval = 0, 1
    else:
        repetitions += 1
        interval = 1 if repetitions == 1 else 6 if repetitions == 2 else max(1, round(interval * ease))
        ease = max(1.3, ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    due = (date.today() + timedelta(days=interval)).isoformat()
    db().execute(
        """INSERT INTO card_progress(user_id,card_id,repetitions,interval_days,ease_factor,due_date,last_reviewed_at)
        VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(user_id,card_id) DO UPDATE SET repetitions=excluded.repetitions,
        interval_days=excluded.interval_days,ease_factor=excluded.ease_factor,due_date=excluded.due_date,
        last_reviewed_at=CURRENT_TIMESTAMP""",
        (session["uid"], card_id, repetitions, interval, ease, due),
    )
    db().commit()
    return jsonify(due=due, interval=interval)


@app.post("/api/bookmark/<int:question_id>")
@login_required
def bookmark(question_id: int):
    found = db().execute(
        "SELECT 1 FROM bookmarks WHERE user_id=? AND question_id=?", (session["uid"], question_id)
    ).fetchone()
    if found:
        db().execute("DELETE FROM bookmarks WHERE user_id=? AND question_id=?", (session["uid"], question_id))
        state = False
    else:
        db().execute("INSERT INTO bookmarks(user_id,question_id) VALUES(?,?)", (session["uid"], question_id))
        state = True
    db().commit()
    return jsonify(bookmarked=state)


@app.get("/bookmarks")
@login_required
def bookmarks():
    rows = db().execute(
        """SELECT q.* FROM bookmarks b JOIN questions q ON q.id=b.question_id
        WHERE b.user_id=? ORDER BY b.created_at DESC""",
        (session["uid"],),
    ).fetchall()
    return render_template("bookmarks.html", rows=rows)


@app.get("/account/export.csv")
@login_required
def export_progress():
    rows = db().execute(
        """SELECT a.created_at,q.section,q.subsection,q.stem,a.selected_option,q.correct_option,a.is_correct,a.elapsed_ms
        FROM attempts a JOIN questions q ON q.id=a.question_id WHERE a.user_id=? ORDER BY a.created_at""",
        (session["uid"],),
    ).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "section", "subsection", "question", "selected", "correct", "is_correct", "elapsed_ms"])
    for row in rows:
        writer.writerow(list(row))
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=psite-progress.csv"
    return response


@app.get("/install")
def install():
    return render_template("install.html")


@app.get("/manifest.webmanifest")
def manifest():
    return app.send_static_file("manifest.webmanifest")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")
