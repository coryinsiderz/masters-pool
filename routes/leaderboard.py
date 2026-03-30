from flask import Blueprint, g, jsonify, redirect, render_template, url_for

from app import get_db_connection

leaderboard_bp = Blueprint("leaderboard", __name__)


@leaderboard_bp.route("/leaderboard")
@leaderboard_bp.route("/")
def leaderboard():
    if not g.current_user:
        return redirect(url_for("auth.login"))
    return render_template("leaderboard.html")


@leaderboard_bp.route("/api/leaderboard")
def api_leaderboard():
    if not g.current_user:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"standings": []})
