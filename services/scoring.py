"""4-of-6 scoring engine.

Each user picks 6 golfers (one per tier). Only the 4 lowest cumulative
stroke totals count toward the user's pool score. If more than 2 golfers
miss the cut, forced picks receive worst-score-among-cutmakers + 1.
Tiebreakers are handled separately.
"""

import psycopg2.extras


def calculate_penalty_score(conn):
    """Return worst total_strokes among active golfers + 1, or None if no scores."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT MAX(total_strokes) FROM golfer_scores WHERE status = 'active' AND total_strokes IS NOT NULL"
        )
        row = cur.fetchone()
        if row and row[0] is not None:
            return row[0] + 1
    return None


def calculate_team_score(golfer_scores, penalty_score):
    """Calculate best-4-of-6 team score.

    Args:
        golfer_scores: list of dicts with keys:
            golfer_id, name, total_strokes, status, position, tier,
            round_1, round_2, round_3, round_4
        penalty_score: int or None, the penalty for MC/WD/DQ golfers

    Returns:
        dict with team_total, counting_golfers, bench_golfers, all_golfers
    """
    if not golfer_scores:
        return {
            "team_total": None,
            "counting_golfers": [],
            "bench_golfers": [],
            "all_golfers": [],
        }

    # Apply penalty scores for MC/WD/DQ
    scored = []
    for g in golfer_scores:
        entry = dict(g)
        if entry.get("status") in ("MC", "WD", "DQ"):
            entry["effective_strokes"] = penalty_score if penalty_score else None
        else:
            entry["effective_strokes"] = entry.get("total_strokes")
        scored.append(entry)

    # If any golfer has no effective score, we can't fully calculate
    has_scores = any(s["effective_strokes"] is not None for s in scored)
    if not has_scores:
        for s in scored:
            s["counting"] = False
        return {
            "team_total": None,
            "counting_golfers": [],
            "bench_golfers": scored,
            "all_golfers": scored,
        }

    # Sort by effective strokes (None sorts to end)
    scored.sort(key=lambda s: (s["effective_strokes"] is None, s["effective_strokes"] or 0))

    # Best 4 count, worst 2 are bench
    for i, s in enumerate(scored):
        s["counting"] = i < 4 and s["effective_strokes"] is not None

    counting = [s for s in scored if s["counting"]]
    bench = [s for s in scored if not s["counting"]]

    team_total = sum(s["effective_strokes"] for s in counting) if counting else None

    return {
        "team_total": team_total,
        "counting_golfers": counting,
        "bench_golfers": bench,
        "all_golfers": scored,
    }


def build_leaderboard(conn):
    """Build the full pool leaderboard.

    Returns a ranked list of dicts:
        user_id, username, team_total, counting_golfers, bench_golfers, rank
    """
    penalty_score = calculate_penalty_score(conn)

    # Get all users who have picks
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT DISTINCT u.id AS user_id, u.username
               FROM users u
               JOIN picks p ON p.user_id = u.id
               ORDER BY u.username"""
        )
        users = cur.fetchall()

    if not users:
        return []

    standings = []
    for user in users:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT p.tier, g.id AS golfer_id, g.name,
                          gs.total_strokes, gs.status, gs.position,
                          gs.round_1, gs.round_2, gs.round_3, gs.round_4,
                          gs.to_par, gs.thru
                   FROM picks p
                   JOIN golfers g ON p.golfer_id = g.id
                   LEFT JOIN golfer_scores gs ON gs.golfer_id = g.id
                   WHERE p.user_id = %s
                   ORDER BY p.tier""",
                (user["user_id"],),
            )
            golfer_scores = cur.fetchall()

        result = calculate_team_score(golfer_scores, penalty_score)
        standings.append({
            "user_id": user["user_id"],
            "username": user["username"],
            "team_total": result["team_total"],
            "counting_golfers": result["counting_golfers"],
            "bench_golfers": result["bench_golfers"],
            "all_golfers": result["all_golfers"],
        })

    # Sort: team_total ascending, None to bottom
    standings.sort(key=lambda s: (s["team_total"] is None, s["team_total"] or 0))

    # Apply tiebreaker and ranks
    _apply_ranks(standings)

    return standings


def _apply_ranks(standings):
    """Apply ranks with tie notation (1, 2, T3, T3, 5, etc.)."""
    if not standings:
        return

    # Group by team_total to find ties
    i = 0
    while i < len(standings):
        total = standings[i]["team_total"]
        if total is None:
            # No score yet, rank as "--"
            for j in range(i, len(standings)):
                standings[j]["rank"] = "--"
            break

        # Find all entries with same total
        j = i
        while j < len(standings) and standings[j]["team_total"] == total:
            j += 1

        tie_count = j - i
        if tie_count > 1:
            # Tiebreak by best individual finisher position
            for entry in standings[i:j]:
                best_pos = _best_position(entry["counting_golfers"])
                entry["_tiebreak"] = best_pos

            # Sort the tied group by tiebreak
            tied = standings[i:j]
            tied.sort(key=lambda s: s["_tiebreak"])
            standings[i:j] = tied

            # Check if still tied after tiebreak
            k = i
            while k < j:
                tb_val = standings[k]["_tiebreak"]
                m = k
                while m < j and standings[m]["_tiebreak"] == tb_val:
                    m += 1
                if m - k > 1:
                    # Still tied
                    for n in range(k, m):
                        standings[n]["rank"] = f"T{k + 1}"
                else:
                    standings[k]["rank"] = str(k + 1)
                k = m
        else:
            standings[i]["rank"] = str(i + 1)

        i = j


def _best_position(golfers):
    """Return the best (lowest) position number among a list of golfers.
    Position is stored as a string, so parse it. Return 9999 if none."""
    best = 9999
    for g in golfers:
        pos = g.get("position", "")
        if pos:
            try:
                # Strip T from tied positions like "T5"
                num = int(str(pos).lstrip("T").strip())
                if num < best:
                    best = num
            except (ValueError, TypeError):
                pass
    return best
