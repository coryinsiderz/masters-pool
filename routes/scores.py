import psycopg2.extras
from flask import Blueprint, g, redirect, render_template, url_for

from models.tournament import get_all_scores, get_tournament_state

scores_bp = Blueprint("scores", __name__)


@scores_bp.route("/scores")
def scores():
    if not g.current_user:
        return redirect(url_for("auth.login"))
    from app import get_db_connection
    conn = get_db_connection()
    tournament = get_tournament_state(conn)
    all_scores = get_all_scores(conn)

    # Get ownership data
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

    # Get current user's picked golfer IDs
    with conn.cursor() as cur:
        cur.execute(
            "SELECT golfer_id FROM picks WHERE user_id = %s",
            (g.current_user["id"],),
        )
        my_golfer_ids = {row[0] for row in cur.fetchall()}

    conn.close()

    # Build ownership map: golfer_id -> {count, owners}
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

    # Split into active and cut/withdrawn
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
    return render_template(
        "scores.html",
        scores=scores_list,
        tournament=tournament,
        total_users=total_users,
        my_golfer_ids=my_golfer_ids,
    )


def _parse_position(pos):
    if not pos:
        return 9999
    try:
        return int(str(pos).lstrip("T").strip())
    except (ValueError, TypeError):
        return 9999
