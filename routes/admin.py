from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from app import get_db_connection
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
    conn = get_db_connection()
    golfers = get_all_golfers(conn)
    conn.close()
    return render_template("admin.html", golfers=golfers)


@admin_bp.route("/admin/golfer", methods=["POST"])
def add_golfer():
    if not is_admin():
        return "Forbidden", 403
    name = request.form.get("name", "").strip()
    tier = int(request.form.get("tier", 1))
    espn_id = request.form.get("espn_id", "").strip() or None
    if name:
        conn = get_db_connection()
        create_golfer(conn, name, tier, espn_id)
        conn.close()
        flash("Golfer added.", "success")
    return redirect(url_for("admin.admin"))


@admin_bp.route("/admin/golfer/<int:golfer_id>/delete", methods=["POST"])
def remove_golfer(golfer_id):
    if not is_admin():
        return "Forbidden", 403
    conn = get_db_connection()
    delete_golfer(conn, golfer_id)
    conn.close()
    flash("Golfer deleted.", "success")
    return redirect(url_for("admin.admin"))


@admin_bp.route("/admin/golfer/<int:golfer_id>/edit", methods=["POST"])
def edit_golfer(golfer_id):
    if not is_admin():
        return "Forbidden", 403
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
        flash("Golfer updated.", "success")
    return redirect(url_for("admin.admin"))


@admin_bp.route("/admin/init-db", methods=["POST"])
def init_db():
    if not is_admin():
        return "Forbidden", 403
    conn = get_db_connection()
    with conn.cursor() as cur:
        with open("schema.sql") as f:
            cur.execute(f.read())
    conn.close()
    flash("Database tables initialized.", "success")
    return redirect(url_for("admin.admin"))
