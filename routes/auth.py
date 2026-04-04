from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from models.user import check_user_password, create_user, get_user_by_username

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        from app import get_db_connection
        conn = get_db_connection()
        user = get_user_by_username(conn, username)
        conn.close()
        if user and check_user_password(user, password):
            session.permanent = True
            session["user_id"] = user["id"]
            return redirect(url_for("leaderboard.leaderboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        recovery_contact = request.form.get("recovery_contact", "").strip() or None
        if not username or not password:
            flash("Name and password are required.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        else:
            from app import get_db_connection
            conn = get_db_connection()
            existing = get_user_by_username(conn, username)
            if existing:
                conn.close()
                flash("Name already taken.", "error")
            else:
                user = create_user(conn, username, password, recovery_contact)
                conn.close()
                session.permanent = True
                session["user_id"] = user["id"]
                return redirect(url_for("team.team"))
        return render_template("register.html")
    return render_template("register.html")


@auth_bp.route("/api/verify-recovery", methods=["POST"])
def verify_recovery():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    answer = (data.get("answer") or "").strip()
    if not name or not answer:
        return jsonify({"error": "Name and answer are required."}), 400

    from app import get_db_connection
    conn = get_db_connection()
    user = get_user_by_username(conn, name)
    conn.close()

    if not user:
        return jsonify({"error": "No user found with that name."}), 401

    if not user.get("recovery_contact"):
        return jsonify({"error": "No recovery question set for this account."}), 401

    if answer.lower() != user["recovery_contact"].strip().lower():
        return jsonify({"error": "Wrong answer."}), 401

    return jsonify({"success": True})


@auth_bp.route("/api/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    answer = (data.get("answer") or "").strip()
    new_password = data.get("new_password") or ""
    if not name or not answer or not new_password:
        return jsonify({"error": "All fields are required."}), 400

    from app import get_db_connection
    conn = get_db_connection()
    user = get_user_by_username(conn, name)

    if not user or not user.get("recovery_contact"):
        conn.close()
        return jsonify({"error": "That's not right."}), 401

    if answer.lower() != user["recovery_contact"].strip().lower():
        conn.close()
        return jsonify({"error": "That's not right."}), 401

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (generate_password_hash(new_password, method='pbkdf2:sha256'), user["id"]),
        )
    conn.close()

    return jsonify({"success": True})


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
