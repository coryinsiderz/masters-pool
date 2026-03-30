"""ESPN API polling service.

Polls ESPN's unofficial golf scoreboard endpoint to fetch live tournament
scores. The endpoint can change without notice, so all field access must
handle missing or malformed data gracefully. Responses should be cached
to avoid excessive polling.
"""


def poll_espn_scores():
    pass
