from datetime import datetime, timedelta, timezone

import psycopg2.extras
from flask import Blueprint, flash, g, redirect, render_template, url_for

from config import Config

exposure_bp = Blueprint("exposure", __name__)

TIER_NAMES = {
    1: "Tier 1",
    2: "Strong Side",
    3: "Weak Side",
    4: "Maybe",
    5: "Meh",
    6: "Miracles",
    7: "X",
}


def _is_locked():
    deadline = datetime.fromisoformat(Config.PICKS_DEADLINE)
    now = datetime.now(timezone(timedelta(hours=-4)))
    return now > deadline


@exposure_bp.route("/exposure")
def exposure():
    if not g.current_user:
        return redirect(url_for("auth.login"))
    if not _is_locked():
        flash("Ownership data available after picks lock.", "error")
        return redirect(url_for("picks.picks"))

    from app import get_db_connection
    conn = get_db_connection()

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT COUNT(DISTINCT user_id) AS cnt FROM picks")
        total_users = cur.fetchone()["cnt"]

        cur.execute(
            """SELECT g.id AS golfer_id, g.name, g.tier, g.masters_id,
                      gs.to_par, gs.position, gs.thru, gs.status,
                      COUNT(p.id) AS ownership_count
               FROM golfers g
               JOIN picks p ON p.golfer_id = g.id
               LEFT JOIN golfer_scores gs ON gs.golfer_id = g.id
               GROUP BY g.id, g.name, g.tier, g.masters_id, gs.to_par, gs.position, gs.thru, gs.status
               ORDER BY COUNT(p.id) DESC, g.name"""
        )
        golfers = cur.fetchall()

        cur.execute(
            """SELECT p.golfer_id, u.username
               FROM picks p
               JOIN users u ON p.user_id = u.id
               ORDER BY u.username"""
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

    owner_map = {}
    for row in owner_rows:
        owner_map.setdefault(row["golfer_id"], []).append(row["username"])

    for golfer in golfers:
        golfer["ownership_pct"] = round(golfer["ownership_count"] / total_users * 100) if total_users else 0
        golfer["owners"] = owner_map.get(golfer["golfer_id"], [])
        golfer["tier_name"] = TIER_NAMES.get(golfer["tier"], str(golfer["tier"]))

    return render_template(
        "exposure.html",
        golfers=golfers,
        total_users=total_users,
        tier_names=TIER_NAMES,
        my_golfer_ids=my_golfer_ids,
    )
