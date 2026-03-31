from datetime import datetime, timedelta, timezone

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from config import Config
from models.golfer import get_all_golfers, get_golfer_by_id, get_golfers_by_tier
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

    from app import get_db_connection
    conn = get_db_connection()
    locked = is_locked()

    if request.method == "POST":
        if locked:
            flash("Picks are locked. The deadline has passed.", "error")
            conn.close()
            return redirect(url_for("picks.picks"))

        missing = []
        valid_picks = []
        for tier_num in range(1, 7):
            golfer_id = request.form.get(f"tier_{tier_num}")
            if not golfer_id:
                missing.append(TIER_NAMES[tier_num])
                continue
            golfer = get_golfer_by_id(conn, int(golfer_id))
            if not golfer or golfer["tier"] != tier_num:
                flash(f"Invalid player selection for {TIER_NAMES[tier_num]}.", "error")
                conn.close()
                return redirect(url_for("picks.picks"))
            valid_picks.append((tier_num, int(golfer_id)))

        if missing:
            flash(f"Missing picks for: {', '.join(missing)}.", "error")
            conn.close()
            return redirect(url_for("picks.picks"))

        for tier_num, golfer_id in valid_picks:
            set_pick(conn, g.current_user["id"], tier_num, golfer_id)

        conn.close()
        flash("Picks saved.", "success")
        return redirect(url_for("team.team"))

    tiers = {}
    has_players = False
    for tier_num in range(1, 7):
        golfers = get_golfers_by_tier(conn, tier_num)
        if golfers:
            has_players = True
        tiers[tier_num] = {
            "name": TIER_NAMES[tier_num],
            "golfers": golfers,
        }

    current_picks = {p["tier"]: p for p in get_picks_for_user(conn, g.current_user["id"])}
    conn.close()

    return render_template(
        "picks.html",
        tiers=tiers,
        current_picks=current_picks,
        locked=locked,
        has_players=has_players,
    )
