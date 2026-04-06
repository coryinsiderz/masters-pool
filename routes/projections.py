from flask import Blueprint, g, jsonify, redirect, render_template, url_for

projections_bp = Blueprint("projections", __name__)


@projections_bp.route("/projections")
def projections():
    if not g.current_user:
        return redirect(url_for("auth.login"))

    from app import format_display_name, get_db_connection
    import psycopg2.extras

    conn = get_db_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT DISTINCT u.id, u.username
               FROM users u JOIN picks p ON u.id = p.user_id
               ORDER BY u.username"""
        )
        rows = cur.fetchall()
    conn.close()

    entrants = [
        {"user_id": r["id"], "name": format_display_name(r["username"])}
        for r in rows
        if r["id"] != g.current_user["id"]
    ]

    return render_template("projections.html", entrants=entrants)


@projections_bp.route("/api/projections/history")
def projections_history():
    if not g.current_user:
        return jsonify({"error": "Login required"}), 401

    from app import format_display_name, get_db_connection
    import psycopg2.extras

    conn = get_db_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT tp.snapshot_time, tp.user_id, tp.projected_total,
                      u.username
               FROM team_projections tp
               JOIN users u ON tp.user_id = u.id
               ORDER BY tp.snapshot_time, u.username"""
        )
        rows = cur.fetchall()
    conn.close()

    # Group by snapshot_time
    snapshots_map = {}
    for r in rows:
        ts = r["snapshot_time"].isoformat() if r["snapshot_time"] else None
        if ts not in snapshots_map:
            snapshots_map[ts] = []
        snapshots_map[ts].append({
            "user_id": r["user_id"],
            "name": format_display_name(r["username"]),
            "projected_total": float(r["projected_total"]) if r["projected_total"] is not None else None,
        })

    snapshots = [
        {"snapshot_time": ts, "teams": teams}
        for ts, teams in snapshots_map.items()
    ]

    return jsonify({
        "snapshots": snapshots,
        "current_user_id": g.current_user["id"],
    })
