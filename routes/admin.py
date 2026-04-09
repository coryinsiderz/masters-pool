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
    import psycopg2.extras
    conn = get_db_connection()
    golfers = get_all_golfers(conn)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT id, username, paid FROM users ORDER BY username")
        users = cur.fetchall()
    conn.close()
    return render_template("admin.html", golfers=golfers, users=users)


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


@admin_bp.route("/admin/bulk-tier-update", methods=["POST"])
def bulk_tier_update():
    if not is_admin():
        return "Forbidden", 403
    from app import get_db_connection
    conn = get_db_connection()
    updated = 0
    for key, value in request.form.items():
        if key.startswith("tier_"):
            golfer_id = int(key.split("_", 1)[1])
            new_tier = int(value)
            update_golfer(conn, golfer_id, tier=new_tier)
            updated += 1
    conn.close()
    flash(f"{updated} tier assignments saved.", "success")
    return redirect(url_for("admin.admin"))


@admin_bp.route("/admin/polling-status")
def polling_status():
    if not is_admin():
        return "Forbidden", 403
    from app import scheduler, get_db_connection
    from models.tournament import get_tournament_state

    interval = 0
    running = False
    if scheduler and scheduler.running:
        running = True
        job = scheduler.get_job("espn_poll")
        if job and job.trigger:
            interval = int(job.trigger.interval.total_seconds())

    conn = get_db_connection()
    state = get_tournament_state(conn)
    conn.close()
    last_poll = state["last_poll_at"].isoformat() if state and state.get("last_poll_at") else None

    return jsonify({
        "running": running,
        "interval": interval,
        "last_poll_at": last_poll,
    })


@admin_bp.route("/admin/set-poll-interval", methods=["POST"])
def set_poll_interval():
    if not is_admin():
        return "Forbidden", 403
    from app import start_scheduler

    interval = int(request.form.get("interval", 300))
    if interval not in (60, 300, 7500):
        interval = 300
    start_scheduler(interval)
    label = {60: "1 min", 300: "5 min", 7500: "Off"}.get(interval, f"{interval}s")
    flash(f"Polling interval set to {label}.", "success")
    return redirect(url_for("admin.admin"))


@admin_bp.route("/admin/user/<int:user_id>/delete", methods=["POST"])
def delete_user(user_id):
    if not is_admin():
        return "Forbidden", 403
    if user_id == 1:
        flash("Cannot delete the admin user.", "error")
        return redirect(url_for("admin.admin"))
    from app import get_db_connection
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM team_projections WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM picks WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.close()
    flash("User deleted.", "success")
    return redirect(url_for("admin.admin"))


@admin_bp.route("/admin/toggle-paid/<int:user_id>", methods=["POST"])
def toggle_paid(user_id):
    if not is_admin():
        return "Forbidden", 403
    from app import get_db_connection
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET paid = NOT COALESCE(paid, FALSE) WHERE id = %s RETURNING paid",
            (user_id,),
        )
        row = cur.fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"paid": row[0]})


@admin_bp.route("/api/admin/fetch-projections", methods=["POST"])
def api_fetch_projections():
    if not is_admin():
        return jsonify({"error": "Forbidden"}), 403
    from app import get_db_connection
    from services.projections import fetch_projections
    conn = get_db_connection()
    result = fetch_projections(conn)
    conn.close()
    return jsonify(result)


@admin_bp.route("/api/admin/match-dg-names", methods=["POST"])
def api_match_dg_names():
    if not is_admin():
        return jsonify({"error": "Forbidden"}), 403
    from app import get_db_connection
    from services.projections import match_dg_names
    conn = get_db_connection()
    result = match_dg_names(conn)
    conn.close()
    return jsonify(result)


@admin_bp.route("/api/admin/fetch-projections-now", methods=["POST"])
def api_fetch_projections_now():
    """Manually trigger a live projections fetch + team computation."""
    if not is_admin():
        return jsonify({"error": "Forbidden"}), 403
    from app import get_db_connection
    from services.projections import fetch_live_projections, compute_team_projections
    conn = get_db_connection()
    fetch_result = fetch_live_projections(conn)
    teams = {}
    if fetch_result.get("matched", 0) > 0:
        teams = compute_team_projections(conn)
    conn.close()
    return jsonify({
        "fetch": fetch_result,
        "teams_computed": len(teams),
    })


@admin_bp.route("/api/admin/projections-polling", methods=["POST"])
def api_projections_polling_toggle():
    """Enable or disable projections polling. Body: {"enabled": true/false}"""
    if not is_admin():
        return jsonify({"error": "Forbidden"}), 403
    from app import scheduler
    import json
    data = request.get_json(force=True)
    enabled = data.get("enabled", False)

    if scheduler and scheduler.running:
        existing = scheduler.get_job("projections_poll")
        if enabled and not existing:
            from app import _projections_poll_job
            from config import Config
            interval = Config.PROJECTIONS_POLL_INTERVAL
            scheduler.add_job(
                _projections_poll_job,
                "interval",
                seconds=interval,
                id="projections_poll",
                replace_existing=True,
            )
            return jsonify({"status": "enabled", "interval": interval})
        elif not enabled and existing:
            scheduler.remove_job("projections_poll")
            return jsonify({"status": "disabled"})
        elif enabled and existing:
            return jsonify({"status": "already_enabled"})
        else:
            return jsonify({"status": "already_disabled"})
    return jsonify({"error": "Scheduler not running"}), 500


@admin_bp.route("/api/admin/projections-polling-status")
def api_projections_polling_status():
    if not is_admin():
        return jsonify({"error": "Forbidden"}), 403
    from app import scheduler
    running = False
    interval = 0
    if scheduler and scheduler.running:
        job = scheduler.get_job("projections_poll")
        if job:
            running = True
            interval = int(job.trigger.interval.total_seconds())
    return jsonify({"running": running, "interval": interval})


@admin_bp.route("/admin/backfill-espn-ids")
def backfill_espn_ids():
    if not is_admin():
        return "Forbidden", 403
    import unicodedata

    from app import get_db_connection
    from services.espn import fetch_leaderboard, parse_leaderboard

    parsed = parse_leaderboard(fetch_leaderboard())
    if not parsed or not parsed["golfers"]:
        return jsonify({"error": "Could not fetch ESPN field"}), 500

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM golfers")
        db_golfers = cur.fetchall()

    def normalize(name):
        # Strip diacritics and lowercase for fuzzy matching
        nfkd = unicodedata.normalize("NFKD", name)
        return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

    # Build lookup: normalized name -> (golfer_id, original_name)
    db_lookup = {}
    for gid, gname in db_golfers:
        db_lookup[normalize(gname)] = (gid, gname)

    matched = []
    unmatched_espn = []
    for espn_golfer in parsed["golfers"]:
        espn_name = espn_golfer["name"]
        espn_id = espn_golfer["espn_id"]
        key = normalize(espn_name)
        if key in db_lookup:
            gid, db_name = db_lookup[key]
            matched.append({"db_id": gid, "db_name": db_name, "espn_name": espn_name, "espn_id": espn_id})
        else:
            unmatched_espn.append({"espn_name": espn_name, "espn_id": espn_id})

    # Apply updates
    with conn.cursor() as cur:
        for m in matched:
            cur.execute("UPDATE golfers SET espn_id = %s WHERE id = %s", (m["espn_id"], m["db_id"]))
    conn.close()

    return jsonify({
        "matched": len(matched),
        "unmatched": len(unmatched_espn),
        "unmatched_names": [u["espn_name"] for u in unmatched_espn],
    })


