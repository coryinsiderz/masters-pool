from datetime import datetime, timedelta, timezone

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from app import get_db_connection
from config import Config
from models.golfer import get_golfers_by_tier
from models.pick import get_picks_for_user, set_pick

picks_bp = Blueprint("picks", __name__)

TIER_NAMES = {
    1: "Tier 1",
    2: "Strong Side",
    3: "Weak Side",
    4: "Maybe",
    5: "Meh",
    6: "Do You Believe in Miracles",
}


def is_locked():
    deadline = datetime.fromisoformat(Config.PICKS_DEADLINE)
    now = datetime.now(timezone(timedelta(hours=-4)))
    return now > deadline


@picks_bp.route("/picks", methods=["GET", "POST"])
def picks():
    if not g.current_user:
        return redirect(url_for("auth.login"))

    conn = get_db_connection()
    locked = is_locked()

    if request.method == "POST" and not locked:
        for tier_num in range(1, 7):
            golfer_id = request.form.get(f"tier_{tier_num}")
            if golfer_id:
                set_pick(conn, g.current_user["id"], tier_num, int(golfer_id))
        flash("Picks saved.", "success")
        conn.close()
        return redirect(url_for("picks.picks"))

    tiers = {}
    for tier_num in range(1, 7):
        tiers[tier_num] = {
            "name": TIER_NAMES[tier_num],
            "golfers": get_golfers_by_tier(conn, tier_num),
        }

    current_picks = {p["tier"]: p for p in get_picks_for_user(conn, g.current_user["id"])}
    conn.close()

    return render_template(
        "picks.html", tiers=tiers, current_picks=current_picks, locked=locked
    )
