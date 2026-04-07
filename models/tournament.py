import psycopg2.extras


def get_tournament_state(conn):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM tournament_state WHERE id = 1")
        return cur.fetchone()


def update_tournament_state(conn, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k} = %s" for k in kwargs)
    vals = list(kwargs.values())
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"UPDATE tournament_state SET {sets} WHERE id = 1 RETURNING *", vals
        )
        return cur.fetchone()


def upsert_golfer_score(conn, golfer_id, **fields):
    cols = ["golfer_id"] + list(fields.keys())
    placeholders = ", ".join(["%s"] * len(cols))
    updates = ", ".join(f"{k} = EXCLUDED.{k}" for k in fields)
    vals = [golfer_id] + list(fields.values())
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"""INSERT INTO golfer_scores ({', '.join(cols)})
                VALUES ({placeholders})
                ON CONFLICT (golfer_id)
                DO UPDATE SET {updates}, updated_at = NOW()
                RETURNING *""",
            vals,
        )
        return cur.fetchone()


def get_all_scores(conn):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT gs.*, g.name, g.tier, g.espn_id, g.masters_id
               FROM golfer_scores gs
               JOIN golfers g ON gs.golfer_id = g.id
               ORDER BY gs.position"""
        )
        return cur.fetchall()


def get_scores_for_golfers(conn, golfer_ids):
    if not golfer_ids:
        return []
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT gs.*, g.name, g.tier, g.masters_id
               FROM golfer_scores gs
               JOIN golfers g ON gs.golfer_id = g.id
               WHERE gs.golfer_id = ANY(%s)""",
            (golfer_ids,),
        )
        return cur.fetchall()
