from flask import Blueprint, g, jsonify, redirect, render_template, url_for

from services.scoring import build_leaderboard

leaderboard_bp = Blueprint("leaderboard", __name__)


@leaderboard_bp.route("/leaderboard")
@leaderboard_bp.route("/")
def leaderboard():
    if not g.current_user:
        return redirect(url_for("auth.login"))
    from app import get_db_connection
    conn = get_db_connection()
    standings = build_leaderboard(conn)
    conn.close()
    return render_template("leaderboard.html", standings=standings)


@leaderboard_bp.route("/api/leaderboard")
def api_leaderboard():
    if not g.current_user:
        return jsonify({"error": "unauthorized"}), 401
    from app import get_db_connection
    conn = get_db_connection()
    standings = build_leaderboard(conn)
    conn.close()
    # Serialize for JSON (strip non-serializable fields)
    result = []
    for s in standings:
        result.append({
            "rank": s["rank"],
            "username": s["username"],
            "team_total": s["team_total"],
            "counting_golfers": [
                {"name": g["name"], "total_strokes": g.get("effective_strokes")}
                for g in s["counting_golfers"]
            ],
            "bench_golfers": [
                {"name": g["name"], "total_strokes": g.get("effective_strokes")}
                for g in s["bench_golfers"]
            ],
        })
    return jsonify({"standings": result})
