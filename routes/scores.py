from datetime import datetime, timedelta, timezone

import psycopg2.extras
from flask import Blueprint, g, redirect, render_template, request, url_for

from config import Config
from models.tournament import get_all_scores, get_tournament_state

scores_bp = Blueprint("scores", __name__)

AUGUSTA_PAR = [4, 5, 4, 3, 4, 3, 4, 5, 4, 4, 4, 3, 5, 4, 5, 3, 4, 4]


@scores_bp.route("/scores")
def scores():
    if not g.current_user:
        return redirect(url_for("auth.login"))
    from app import get_db_connection
    conn = get_db_connection()
    tournament = get_tournament_state(conn)
    all_scores = get_all_scores(conn)

    # Check if picks are locked
    deadline = datetime.fromisoformat(Config.PICKS_DEADLINE)
    now_et = datetime.now(timezone(timedelta(hours=-4)))
    locked = now_et > deadline

    # Ownership data only available after picks lock
    total_users = 0
    my_golfer_ids = set()
    if locked:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT COUNT(DISTINCT user_id) AS cnt FROM picks")
            total_users = cur.fetchone()["cnt"]
            cur.execute(
                """SELECT p.golfer_id, u.username
                   FROM picks p
                   JOIN users u ON p.user_id = u.id
                   ORDER BY p.golfer_id, u.username"""
            )
            owner_rows = cur.fetchall()

        with conn.cursor() as cur:
            cur.execute(
                "SELECT golfer_id FROM picks WHERE user_id = %s",
                (g.current_user["id"],),
            )
            my_golfer_ids = {row[0] for row in cur.fetchall()}

        # Build ownership map
        ownership = {}
        for row in owner_rows:
            gid = row["golfer_id"]
            if gid not in ownership:
                ownership[gid] = {"count": 0, "owners": []}
            ownership[gid]["count"] += 1
            ownership[gid]["owners"].append(row["username"])

        # Attach ownership to each score
        for s in all_scores:
            gid = s.get("golfer_id")
            own = ownership.get(gid, {"count": 0, "owners": []})
            s["ownership_count"] = own["count"]
            s["ownership_pct"] = round(own["count"] / total_users * 100) if total_users else 0
            s["owners"] = own["owners"]
    else:
        for s in all_scores:
            s["ownership_count"] = 0
            s["ownership_pct"] = 0
            s["owners"] = []

    # Split into active and cut
    active = []
    cut = []
    for s in all_scores:
        if s.get("status") in ("MC", "WD", "DQ"):
            cut.append(s)
        else:
            active.append(s)

    active.sort(key=lambda s: _parse_position(s.get("position", "")))
    cut.sort(key=lambda s: s.get("name", ""))
    scores_list = active + cut

    # Check view mode
    view = request.args.get("view", "leaderboard")
    current_round = tournament.get("current_round", 0) if tournament else 0
    selected_round = request.args.get("round", type=int) or current_round or 1

    scorecard_data = {}
    has_hole_data = False
    if view == "board":
        from services.espn import fetch_scorecard_data, get_mock_scorecard_data
        scorecard_data = fetch_scorecard_data()
        has_hole_data = any(v.get("has_holes") for v in scorecard_data.values())
        if not has_hole_data:
            scorecard_data = get_mock_scorecard_data()
            has_hole_data = True

    return render_template(
        "scores.html",
        scores=scores_list,
        tournament=tournament,
        total_users=total_users,
        my_golfer_ids=my_golfer_ids,
        view=view,
        par=AUGUSTA_PAR,
        scorecard_data=scorecard_data,
        has_hole_data=has_hole_data,
        selected_round=selected_round,
        current_round=current_round,
    )


def _parse_position(pos):
    if not pos:
        return 9999
    try:
        return int(str(pos).lstrip("T").strip())
    except (ValueError, TypeError):
        return 9999
