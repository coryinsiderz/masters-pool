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

    total_pot = total_entries * 10
    raw_2nd = round((total_pot * 0.25) / 5) * 5
    raw_3rd = round((total_pot * 0.15) / 5) * 5
    payout_1st = total_pot - raw_2nd - raw_3rd

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
