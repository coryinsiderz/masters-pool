import psycopg2.extras
from flask import Blueprint, g, jsonify, redirect, render_template, url_for

from services.scoring import build_leaderboard

leaderboard_bp = Blueprint("leaderboard", __name__)

TIER_NAMES = {
    1: "Tier 1",
    2: "Strong Side",
    3: "Weak Side",
    4: "Maybe",
    5: "Meh",
    6: "Miracles",
}


def _get_ownership_data(conn):
    """Get ownership counts and owner names for each golfer."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT COUNT(DISTINCT user_id) FROM picks")
        total_users = cur.fetchone()["count"]
        cur.execute(
            """SELECT golfer_id, COUNT(*) AS cnt
               FROM picks GROUP BY golfer_id"""
        )
        counts = {r["golfer_id"]: r["cnt"] for r in cur.fetchall()}
        cur.execute(
            """SELECT p.golfer_id, u.username
               FROM picks p JOIN users u ON p.user_id = u.id
               ORDER BY u.username"""
        )
        owner_names = {}
        for r in cur.fetchall():
            owner_names.setdefault(r["golfer_id"], []).append(r["username"])
    return total_users, counts, owner_names


def _build_full_leaderboard(conn):
    """Build leaderboard with per-tier golfer data and ownership."""
    standings = build_leaderboard(conn)
    total_users, ownership, owner_names = _get_ownership_data(conn)

    result = []
    for entry in standings:
        # Build per-tier golfer map
        tiers = {}
        for g in entry.get("all_golfers", []):
            tier = g.get("tier")
            if tier is None:
                continue
            gid = g.get("golfer_id")
            own_count = ownership.get(gid, 0)
            own_pct = round(own_count / total_users * 100) if total_users else 0
            tiers[tier] = {
                "name": g.get("name", ""),
                "tier": tier,
                "to_par": g.get("to_par", ""),
                "total_strokes": g.get("effective_strokes") or g.get("total_strokes"),
                "thru": g.get("thru", ""),
                "status": g.get("status", "active"),
                "is_counting": g.get("counting", False),
                "ownership_count": own_count,
                "ownership_pct": own_pct,
                "owners": owner_names.get(gid, []),
                "position": g.get("position", ""),
                "round_1": g.get("round_1"),
                "round_2": g.get("round_2"),
                "round_3": g.get("round_3"),
                "round_4": g.get("round_4"),
            }

        # Calculate team to-par total
        counting = [t for t in tiers.values() if t["is_counting"]]
        team_to_par = _sum_to_par(counting)

        result.append({
            "user_id": entry["user_id"],
            "username": entry["username"],
            "rank": entry["rank"],
            "team_total": entry["team_total"],
            "team_to_par": team_to_par,
            "tiers": tiers,
        })

    return result, total_users


def _sum_to_par(counting_golfers):
    """Sum to-par strings for counting golfers. Returns string like '-12' or '+4' or 'E'."""
    total = 0
    has_scores = False
    for g in counting_golfers:
        tp = g.get("to_par", "")
        if not tp:
            continue
        has_scores = True
        if tp == "E":
            pass
        else:
            try:
                total += int(tp)
            except (ValueError, TypeError):
                pass
    if not has_scores:
        return "--"
    if total == 0:
        return "E"
    elif total > 0:
        return f"+{total}"
    else:
        return str(total)


@leaderboard_bp.route("/leaderboard")
@leaderboard_bp.route("/")
def leaderboard():
    if not g.current_user:
        return redirect(url_for("auth.login"))
    from app import get_db_connection
    conn = get_db_connection()
    standings, total_users = _build_full_leaderboard(conn)
    conn.close()
    return render_template(
        "leaderboard.html",
        standings=standings,
        total_users=total_users,
        tier_names=TIER_NAMES,
    )


@leaderboard_bp.route("/api/leaderboard")
def api_leaderboard():
    if not g.current_user:
        return jsonify({"error": "unauthorized"}), 401
    from app import get_db_connection
    conn = get_db_connection()
    standings, total_users = _build_full_leaderboard(conn)
    conn.close()
    return jsonify({"standings": standings, "total_users": total_users})
