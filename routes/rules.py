from datetime import datetime, timedelta, timezone

from flask import Blueprint, g, redirect, render_template, url_for

from config import Config

rules_bp = Blueprint("rules", __name__)


@rules_bp.route("/rules")
def rules():
    if not g.current_user:
        return redirect(url_for("auth.login"))

    from app import get_db_connection

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(DISTINCT user_id) FROM picks")
            total_entries = cur.fetchone()[0]
    finally:
        conn.close()

    total_pot = 240
    raw_2nd = 60
    raw_3rd = 30
    payout_1st = 150

    picks_locked = datetime.now(timezone(timedelta(hours=-4))) > datetime.fromisoformat(Config.PICKS_DEADLINE)

    return render_template(
        "rules.html",
        total_entries=total_entries,
        total_pot=total_pot,
        payout_1st=int(payout_1st),
        payout_2nd=int(raw_2nd),
        payout_3rd=int(raw_3rd),
        picks_locked=picks_locked,
    )
