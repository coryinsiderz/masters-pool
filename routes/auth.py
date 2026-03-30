from flask import Blueprint, flash, redirect, render_template, request, session, url_for

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


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
