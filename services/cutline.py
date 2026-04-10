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

    # Find the score whose cumulative expected count is nearest to 50
    CUT_TARGET = 50.0
    crossing_idx = None
    best_dist = float("inf")
    for i, (tp, avg_mc, cnt, cum) in enumerate(score_cum):
        dist = abs(cum - CUT_TARGET)
        if dist < best_dist:
            best_dist = dist
            crossing_idx = i

    cutline_probs = []
    if crossing_idx is not None:
        # Center 3-score band on the nearest-to-50 score
        n = len(score_cum)
        if crossing_idx == 0:
            start, end = 0, min(n, 3)
        elif crossing_idx >= n - 1:
            start, end = max(0, n - 3), n
        else:
            start, end = crossing_idx - 1, crossing_idx + 2
        candidates = score_cum[start:end]

        # Weight each score by inverse distance from the crossing target
        weights = []
        for tp, avg_mc, cnt, cum in candidates:
            dist = abs(cum - CUT_TARGET) + 0.1
            weights.append((tp, 1.0 / dist))

        total_w = sum(w for _, w in weights)
        cutline_probs = [(tp, w / total_w) for tp, w in weights]

    logger.info("Cutline probs (raw): %s",
                 [(tp, f"{p:.0%}") for tp, p in cutline_probs])

    # Sharpen probabilities based on round completion
    if cutline_probs:
        active = [s for s in scores_with_mc if s.get("status") == "active"]
        finished = sum(1 for s in active if s.get("thru") == "F")
        total_active = len(active)
        completion_ratio = finished / total_active if total_active else 0.0

        sharpening_factor = 1 + (completion_ratio * 50)
        sharpened = [(tp, p ** sharpening_factor) for tp, p in cutline_probs]
        total_s = sum(p for _, p in sharpened)
        if total_s > 0:
            cutline_probs = [(tp, p / total_s) for tp, p in sharpened]

        logger.info("Cutline sharpening: %.0f%% complete, factor %.1f",
                     completion_ratio * 100, sharpening_factor)
        logger.info("Cutline probs (sharpened): %s",
                     [(tp, f"{p:.0%}") for tp, p in cutline_probs])

    return cutline_probs
