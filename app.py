import logging
import os
from datetime import datetime, timedelta, timezone

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from flask import Flask, g, redirect, session, url_for

from config import Config

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.secret_key = Config.SECRET_KEY
app.permanent_session_lifetime = timedelta(days=30)

# Scheduler instance (accessible to admin routes)
scheduler = None


def get_db_connection():
    conn = psycopg2.connect(Config.DATABASE_URL)
    conn.autocommit = True
    return conn


def _poll_job():
    """Background job that calls update_scores with its own connection."""
    from services.espn import update_scores
    logger.info("Scheduler polling ESPN at %s", datetime.now(timezone.utc).isoformat())
    success = update_scores()
    logger.info("Scheduler poll %s", "succeeded" if success else "failed")


def _should_start_scheduler():
    """Determine if we should start the scheduler in this process."""
    if Config.ENABLE_POLLING != "1":
        return False
    # In Flask debug mode, the reloader spawns two processes.
    # Only start in the main (reloader) process, identified by WERKZEUG_RUN_MAIN.
    if os.environ.get("FLASK_DEBUG") == "1" or app.debug:
        return os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    # Under gunicorn or direct run without debug, always start.
    return True


def start_scheduler(interval=None):
    """Start or restart the background scheduler."""
    global scheduler
    from apscheduler.schedulers.background import BackgroundScheduler

    if interval is None:
        interval = Config.ESPN_POLL_INTERVAL

    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _poll_job,
        "interval",
        seconds=interval,
        id="espn_poll",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started with %d second interval", interval)


@app.before_request
def load_user():
    g.current_user = None
    user_id = session.get("user_id")
    if user_id:
        from models.user import get_user_by_id
        try:
            conn = get_db_connection()
            g.current_user = get_user_by_id(conn, user_id)
            conn.close()
        except (psycopg2.errors.UndefinedTable, psycopg2.ProgrammingError):
            g.current_user = None
        except Exception:
            session.pop("user_id", None)


@app.after_request
def add_no_cache(response):
    if 'text/css' in response.content_type or 'javascript' in response.content_type:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


@app.context_processor
def inject_globals():
    deadline = datetime.fromisoformat(Config.PICKS_DEADLINE)
    now = datetime.now(timezone(timedelta(hours=-4)))
    user = g.get("current_user")
    return {
        "current_user": user,
        "picks_deadline": Config.PICKS_DEADLINE,
        "picks_locked": now > deadline,
        "is_admin": user and user["username"] == Config.ADMIN_USERNAME,
    }


def format_display_name(username):
    """Format username for display: 'cory' -> 'Cory', 'cory baltz' -> 'Cory B.'"""
    if not username:
        return ""
    parts = username.strip().split()
    if len(parts) == 1:
        return parts[0].capitalize()
    if len(parts) == 2:
        if len(parts[1]) == 2 and parts[1].endswith("."):
            return f"{parts[0].capitalize()} {parts[1].upper()}"
        return f"{parts[0].capitalize()} {parts[1][0].upper()}."
    return parts[0].capitalize() + " " + parts[1][0].upper() + "."


app.jinja_env.filters["display_name"] = format_display_name


def format_ordinal(value):
    """Convert position to ordinal: 1 -> '1st', 2 -> '2nd', 11 -> '11th', etc."""
    if not value:
        return ""
    s = str(value).lstrip("T").strip()
    try:
        n = int(s)
    except (ValueError, TypeError):
        return str(value)
    if 11 <= n % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    tied = "T" if str(value).startswith("T") else ""
    return f"{tied}{n}{suffix}"


app.jinja_env.filters["ordinal"] = format_ordinal


@app.route("/health")
def health():
    return "OK", 200


from routes.auth import auth_bp
from routes.picks import picks_bp
from routes.leaderboard import leaderboard_bp
from routes.scores import scores_bp
from routes.admin import admin_bp
from routes.team import team_bp
from routes.exposure import exposure_bp

app.register_blueprint(auth_bp)
app.register_blueprint(picks_bp)
app.register_blueprint(leaderboard_bp)
app.register_blueprint(scores_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(team_bp)
app.register_blueprint(exposure_bp)

# Start scheduler if appropriate
if _should_start_scheduler():
    start_scheduler()


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8888, debug=True)
