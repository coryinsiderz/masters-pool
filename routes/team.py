import psycopg2.extras
from flask import Blueprint, g, redirect, render_template, url_for

from models.pick import get_picks_for_user
from models.tournament import get_scores_for_golfers, get_tournament_state

team_bp = Blueprint("team", __name__)

TIER_NAMES = {
    1: "Tier 1",
    2: "Strong Side",
    3: "Weak Side",
    4: "Maybe",
    5: "Meh",
    6: "Do You Believe in Miracles",
}


@team_bp.route("/team")
def team():
    if not g.current_user:
        return redirect(url_for("auth.login"))

    from app import get_db_connection
    conn = get_db_connection()
    picks = get_picks_for_user(conn, g.current_user["id"])
    golfer_ids = [p["golfer_id"] for p in picks]
    scores = get_scores_for_golfers(conn, golfer_ids) if golfer_ids else []
    tournament = get_tournament_state(conn)
    current_round = tournament.get("current_round", 0) if tournament else 0

    # Get ownership data
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT COUNT(DISTINCT user_id) AS cnt FROM picks")
        total_users = cur.fetchone()["cnt"]
        if golfer_ids:
            cur.execute(
                "SELECT golfer_id, COUNT(*) AS cnt FROM picks WHERE golfer_id = ANY(%s) GROUP BY golfer_id",
                (golfer_ids,),
            )
            ownership = {r["golfer_id"]: r["cnt"] for r in cur.fetchall()}
            cur.execute(
                """SELECT p.golfer_id, u.username
                   FROM picks p JOIN users u ON p.user_id = u.id
                   WHERE p.golfer_id = ANY(%s)
                   ORDER BY u.username""",
                (golfer_ids,),
            )
            owner_names = {}
            for r in cur.fetchall():
                owner_names.setdefault(r["golfer_id"], []).append(r["username"])
        else:
            ownership = {}
            owner_names = {}
    conn.close()

    scores_by_id = {s["golfer_id"]: s for s in scores}

    # Build golfer cards with merged pick + score data
    cards = []
    for pick in picks:
        score = scores_by_id.get(pick["golfer_id"], {})
        gid = pick["golfer_id"]
        own_count = ownership.get(gid, 0)
        own_pct = round(own_count / total_users * 100) if total_users else 0
        cards.append({
            "tier": pick["tier"],
            "tier_name": TIER_NAMES.get(pick["tier"], str(pick["tier"])),
            "name": pick["golfer_name"],
            "ownership_pct": own_pct,
            "ownership_count": own_count,
            "owners": owner_names.get(gid, []),
            "to_par": score.get("to_par", ""),
            "total_strokes": score.get("total_strokes"),
            "position": score.get("position", ""),
            "thru": score.get("thru", ""),
            "status": score.get("status", "active"),
            "round_1": score.get("round_1"),
            "round_2": score.get("round_2"),
            "round_3": score.get("round_3"),
            "round_4": score.get("round_4"),
        })

    # Calculate team to-par and mark counting golfers
    team_to_par = _calc_team_to_par(cards)
    _mark_counting(cards)

    return render_template(
        "team.html",
        cards=cards,
        team_to_par=team_to_par,
        has_picks=len(picks) > 0,
        total_users=total_users,
        current_round=current_round,
    )


def _mark_counting(cards):
    """Mark the best 4 of 6 cards as counting based on total_strokes."""
    scored = []
    for i, c in enumerate(cards):
        ts = c.get("total_strokes")
        scored.append((i, ts))
    # Sort by total_strokes ascending, None to end
    scored.sort(key=lambda x: (x[1] is None, x[1] or 0))
    counting_indices = {scored[j][0] for j in range(min(4, len(scored))) if scored[j][1] is not None}
    for i, c in enumerate(cards):
        c["counting"] = i in counting_indices


def _calc_team_to_par(cards):
    """Sum the best 4 to-par scores from 6 golfers."""
    pars = []
    for c in cards:
        tp = c.get("to_par", "")
        if not tp:
            continue
        if tp == "E":
            pars.append(0)
        else:
            try:
                pars.append(int(tp))
            except (ValueError, TypeError):
                continue
    if not pars:
        return "--"
    pars.sort()
    best4 = pars[:4]
    total = sum(best4)
    if total == 0:
        return "E"
    elif total > 0:
        return f"+{total}"
    return str(total)
