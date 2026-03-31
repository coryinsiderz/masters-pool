from flask import Blueprint, g, redirect, render_template, url_for

from models.tournament import get_all_scores, get_tournament_state

scores_bp = Blueprint("scores", __name__)


@scores_bp.route("/scores")
def scores():
    if not g.current_user:
        return redirect(url_for("auth.login"))
    from app import get_db_connection
    conn = get_db_connection()
    tournament = get_tournament_state(conn)
    all_scores = get_all_scores(conn)
    conn.close()

    # Split into active and cut/withdrawn, sort active by position
    active = []
    cut = []
    for s in all_scores:
        if s.get("status") in ("MC", "WD", "DQ"):
            cut.append(s)
        else:
            active.append(s)

    active.sort(key=lambda s: _parse_position(s.get("position", "")))
    cut.sort(key=lambda s: s.get("name", ""))

    scores_list = active + cut
    return render_template("scores.html", scores=scores_list, tournament=tournament)


def _parse_position(pos):
    """Parse position string to int for sorting. T5 -> 5, etc."""
    if not pos:
        return 9999
    try:
        return int(str(pos).lstrip("T").strip())
    except (ValueError, TypeError):
        return 9999
