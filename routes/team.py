from datetime import datetime, timedelta, timezone

import psycopg2.extras
from flask import Blueprint, g, jsonify, redirect, render_template, url_for

from config import Config
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
    7: "X",
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

    # Cutline projection data (before conn.close)
    cutline_probs = []
    show_cut = Config.SHOW_CUT_PROJECTIONS and current_round <= 2
    if show_cut:
        from services.cutline import get_mc_map, compute_cutline_probs
        from models.tournament import get_all_scores
        mc_map = get_mc_map(conn)
        all_scores = get_all_scores(conn)
        for s in all_scores:
            s["mc_probability"] = mc_map.get(s.get("golfer_id"))
        cutline_probs = compute_cutline_probs(all_scores)

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
            "masters_id": pick.get("masters_id"),
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
            "current_round_par": score.get("current_round_par"),
            "mc_pct": round(mc_map.get(pick["golfer_id"], 0) * 100) if show_cut and mc_map else None,
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
        show_cut_projections=show_cut,
        cutline_probs=cutline_probs,
    )


def _is_picks_locked():
    deadline = datetime.fromisoformat(Config.PICKS_DEADLINE)
    now = datetime.now(timezone(timedelta(hours=-4)))
    return now > deadline


@team_bp.route("/api/teams/summary")
def teams_summary():
    if not g.current_user:
        return jsonify({"error": "Login required"}), 401
    if not _is_picks_locked():
        return jsonify({"error": "Picks are not yet locked"}), 403

    from app import format_display_name, get_db_connection

    conn = get_db_connection()

    # Get all users who have picks
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT DISTINCT u.id, u.username
               FROM users u JOIN picks p ON u.id = p.user_id
               ORDER BY u.username"""
        )
        users = cur.fetchall()

    # Fetch all picks and scores in bulk
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT p.user_id, p.tier, p.golfer_id, g.name AS golfer_name
               FROM picks p JOIN golfers g ON p.golfer_id = g.id
               ORDER BY p.user_id, p.tier"""
        )
        all_picks = cur.fetchall()

    all_golfer_ids = list({p["golfer_id"] for p in all_picks})
    scores = get_scores_for_golfers(conn, all_golfer_ids) if all_golfer_ids else []
    conn.close()

    scores_by_id = {s["golfer_id"]: s for s in scores}

    # Group picks by user
    picks_by_user = {}
    for p in all_picks:
        picks_by_user.setdefault(p["user_id"], []).append(p)

    result = []
    for user in users:
        user_picks = picks_by_user.get(user["id"], [])
        cards = []
        for pick in user_picks:
            score = scores_by_id.get(pick["golfer_id"], {})
            cards.append({"to_par": score.get("to_par", ""), "total_strokes": score.get("total_strokes")})
        team_to_par = _calc_team_to_par(cards)
        result.append({
            "user_id": user["id"],
            "username": user["username"],
            "display_name": format_display_name(user["username"]),
            "team_to_par": team_to_par,
        })

    return jsonify(result)


@team_bp.route("/api/team/<int:user_id>")
def team_detail(user_id):
    if not g.current_user:
        return jsonify({"error": "Login required"}), 401
    if not _is_picks_locked():
        return jsonify({"error": "Picks are not yet locked"}), 403

    from app import format_display_name, format_ordinal, get_db_connection

    conn = get_db_connection()
    picks = get_picks_for_user(conn, user_id)
    if not picks:
        conn.close()
        return jsonify({"error": "No picks found for this user"}), 404

    golfer_ids = [p["golfer_id"] for p in picks]
    scores = get_scores_for_golfers(conn, golfer_ids)
    tournament = get_tournament_state(conn)
    current_round = tournament.get("current_round", 0) if tournament else 0

    # Ownership data
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT COUNT(DISTINCT user_id) AS cnt FROM picks")
        total_users = cur.fetchone()["cnt"]
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

    # Get username for this user_id
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        user_row = cur.fetchone()

    # MC probability for API response
    show_cut_api = Config.SHOW_CUT_PROJECTIONS and current_round <= 2
    mc_map_api = {}
    if show_cut_api:
        from services.cutline import get_mc_map
        mc_map_api = get_mc_map(conn)

    conn.close()

    username = user_row["username"] if user_row else ""
    scores_by_id = {s["golfer_id"]: s for s in scores}

    cards = []
    for pick in picks:
        score = scores_by_id.get(pick["golfer_id"], {})
        gid = pick["golfer_id"]
        own_count = ownership.get(gid, 0)
        own_pct = round(own_count / total_users * 100) if total_users else 0

        # Format position with ordinal
        pos_raw = score.get("position", "")
        status = score.get("status", "active")
        if status in ("MC", "WD", "DQ"):
            pos_display = status
        elif pos_raw:
            pos_display = format_ordinal(pos_raw)
        else:
            pos_display = "--"

        # Format thru
        thru = score.get("thru", "")
        if status in ("MC", "WD", "DQ"):
            thru_display = ""
        elif thru and thru != "F":
            thru_display = f"Thru {thru}"
        else:
            thru_display = ""

        cards.append({
            "tier_name": TIER_NAMES.get(pick["tier"], str(pick["tier"])),
            "name": pick["golfer_name"],
            "masters_id": pick.get("masters_id"),
            "to_par": score.get("to_par", "") or "--",
            "total_strokes": score.get("total_strokes"),
            "position": pos_display,
            "thru": thru_display,
            "status": status,
            "ownership_pct": own_pct,
            "owners": ", ".join(format_display_name(n) for n in owner_names.get(gid, [])),
            "round_1": score.get("round_1"),
            "round_2": score.get("round_2"),
            "round_3": score.get("round_3"),
            "round_4": score.get("round_4"),
            "current_round": current_round,
            "current_round_par": score.get("current_round_par"),
            "mc_pct": round(mc_map_api.get(gid, 0) * 100) if show_cut_api and mc_map_api else None,
        })

    _mark_counting(cards)
    team_to_par = _calc_team_to_par(cards)

    return jsonify({
        "username": username,
        "display_name": format_display_name(username),
        "team_to_par": team_to_par,
        "cards": [{
            "tier_name": c["tier_name"],
            "name": c["name"],
            "masters_id": c.get("masters_id"),
            "to_par": c["to_par"],
            "position": c["position"],
            "thru": c["thru"],
            "status": c["status"],
            "ownership_pct": c["ownership_pct"],
            "owners": c["owners"],
            "counting": c["counting"],
            "round_1": c["round_1"],
            "round_2": c["round_2"],
            "round_3": c["round_3"],
            "round_4": c["round_4"],
            "current_round": c["current_round"],
            "current_round_par": c["current_round_par"],
            "mc_pct": c.get("mc_pct"),
        } for c in cards],
    })


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
