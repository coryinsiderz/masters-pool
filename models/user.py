import psycopg2.extras
from werkzeug.security import check_password_hash, generate_password_hash


def create_user(conn, username, password):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING *",
            (username, generate_password_hash(password, method='pbkdf2:sha256')),
        )
        return cur.fetchone()


def get_user_by_username(conn, username):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        return cur.fetchone()


def get_user_by_id(conn, user_id):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        return cur.fetchone()


def check_user_password(user_row, password):
    if not user_row:
        return False
    return check_password_hash(user_row["password_hash"], password)
