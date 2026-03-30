import os
from datetime import datetime, timedelta, timezone

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from flask import Flask, g, redirect, session, url_for

from config import Config

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY
app.permanent_session_lifetime = timedelta(days=30)


def get_db_connection():
    conn = psycopg2.connect(Config.DATABASE_URL)
    conn.autocommit = True
    return conn


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
        except Exception:
            session.pop("user_id", None)


@app.context_processor
def inject_globals():
    deadline = datetime.fromisoformat(Config.PICKS_DEADLINE)
    now = datetime.now(timezone(timedelta(hours=-4)))
    return {
        "current_user": g.get("current_user"),
        "picks_deadline": Config.PICKS_DEADLINE,
        "picks_locked": now > deadline,
    }


@app.route("/health")
def health():
    return "OK", 200


from routes.auth import auth_bp
from routes.picks import picks_bp
from routes.leaderboard import leaderboard_bp
from routes.scores import scores_bp
from routes.admin import admin_bp
from routes.team import team_bp

app.register_blueprint(auth_bp)
app.register_blueprint(picks_bp)
app.register_blueprint(leaderboard_bp)
app.register_blueprint(scores_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(team_bp)


if __name__ == "__main__":
    app.run(debug=True, port=5050)
