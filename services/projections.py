"""Service for fetching and processing projections from external API."""

import logging
import os
from datetime import datetime, timezone

import psycopg2.extras
import requests

logger = logging.getLogger(__name__)

PROJECTIONS_BASE_URL = "https://gbt.up.railway.app/api"
MC_PENALTY_SCORE = 10  # configurable penalty for likely-MC golfers


def _get_api_key():
    key = os.environ.get("PROJECTIONS_API_KEY") or os.environ.get("DG_API_KEY")
    if not key:
        raise RuntimeError("No PROJECTIONS_API_KEY or DG_API_KEY in environment")
    return key


def _extract_last_name(name):
    """Extract last name from 'Last, First' or 'First Last' format, case-insensitive."""
    if not name:
        return ""
    name = name.strip()
    if "," in name:
        return name.split(",")[0].strip().lower()
    parts = name.split()
    return parts[-1].strip().lower() if parts else ""


def _build_golfer_lookup(conn):
    """Build a dict mapping lowercase last names to golfer records.

    Prefers dg_name over name for matching. If multiple golfers share a last
    name, stores a list so callers can handle ambiguity.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT id, name, dg_name, tier FROM golfers ORDER BY name")
        golfers = cur.fetchall()

    lookup = {}
    for g in golfers:
        match_name = g["dg_name"] or g["name"]
        last = _extract_last_name(match_name)
        if last in lookup:
            # Multiple golfers with same last name — store as list
            if isinstance(lookup[last], list):
                lookup[last].append(g)
            else:
                lookup[last] = [lookup[last], g]
        else:
            lookup[last] = g
    return lookup


def _match_player(api_name, lookup):
    """Match an API player name against our golfer lookup.

    Returns golfer dict or None. For duplicate last names, tries full-name
    match on first name as tiebreaker.
    """
    last = _extract_last_name(api_name)
    hit = lookup.get(last)
    if hit is None:
        return None
    if isinstance(hit, list):
        # Multiple golfers with same last name — try first-name match
        api_first = ""
        if "," in api_name:
            parts = api_name.split(",", 1)
            api_first = parts[1].strip().lower() if len(parts) > 1 else ""
        else:
            parts = api_name.split()
            api_first = parts[0].strip().lower() if parts else ""

        for g in hit:
            match_name = g["dg_name"] or g["name"]
            if "," in match_name:
                g_first = match_name.split(",", 1)[1].strip().lower()
            else:
                g_first = match_name.split()[0].strip().lower() if match_name.split() else ""
            if g_first == api_first:
                return g
        # No first-name match found
        return None
    return hit


def fetch_projections(conn):
    """Fetch pre-tournament projections and insert into golfer_projections.

    Returns dict with 'matched' and 'unmatched' counts.
    """
    key = _get_api_key()
    url = f"{PROJECTIONS_BASE_URL}/projections"
    try:
        r = requests.get(
            url,
            params={"tour": "pga"},
            headers={"X-API-Key": key},
            timeout=15,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        logger.error("Failed to fetch projections: %s", e)
        return {"matched": 0, "unmatched": 0, "error": str(e)}

    data = r.json()
    # Handle both list and dict-with-list response shapes
    players = data if isinstance(data, list) else data.get("baseline", data.get("data", []))

    lookup = _build_golfer_lookup(conn)
    now = datetime.now(timezone.utc)
    matched = 0
    unmatched = []

    with conn.cursor() as cur:
        for p in players:
            name = p.get("player_name", "")
            golfer = _match_player(name, lookup)
            if golfer:
                cur.execute(
                    """INSERT INTO golfer_projections
                       (golfer_id, projected_to_par, mc_probability, win_probability, snapshot_time)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (
                        golfer["id"],
                        p.get("projected_to_par"),
                        p.get("mc_probability", 1.0 - p.get("make_cut", 0.5)),
                        p.get("win", p.get("win_probability", 0)),
                        now,
                    ),
                )
                matched += 1
                logger.debug("Matched: %s -> golfer %d (%s)", name, golfer["id"], golfer["name"])
            else:
                unmatched.append(name)

    if unmatched:
        logger.info("Unmatched players (%d): %s", len(unmatched), ", ".join(unmatched[:20]))

    return {"matched": matched, "unmatched": len(unmatched), "unmatched_names": unmatched}


def fetch_live_projections(conn):
    """Fetch in-play live projections and insert into golfer_projections.

    Same logic as fetch_projections but hits the /live endpoint.
    Returns dict with 'matched' and 'unmatched' counts.
    """
    key = _get_api_key()
    url = f"{PROJECTIONS_BASE_URL}/projections/live"
    try:
        r = requests.get(
            url,
            params={"tour": "pga"},
            headers={"X-API-Key": key},
            timeout=15,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        logger.error("Failed to fetch live projections: %s", e)
        return {"matched": 0, "unmatched": 0, "error": str(e)}

    data = r.json()
    players = data if isinstance(data, list) else data.get("players", data.get("data", []))

    lookup = _build_golfer_lookup(conn)
    now = datetime.now(timezone.utc)
    matched = 0
    unmatched = []

    with conn.cursor() as cur:
        for p in players:
            name = p.get("player_name", "")
            golfer = _match_player(name, lookup)
            if golfer:
                cur.execute(
                    """INSERT INTO golfer_projections
                       (golfer_id, projected_to_par, actual_to_par, mc_probability, win_probability, snapshot_time)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (
                        golfer["id"],
                        p.get("projected_to_par", p.get("to_par")),
                        p.get("actual_to_par"),
                        p.get("mc_probability", 1.0 - p.get("make_cut", 0.5)),
                        p.get("win", p.get("win_probability", 0)),
                        now,
                    ),
                )
                matched += 1
            else:
                unmatched.append(name)

    if unmatched:
        logger.info("Live unmatched (%d): %s", len(unmatched), ", ".join(unmatched[:20]))

    return {"matched": matched, "unmatched": len(unmatched), "unmatched_names": unmatched}


def compute_team_projections(conn, snapshot_time=None):
    """Compute projected and actual totals for each user using best-4-of-6 scoring.

    For golfers with mc_probability > 0.5 and no actual MC status yet,
    applies MC_PENALTY_SCORE instead of their projected_to_par.

    Returns dict of {user_id: {"projected_total": x, "actual_total": y}}.
    """
    if snapshot_time is None:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(snapshot_time) FROM golfer_projections")
            row = cur.fetchone()
            snapshot_time = row[0] if row and row[0] else None
    if not snapshot_time:
        logger.warning("No projection snapshots found")
        return {}

    # Get all users with picks
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT p.user_id, p.golfer_id, g.name
               FROM picks p
               JOIN golfers g ON p.golfer_id = g.id
               ORDER BY p.user_id, p.tier"""
        )
        all_picks = cur.fetchall()

    # Get latest projections at or before the snapshot time
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT DISTINCT ON (golfer_id)
                      golfer_id, projected_to_par, actual_to_par, mc_probability
               FROM golfer_projections
               WHERE snapshot_time <= %s
               ORDER BY golfer_id, snapshot_time DESC""",
            (snapshot_time,),
        )
        proj_map = {r["golfer_id"]: r for r in cur.fetchall()}

    # Get actual to_par from ESPN scoring data
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT golfer_id, to_par, status, thru
               FROM golfer_scores"""
        )
        espn_scores = {r["golfer_id"]: r for r in cur.fetchall()}

    # Get actual MC statuses from golfer_scores
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT golfer_id, status FROM golfer_scores WHERE status = 'cut'")
        actual_mc = {r["golfer_id"] for r in cur.fetchall()}

    # Group picks by user
    from collections import defaultdict
    user_picks = defaultdict(list)
    for pick in all_picks:
        user_picks[pick["user_id"]].append(pick)

    results = {}
    now = datetime.now(timezone.utc)

    with conn.cursor() as cur:
        for user_id, picks in user_picks.items():
            proj_scores = []
            actual_scores = []

            for pick in picks:
                gid = pick["golfer_id"]
                proj = proj_map.get(gid)
                if proj is None:
                    proj_scores.append(MC_PENALTY_SCORE)
                    continue

                to_par = proj["projected_to_par"]
                actual = proj["actual_to_par"]
                mc_prob = proj["mc_probability"] or 0
                is_mc = gid in actual_mc

                # Projected score
                if is_mc:
                    proj_scores.append(MC_PENALTY_SCORE)
                elif mc_prob > 0.5 and to_par is None:
                    proj_scores.append(MC_PENALTY_SCORE)
                elif to_par is not None:
                    proj_scores.append(float(to_par))
                else:
                    proj_scores.append(MC_PENALTY_SCORE)

                # Actual score from ESPN data
                espn = espn_scores.get(gid)
                if is_mc:
                    actual_scores.append(MC_PENALTY_SCORE)
                elif espn:
                    espn_tp = espn.get("to_par", "")
                    espn_thru = espn.get("thru", "")
                    if espn_tp == "E" and espn_thru:
                        actual_scores.append(0.0)
                    elif espn_tp and espn_tp not in ("", "--", "E"):
                        try:
                            actual_scores.append(float(int(espn_tp)))
                        except (ValueError, TypeError):
                            pass
                    elif espn_tp == "E" and not espn_thru:
                        pass  # hasn't started
                # else: no ESPN data, skip

            # Best 4 of 6 for projected
            proj_scores.sort()
            projected_total = sum(proj_scores[:4]) if len(proj_scores) >= 4 else sum(proj_scores)

            # Best 4 of 6 for actual (null if fewer than 4 have scores)
            actual_total = None
            if len(actual_scores) >= 4:
                actual_scores.sort()
                actual_total = sum(actual_scores[:4])

            results[user_id] = {
                "projected_total": projected_total,
                "actual_total": actual_total,
            }

            cur.execute(
                """INSERT INTO team_projections
                   (user_id, projected_total, actual_total, snapshot_time)
                   VALUES (%s, %s, %s, %s)""",
                (user_id, projected_total, actual_total, now),
            )

    logger.info("Computed team projections for %d users", len(results))
    return results


def match_dg_names(conn):
    """One-time setup: match API player names to our golfers by last name.

    Updates golfers.dg_name for confirmed matches.
    Returns dict with match stats and unmatched lists.
    """
    key = _get_api_key()

    # Fetch field from the projections API
    url = f"{PROJECTIONS_BASE_URL}/projections"
    try:
        r = requests.get(
            url,
            params={"tour": "pga"},
            headers={"X-API-Key": key},
            timeout=15,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        logger.error("Failed to fetch field for name matching: %s", e)
        return {"error": str(e)}

    data = r.json()
    api_players = data if isinstance(data, list) else data.get("baseline", data.get("data", []))

    # Get all our golfers
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT id, name, dg_name FROM golfers ORDER BY name")
        our_golfers = cur.fetchall()

    # Build lookup from our golfers by last name
    our_lookup = {}
    for g in our_golfers:
        last = _extract_last_name(g["name"])
        if last in our_lookup:
            if isinstance(our_lookup[last], list):
                our_lookup[last].append(g)
            else:
                our_lookup[last] = [our_lookup[last], g]
        else:
            our_lookup[last] = g

    matched = 0
    unmatched_api = []
    matched_pairs = []

    with conn.cursor() as cur:
        for p in api_players:
            api_name = p.get("player_name", "")
            api_last = _extract_last_name(api_name)
            hit = our_lookup.get(api_last)

            if hit is None:
                unmatched_api.append(api_name)
                continue

            # Resolve ambiguity for duplicate last names
            if isinstance(hit, list):
                # Try first-name match
                api_first = ""
                if "," in api_name:
                    parts = api_name.split(",", 1)
                    api_first = parts[1].strip().lower()
                else:
                    parts = api_name.split()
                    api_first = parts[0].strip().lower() if parts else ""

                resolved = None
                for g in hit:
                    g_name = g["name"]
                    if "," in g_name:
                        g_first = g_name.split(",", 1)[1].strip().lower()
                    else:
                        g_first = g_name.split()[0].strip().lower() if g_name.split() else ""
                    if g_first == api_first:
                        resolved = g
                        break
                if resolved is None:
                    unmatched_api.append(f"{api_name} (ambiguous: {[x['name'] for x in hit]})")
                    continue
                hit = resolved

            # Update dg_name
            cur.execute(
                "UPDATE golfers SET dg_name = %s WHERE id = %s",
                (api_name, hit["id"]),
            )
            matched_pairs.append((api_name, hit["name"]))
            matched += 1

    # Find our golfers that weren't matched
    matched_ids = {pair[1] for pair in matched_pairs}
    unmatched_ours = [g["name"] for g in our_golfers if g["name"] not in matched_ids]

    logger.info("Name matching: %d matched, %d API unmatched, %d ours unmatched",
                matched, len(unmatched_api), len(unmatched_ours))

    return {
        "matched": matched,
        "unmatched_api": unmatched_api,
        "unmatched_ours": unmatched_ours,
        "matched_pairs": matched_pairs,
    }
