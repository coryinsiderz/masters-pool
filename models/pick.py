import psycopg2.extras


def set_pick(conn, user_id, tier, golfer_id):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO picks (user_id, tier, golfer_id)
               VALUES (%s, %s, %s)
               ON CONFLICT (user_id, tier)
               DO UPDATE SET golfer_id = EXCLUDED.golfer_id, updated_at = NOW()
               RETURNING *""",
            (user_id, tier, golfer_id),
        )
        return cur.fetchone()


def get_picks_for_user(conn, user_id):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT p.*, g.name AS golfer_name, g.tier AS golfer_tier
               FROM picks p
               JOIN golfers g ON p.golfer_id = g.id
               WHERE p.user_id = %s
               ORDER BY p.tier""",
            (user_id,),
        )
        return cur.fetchall()


def get_all_picks(conn):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT p.*, g.name AS golfer_name, g.tier AS golfer_tier,
                      u.username
               FROM picks p
               JOIN golfers g ON p.golfer_id = g.id
               JOIN users u ON p.user_id = u.id
               ORDER BY u.username, p.tier"""
        )
        return cur.fetchall()


def clear_picks_for_user(conn, user_id):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM picks WHERE user_id = %s", (user_id,))
