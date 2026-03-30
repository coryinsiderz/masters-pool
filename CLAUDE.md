# Claude Code Rules — Baltz Masters Pool

## Critical Rules

- **Git safety**: Never force-push, never reset --hard, never amend without explicit permission. Create new commits. Use feature branches for non-trivial work.
- **No production DB mutations**: Never write startup code that modifies, deletes, or seeds picks, users, or golfer data. The production database on Neon has real user data. Local dev and Railway hit the SAME database.
- **Feature branches**: For anything beyond a quick fix, work on a branch (`git checkout -b feature/name` or `fix/name`). Merge to main only when the user says to.
- **No AI slop**: No emojis anywhere. No gratuitous gradients, rounded corners, or drop shadows. No "Welcome back!" enthusiasm. The app uses an Augusta National traditional scoreboard aesthetic — clean, serious, classic serif typography.
- **Test before pushing**: Use the dev server and verify changes visually before committing. Flask caches templates — restart the server after template changes.

## Key Gotchas

- **Shared Neon DB**: Local dev and Railway production use the same Postgres database via DATABASE_URL. Every write is real. Never run seed or test data functions.
- **Flask template caching**: After editing any `.html` template, restart the dev server. Changes won't appear otherwise.
- **ESPN API is unofficial**: The golf scoreboard endpoint can change without notice. Always handle missing/malformed fields gracefully. Cache responses.
- **Picks lock at a hard deadline**: 2026-04-09T07:30:00-04:00. All pick submission logic must check this server-side, never trust the client.
- **Scoring is 4-of-6**: Each user picks 6 golfers (one per tier). Only the 4 lowest cumulative stroke totals count. If >2 golfers miss the cut, forced picks get worst-score-among-cutmakers + 1.
- **Background images are swappable**: Each page template defines its own background image via a block. Use CSS background-image on the body/container, not inline styles.

## Starting a Session

1. Check which branch you're on: `git branch --show-current`
2. Check for uncommitted changes: `git status`
3. Start the dev server: `python app.py` (runs on port 5050)
4. The app runs at `http://localhost:5050`

## Key File Locations

| File | Purpose |
|------|---------|
| `app.py` | Main Flask application, DB connection, session setup |
| `config.py` | Environment variable configuration |
| `schema.sql` | Full database schema |
| `models/user.py` | User model + auth helpers |
| `models/golfer.py` | Golfer model (tiers, ESPN ID mapping) |
| `models/pick.py` | Pick model (one per tier per user) |
| `models/tournament.py` | Tournament state + golfer scores |
| `routes/auth.py` | Login, register, logout |
| `routes/picks.py` | Make/edit picks, deadline enforcement |
| `routes/leaderboard.py` | Pool leaderboard |
| `routes/scores.py` | Live tournament scores from ESPN |
| `routes/admin.py` | Tier/golfer management, DB init |
| `routes/team.py` | User's team detail view |
| `services/espn.py` | ESPN API polling + score updates |
| `services/scoring.py` | 4-of-6 scoring engine + tiebreaker |
| `templates/base.html` | Base template — Augusta aesthetic, nav, backgrounds |
| `static/css/style.css` | All custom styles |
| `static/images/` | Background photos (hole12.png, masters_logo.png) |

## Deployment

- **Hosting**: Railway (web service)
- **Database**: Neon Postgres via `DATABASE_URL` env var
- **Python**: 3.12.8 (pinned in runtime.txt)
- **Process**: `gunicorn app:app` (Procfile)
- **Environment variables**: `DATABASE_URL`, `SECRET_KEY`, `ADMIN_USERNAME`

## Tier Names (in order)

1. Tier 1
2. Strong Side
3. Weak Side
4. Maybe
5. Meh
6. Do You Believe in Miracles

## Working Style

- No emojis in code, UI, or commit messages
- Direct communication — no filler phrases
- Show actual code blocks, not summaries
- Feature branches for anything non-trivial
- Test visually before pushing
- Commit messages: imperative mood, explain the "why" not the "what"
