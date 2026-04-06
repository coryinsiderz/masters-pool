import psycopg2.extras


def create_golfer(conn, name, tier, espn_id=None):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "INSERT INTO golfers (name, tier, espn_id) VALUES (%s, %s, %s) RETURNING *",
            (name, tier, espn_id),
        )
        return cur.fetchone()


def get_all_golfers(conn):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM golfers ORDER BY tier, id")
        return cur.fetchall()


def get_golfers_by_tier(conn, tier):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM golfers WHERE tier = %s ORDER BY name", (tier,))
        return cur.fetchall()


def get_golfer_by_id(conn, golfer_id):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM golfers WHERE id = %s", (golfer_id,))
        return cur.fetchone()


def update_golfer(conn, golfer_id, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k} = %s" for k in kwargs)
    vals = list(kwargs.values()) + [golfer_id]
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"UPDATE golfers SET {sets} WHERE id = %s RETURNING *", vals)
        return cur.fetchone()


def delete_golfer(conn, golfer_id):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM golfers WHERE id = %s", (golfer_id,))
