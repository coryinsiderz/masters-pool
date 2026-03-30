from flask import Blueprint, g, redirect, render_template, url_for

scores_bp = Blueprint("scores", __name__)


@scores_bp.route("/scores")
def scores():
    if not g.current_user:
        return redirect(url_for("auth.login"))
    return render_template("scores.html")
