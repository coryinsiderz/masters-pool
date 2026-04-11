"""ESPN API polling service.

Polls ESPN's unofficial golf scoreboard endpoint to fetch live tournament
scores. The endpoint can change without notice, so all field access must
handle missing or malformed data gracefully. Responses should be cached
to avoid excessive polling.
"""

import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/golf/pga/scoreboard"
)

HEADERS = {
    "User-Agent": "BaltzMastersPool/1.0 (golf pool tracker)",
}


def fetch_leaderboard():
    """Fetch raw JSON from the ESPN golf scoreboard endpoint."""
    try:
        resp = requests.get(ESPN_SCOREBOARD_URL, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        logger.info(
            "ESPN fetch success at %s", datetime.now(timezone.utc).isoformat()
        )
        return data
    except requests.exceptions.Timeout:
        logger.error("ESPN fetch timed out")
        return None
    except requests.exceptions.ConnectionError:
        logger.error("ESPN fetch connection error")
        return None
    except requests.exceptions.HTTPError as e:
        logger.error("ESPN fetch HTTP error: %s", e)
        return None
    except Exception as e:
        logger.error("ESPN fetch unexpected error: %s", e)
        return None


def parse_leaderboard(data):
    """Parse raw ESPN JSON into tournament info and golfer scores.

    Returns a dict with keys:
        tournament: {name, event_id, status, current_round}
        golfers: [{espn_id, name, position, total_strokes, to_par,
                   round_1, round_2, round_3, round_4, status, thru}]
    """
    if not data:
        return None

    events = data.get("events", [])
    if not events:
        logger.warning("No events in ESPN response")
        return None

    event = events[0]
    competitions = event.get("competitions", [])
    if not competitions:
        logger.warning("No competitions in ESPN event")
        return None

    comp = competitions[0]
    comp_status = comp.get("status", {})
    status_type = comp_status.get("type", {})
    state = status_type.get("state", "pre")
    current_round = comp_status.get("period", 0)

    # Map ESPN state to our status values
    status_map = {"pre": "pre", "in": "active", "post": "complete"}
    tournament_status = status_map.get(state, "pre")

    tournament = {
        "name": event.get("name", ""),
        "event_id": str(event.get("id", "")),
        "status": tournament_status,
        "current_round": current_round,
    }

    golfers = []
    competitors = comp.get("competitors", [])
    for competitor in competitors:
        athlete = competitor.get("athlete", {})
        espn_id = str(competitor.get("id", ""))
        name = athlete.get("fullName", athlete.get("displayName", ""))

        # Position from order field
        position = str(competitor.get("order", ""))

        # To-par score (string like "-5", "+3", "E")
        to_par = competitor.get("score", "")

        # Round scores from linescores
        linescores = competitor.get("linescores", [])
        round_scores = {1: None, 2: None, 3: None, 4: None}
        holes_completed = {1: 0, 2: 0, 3: 0, 4: 0}
        total_strokes = 0
        for ls in linescores:
            period = ls.get("period")
            value = ls.get("value")
            if period and value is not None and 1 <= period <= 4:
                round_scores[period] = int(value)
                total_strokes += int(value)
                holes_completed[period] = len(ls.get("linescores", []))

        if not linescores:
            total_strokes = None

        # Determine golfer status: active, MC, WD, DQ
        # ESPN doesn't explicitly mark cut players. We detect MC by comparing
        # against the cut score (computed in a second pass below).
        golfer_status = "active"
        num_rounds_played = sum(1 for v in round_scores.values() if v is not None and v > 0)

        # Thru: derive from hole-by-hole linescore count
        # Per-golfer hole count is always the primary thru source.
        # The "complete" shortcut only fires post-R4 as a fallback
        # for golfers whose linescore data might be missing.
        thru = ""
        if golfer_status == "MC":
            thru = "MC"
        elif current_round and current_round in holes_completed:
            h = holes_completed[current_round]
            if h >= 18:
                thru = "F"
            elif h > 0:
                thru = str(h)
            # If h == 0, player hasn't started this round yet
        elif tournament_status == "complete" and current_round >= 4:
            # Only blanket "F" when tournament is truly over (post-R4)
            thru = "F"

        # Capture the current round's to-par from ESPN displayValue
        current_round_par = None
        for ls in linescores:
            if ls.get("period") == current_round:
                dv = ls.get("displayValue", "")
                if dv:
                    current_round_par = dv

        golfers.append({
            "espn_id": espn_id,
            "name": name,
            "position": position,
            "total_strokes": total_strokes,
            "to_par": to_par,
            "round_1": round_scores[1],
            "round_2": round_scores[2],
            "round_3": round_scores[3],
            "round_4": round_scores[4],
            "status": golfer_status,
            "thru": thru,
            "current_round": current_round,
            "current_round_par": current_round_par,
            "_num_rounds_played": num_rounds_played,
        })

    # Second pass: detect MC players by 36-hole cut score (top 50 and ties)
    if current_round > 2:
        MASTERS_PAR_36 = 144  # 72 * 2

        # Compute 36-hole to-par for each golfer
        for g in golfers:
            r1 = g.get("round_1") or 0
            r2 = g.get("round_2") or 0
            if r1 > 0 and r2 > 0:
                g["_36h_to_par"] = (r1 + r2) - MASTERS_PAR_36
            else:
                g["_36h_to_par"] = 999

        # Sort by 36-hole score, find the cut score at position 50
        by_36h = sorted(golfers, key=lambda g: g["_36h_to_par"])
        cut_score = None
        if len(by_36h) >= 50:
            cut_score = by_36h[49]["_36h_to_par"]

        if cut_score is not None:
            for g in golfers:
                if g["_36h_to_par"] > cut_score:
                    g["status"] = "MC"
                    g["thru"] = "MC"

            mc_count = sum(1 for g in golfers if g["status"] == "MC")
            logger.info("Cut score (36h): +%d, marked %d golfers as MC", cut_score, mc_count)

        # Clean up
        for g in golfers:
            g.pop("_36h_to_par", None)

    # Clean up internal field
    for g in golfers:
        del g["_num_rounds_played"]

    logger.info("Parsed %d golfers from ESPN data", len(golfers))
    return {"tournament": tournament, "golfers": golfers}


def update_scores(conn=None):
    """Fetch ESPN data and update tournament_state and golfer_scores tables.

    If conn is None, creates and closes its own connection (for scheduler use).
    If conn is provided, uses it without closing (for route use).
    """
    from models.tournament import update_tournament_state, upsert_golfer_score

    own_conn = False
    if conn is None:
        try:
            from app import get_db_connection
            conn = get_db_connection()
            own_conn = True
        except Exception as e:
            logger.error("Failed to get DB connection for score update: %s", e)
            return False

    try:
        data = fetch_leaderboard()
        parsed = parse_leaderboard(data)
        if not parsed:
            logger.error("No parsed data to update scores")
            return False

        t = parsed["tournament"]
        update_tournament_state(
            conn,
            tournament_name=t["name"],
            espn_event_id=t["event_id"],
            status=t["status"],
            current_round=t["current_round"],
            last_poll_at=datetime.now(timezone.utc),
        )

        # Get our golfers' ESPN IDs so we only update ones in our pool
        with conn.cursor() as cur:
            cur.execute("SELECT id, espn_id FROM golfers WHERE espn_id IS NOT NULL")
            our_golfers = {row[1]: row[0] for row in cur.fetchall()}

        updated_count = 0
        for golfer in parsed["golfers"]:
            if golfer["espn_id"] in our_golfers:
                golfer_id = our_golfers[golfer["espn_id"]]
                upsert_golfer_score(
                    conn,
                    golfer_id,
                    round_1=golfer["round_1"],
                    round_2=golfer["round_2"],
                    round_3=golfer["round_3"],
                    round_4=golfer["round_4"],
                    total_strokes=golfer["total_strokes"],
                    to_par=golfer["to_par"],
                    status=golfer["status"],
                    position=golfer["position"],
                    thru=golfer["thru"],
                    current_round=golfer["current_round"],
                    current_round_par=golfer["current_round_par"],
                )
                updated_count += 1

        logger.info("Updated scores for %d/%d pool golfers", updated_count, len(our_golfers))
        return True
    except Exception as e:
        logger.error("Error updating scores: %s", e)
        return False
    finally:
        if own_conn:
            conn.close()


def fetch_scorecard_data():
    """Fetch hole-by-hole scorecard data from ESPN.

    Returns dict keyed by espn_id with per-round hole scores:
    {
        espn_id: {
            "name": str,
            "round_1_holes": [18 ints or None],
            "round_2_holes": [...],
            "round_3_holes": [...],
            "round_4_holes": [...],
        }
    }

    ESPN hole periods: 10-18 = holes 1-9, 1-9 = holes 10-18.
    """
    data = fetch_leaderboard()
    if not data:
        return {}

    events = data.get("events", [])
    if not events:
        return {}

    comp = events[0].get("competitions", [{}])[0]
    competitors = comp.get("competitors", [])
    result = {}

    for competitor in competitors:
        espn_id = str(competitor.get("id", ""))
        athlete = competitor.get("athlete", {})
        name = athlete.get("fullName", "")
        linescores = competitor.get("linescores", [])

        rounds = {}
        has_holes = False
        for ls in linescores:
            round_num = ls.get("period")
            if not round_num or round_num < 1 or round_num > 4:
                continue
            holes_data = ls.get("linescores", [])
            if not holes_data:
                rounds[round_num] = [None] * 18
                continue
            has_holes = True
            # Map ESPN periods to hole numbers
            # periods 10-18 = holes 1-9, periods 1-9 = holes 10-18
            hole_scores = [None] * 18
            for hole in holes_data:
                period = hole.get("period")
                value = hole.get("value")
                if period is None or value is None:
                    continue
                if 10 <= period <= 18:
                    hole_num = period - 9  # 10->1, 11->2, ..., 18->9
                elif 1 <= period <= 9:
                    hole_num = period + 9  # 1->10, 2->11, ..., 9->18
                else:
                    continue
                hole_scores[hole_num - 1] = int(value)
            rounds[round_num] = hole_scores

        result[espn_id] = {
            "name": name,
            "round_1_holes": rounds.get(1, [None] * 18),
            "round_2_holes": rounds.get(2, [None] * 18),
            "round_3_holes": rounds.get(3, [None] * 18),
            "round_4_holes": rounds.get(4, [None] * 18),
            "has_holes": has_holes,
        }

    logger.info("Fetched scorecard data for %d golfers (%d with holes)",
                len(result), sum(1 for v in result.values() if v["has_holes"]))
    return result


def get_mock_scorecard_data():
    """Temporary mock data for visual testing. Delete before go-live."""
    import random
    from app import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT espn_id, name FROM golfers LIMIT 20")
    golfers = cur.fetchall()
    conn.close()

    augusta_par = [4, 5, 4, 3, 4, 3, 4, 5, 4, 4, 4, 3, 5, 4, 5, 3, 4, 4]
    data = {}
    for g in golfers:
        espn_id = g[0] or str(g[1])
        rounds = {"has_holes": True, "name": g[1]}
        for r in range(1, 3):
            holes = []
            for par in augusta_par:
                offset = random.choice([-2, -1, -1, 0, 0, 0, 0, 0, 1, 1, 2])
                holes.append(par + offset)
            rounds[f"round_{r}_holes"] = holes
        rounds["round_3_holes"] = [None] * 18
        rounds["round_4_holes"] = [None] * 18
        data[espn_id] = rounds
    return data


def get_espn_field():
    """Return a list of {espn_id, name} for all golfers in the current ESPN field."""
    data = fetch_leaderboard()
    parsed = parse_leaderboard(data)
    if not parsed:
        return []

    return [
        {"espn_id": g["espn_id"], "name": g["name"]}
        for g in parsed["golfers"]
    ]
