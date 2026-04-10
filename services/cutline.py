"""Cutline projection utilities.

Computes projected cut probabilities using a top-50-and-ties
cumulative expected model based on golfer_projections mc_probability.
"""

import logging
from collections import defaultdict

import psycopg2.extras

logger = logging.getLogger(__name__)


def _to_par_sort_key(tp):
    if tp == "E":
        return 0
    try:
        return int(tp)
    except (ValueError, TypeError):
        return 999


def get_mc_map(conn):
    """Fetch mc_probability per golfer from the latest projection snapshot.

    Returns dict {golfer_id: float} or empty dict if no data.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT gp.golfer_id, gp.mc_probability
               FROM golfer_projections gp
               WHERE gp.snapshot_time = (SELECT MAX(snapshot_time) FROM golfer_projections)"""
        )
        return {
            row["golfer_id"]: float(row["mc_probability"])
            for row in cur.fetchall()
            if row["mc_probability"] is not None
        }


def compute_cutline_probs(scores_with_mc):
    """Compute projected cut probabilities from scored golfer data.

    Args:
        scores_with_mc: list of dicts, each with at least 'status', 'to_par',
                        and 'mc_probability' keys.

    Returns:
        list of (score_str, probability) tuples, sorted by score.
        Typically 3 entries around the projected cut line.
        Empty list if insufficient data.
    """
    # Group active golfers by to_par
    score_groups = defaultdict(list)
    for s in scores_with_mc:
        if s.get("status") == "active" and s.get("mc_probability") is not None:
            score_groups[s.get("to_par", "")].append(s["mc_probability"])

    if not score_groups:
        return []

    # Build sorted list of (score, avg_mc, count)
    sorted_scores = []
    for tp in sorted(score_groups.keys(), key=_to_par_sort_key):
        probs = score_groups[tp]
        avg_mc = sum(probs) / len(probs)
        sorted_scores.append((tp, avg_mc, len(probs)))

    # Compute cumulative expected count (top 50 and ties)
    cum_expected = 0.0
    score_cum = []
    for tp, avg_mc, cnt in sorted_scores:
        contribution = cnt * avg_mc
        cum_expected += contribution
        score_cum.append((tp, avg_mc, cnt, cum_expected))

    logger.info("Cutline score groups (cumulative expected):")
    for tp, avg_mc, cnt, cum in score_cum:
        logger.info("  %4s: %2d golfers, avg MC %.1f%%, cum expected %.1f",
                     tp, cnt, avg_mc * 100, cum)

    # Find the crossing point: score where cum_expected first reaches ~50
    CUT_TARGET = 50.0
    crossing_idx = None
    for i, (tp, avg_mc, cnt, cum) in enumerate(score_cum):
        if cum >= CUT_TARGET:
            crossing_idx = i
            break

    cutline_probs = []
    if crossing_idx is not None:
        # Take up to 1 score before and 1 after the crossing point
        start = max(0, crossing_idx - 1)
        end = min(len(score_cum), crossing_idx + 2)
        candidates = score_cum[start:end]

        # Weight each score by inverse distance from the crossing target
        weights = []
        for tp, avg_mc, cnt, cum in candidates:
            dist = abs(cum - CUT_TARGET) + 0.1
            weights.append((tp, 1.0 / dist))

        total_w = sum(w for _, w in weights)
        cutline_probs = [(tp, w / total_w) for tp, w in weights]

    logger.info("Cutline probs: %s",
                 [(tp, f"{p:.0%}") for tp, p in cutline_probs])

    return cutline_probs
