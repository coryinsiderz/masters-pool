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

    # Join mc_probability from latest projection snapshot (rounds 1-2 only)
    current_round = tournament.get("current_round", 0) if tournament else 0
    projected_cut_score = None
    cutline_probs = []
    if current_round <= 2:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT gp.golfer_id, gp.mc_probability
                   FROM golfer_projections gp
                   WHERE gp.snapshot_time = (SELECT MAX(snapshot_time) FROM golfer_projections)"""
            )
            mc_map = {row["golfer_id"]: float(row["mc_probability"]) for row in cur.fetchall() if row["mc_probability"] is not None}

        for s in all_scores:
            s["mc_probability"] = mc_map.get(s.get("golfer_id"))

        # Compute multi-level cutline probabilities using top-50-and-ties model
        import logging
        _log = logging.getLogger(__name__)

        from collections import defaultdict
        score_groups = defaultdict(list)
        for s in all_scores:
            if s.get("status") == "active" and s.get("mc_probability") is not None:
                score_groups[s.get("to_par", "")].append(s["mc_probability"])

        def _to_par_sort_key(tp):
            if tp == "E":
                return 0
            try:
                return int(tp)
            except (ValueError, TypeError):
                return 999

        # Build sorted list of (score, avg_mc, count)
        sorted_scores = []
        for tp in sorted(score_groups.keys(), key=_to_par_sort_key):
            probs = score_groups[tp]
            avg_mc = sum(probs) / len(probs)
            sorted_scores.append((tp, avg_mc, len(probs)))

        # Compute cumulative expected count (top 50 and ties)
        cum_expected = 0.0
        score_cum = []  # (score, avg_mc, count, cum_expected_after)
        for tp, avg_mc, cnt in sorted_scores:
            contribution = cnt * avg_mc
            cum_expected += contribution
            score_cum.append((tp, avg_mc, cnt, cum_expected))

        _log.info("Cutline score groups (cumulative expected):")
        for tp, avg_mc, cnt, cum in score_cum:
            _log.info("  %4s: %2d golfers, avg MC %.1f%%, cum expected %.1f",
                       tp, cnt, avg_mc * 100, cum)

        # Find the crossing point: score where cum_expected first reaches ~50
        # Take the 3 consecutive scores around that crossing
        CUT_TARGET = 50.0
        crossing_idx = None
        for i, (tp, avg_mc, cnt, cum) in enumerate(score_cum):
            if cum >= CUT_TARGET:
                crossing_idx = i
                break

        if crossing_idx is not None:
            # Take up to 1 score before and 1 after the crossing point
            start = max(0, crossing_idx - 1)
            end = min(len(score_cum), crossing_idx + 2)
            candidates = score_cum[start:end]

            # Weight each score by inverse distance from the crossing target
            # The score whose cumulative is closest to 50 gets highest weight
            weights = []
            for tp, avg_mc, cnt, cum in candidates:
                dist = abs(cum - CUT_TARGET) + 0.1  # avoid div by zero
                weights.append((tp, 1.0 / dist))

            total_w = sum(w for _, w in weights)
            cutline_probs = [(tp, w / total_w) for tp, w in weights]
            # Already sorted by score (candidates came from sorted list)

        _log.info("Cutline probs: %s",
                   [(tp, f"{p:.0%}") for tp, p in cutline_probs])
    else:
        for s in all_scores:
            s["mc_probability"] = None

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
        projected_cut_score=projected_cut_score,
        cutline_probs=cutline_probs,
    )


def _parse_position(pos):
    if not pos:
        return 9999
    try:
        return int(str(pos).lstrip("T").strip())
    except (ValueError, TypeError):
        return 9999
