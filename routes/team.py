from flask import Blueprint, g, redirect, render_template, url_for

from app import get_db_connection
from models.pick import get_picks_for_user
from models.tournament import get_scores_for_golfers

team_bp = Blueprint("team", __name__)


@team_bp.route("/team")
def team():
    if not g.current_user:
        return redirect(url_for("auth.login"))

    conn = get_db_connection()
    picks = get_picks_for_user(conn, g.current_user["id"])
    golfer_ids = [p["golfer_id"] for p in picks]
    scores = get_scores_for_golfers(conn, golfer_ids) if golfer_ids else []
    conn.close()

    scores_by_id = {s["golfer_id"]: s for s in scores}

    return render_template("team.html", picks=picks, scores_by_id=scores_by_id)
