from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, url_for

from config import Config
from models.golfer import create_golfer, delete_golfer, get_all_golfers, update_golfer

admin_bp = Blueprint("admin", __name__)


def is_admin():
    return (
        g.current_user
        and g.current_user["username"] == Config.ADMIN_USERNAME
    )


@admin_bp.route("/admin")
def admin():
    if not is_admin():
        return "Forbidden", 403
    from app import get_db_connection
    conn = get_db_connection()
    golfers = get_all_golfers(conn)
    conn.close()
    return render_template("admin.html", golfers=golfers)


@admin_bp.route("/admin/golfer", methods=["POST"])
def add_golfer():
    if not is_admin():
        return "Forbidden", 403
    from app import get_db_connection
    name = request.form.get("name", "").strip()
    tier = int(request.form.get("tier", 1))
    espn_id = request.form.get("espn_id", "").strip() or None
    if name:
        conn = get_db_connection()
        create_golfer(conn, name, tier, espn_id)
        conn.close()
        flash("Player added.", "success")
    return redirect(url_for("admin.admin"))


@admin_bp.route("/admin/golfer/<int:golfer_id>/delete", methods=["POST"])
def remove_golfer(golfer_id):
    if not is_admin():
        return "Forbidden", 403
    from app import get_db_connection
    conn = get_db_connection()
    delete_golfer(conn, golfer_id)
    conn.close()
    flash("Player deleted.", "success")
    return redirect(url_for("admin.admin"))


@admin_bp.route("/admin/golfer/<int:golfer_id>/edit", methods=["POST"])
def edit_golfer(golfer_id):
    if not is_admin():
        return "Forbidden", 403
    from app import get_db_connection
    name = request.form.get("name", "").strip()
    tier = request.form.get("tier")
    espn_id = request.form.get("espn_id", "").strip() or None
    updates = {}
    if name:
        updates["name"] = name
    if tier:
        updates["tier"] = int(tier)
    updates["espn_id"] = espn_id
    if updates:
        conn = get_db_connection()
        update_golfer(conn, golfer_id, **updates)
        conn.close()
        flash("Player updated.", "success")
    return redirect(url_for("admin.admin"))


def _tables_exist():
    from app import get_db_connection
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        )
        count = cur.fetchone()[0]
    conn.close()
    return count > 0


@admin_bp.route("/admin/init-db", methods=["POST"])
def init_db():
    if _tables_exist() and not is_admin():
        return "Forbidden", 403
    from app import get_db_connection
    conn = get_db_connection()
    with conn.cursor() as cur:
        with open("schema.sql") as f:
            cur.execute(f.read())
    conn.close()
    flash("Database tables initialized.", "success")
    return redirect(url_for("admin.admin"))


@admin_bp.route("/admin/test-espn")
def test_espn():
    if not is_admin():
        return "Forbidden", 403
    from services.espn import fetch_leaderboard, parse_leaderboard
    data = fetch_leaderboard()
    parsed = parse_leaderboard(data)
    if not parsed:
        return jsonify({"error": "Failed to fetch or parse ESPN data"}), 500
    return jsonify(parsed)


@admin_bp.route("/admin/espn-field")
def espn_field():
    if not is_admin():
        return "Forbidden", 403
    from services.espn import get_espn_field
    field = get_espn_field()
    return jsonify({"count": len(field), "golfers": field})


@admin_bp.route("/admin/import-field", methods=["POST"])
def import_field():
    if not is_admin():
        return "Forbidden", 403
    from app import get_db_connection
    from services.espn import get_espn_field
    field = get_espn_field()
    if not field:
        flash("Failed to fetch ESPN field.", "error")
        return redirect(url_for("admin.admin"))
    conn = get_db_connection()
    imported = 0
    with conn.cursor() as cur:
        for player in field:
            cur.execute(
                "SELECT 1 FROM golfers WHERE espn_id = %s", (player["espn_id"],)
            )
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO golfers (name, tier, espn_id) VALUES (%s, %s, %s)",
                    (player["name"], 1, player["espn_id"]),
                )
                imported += 1
    conn.close()
    flash(f"{imported} players imported from ESPN.", "success")
    return redirect(url_for("admin.admin"))


@admin_bp.route("/admin/update-scores")
def update_scores_route():
    if not is_admin():
        return "Forbidden", 403
    from app import get_db_connection
    from services.espn import update_scores
    conn = get_db_connection()
    success = update_scores(conn)
    conn.close()
    if success:
        flash("Scores updated from ESPN.", "success")
    else:
        flash("Failed to update scores from ESPN.", "error")
    return redirect(url_for("scores.scores"))
