# Claude Code Rules -- Baltz Masters Pool

## Critical Rules

- **Git safety**: Never force-push, never reset --hard, never amend without explicit permission. Create new commits. Use feature branches for non-trivial work.
- **No production DB mutations**: Never write startup code that modifies, deletes, or seeds picks, users, or golfer data. The production database on Neon has real user data. Local dev and Railway hit the SAME database.
- **Feature branches**: For anything beyond a quick fix, work on a branch (`git checkout -b feature/name` or `fix/name`). Merge to main only when the user says to.
- **No AI slop**: No gratuitous gradients, rounded corners, or drop shadows. No "Welcome back!" enthusiasm. The app uses an Augusta National traditional scoreboard aesthetic -- clean, serious, classic serif typography.
- **Test before pushing**: Use the dev server and verify changes visually before committing. Flask caches templates -- restart the server after template changes.

## Key Gotchas

- **Shared Neon DB**: Local dev and Railway production use the same Postgres database via DATABASE_URL. Every write is real. Never run seed or test data functions without explicit permission.
- **Flask template caching**: After editing any `.html` template, restart the dev server. Changes won't appear otherwise.
- **ESPN API is unofficial**: The golf scoreboard endpoint can change without notice. Always handle missing/malformed fields gracefully. Cache responses.
- **Picks lock at a hard deadline**: 2026-04-09T07:30:00-04:00. All pick submission logic must check this server-side, never trust the client.
- **Scoring is 4-of-6**: Each user picks 6 golfers (one per tier). Only the 4 lowest cumulative stroke totals count. If >2 golfers miss the cut, forced picks get worst-score-among-cutmakers + 1.
- **Python 3.9 locally**: System Python is 3.9, Railway runs 3.12.8. Use pbkdf2:sha256 for password hashing (not scrypt). Watch for 3.9 incompatibilities.
- **Circular imports**: Routes import `get_db_connection` lazily inside functions, not at module level, to avoid circular import with app.py.
- **Mobile Safari**: `position: fixed` on background image divs fails on iOS. Mobile uses `body::before`/`::after` pseudo-elements instead.

## Starting a Session

1. Check which branch you're on: `git branch --show-current`
2. Check for uncommitted changes: `git status`
3. Start the dev server: `python3 app.py` (runs on port 8888, binds to 0.0.0.0)
4. The app runs at `http://localhost:8888`

## Key File Locations

| File | Purpose |
|------|---------|
| `app.py` | Flask app, DB connection, scheduler, Jinja filters (display_name, ordinal), blueprint registration |
| `config.py` | Environment variable configuration (DATABASE_URL, SECRET_KEY, PICKS_DEADLINE, ENABLE_POLLING) |
| `schema.sql` | Full database schema (5 tables) |
| `models/user.py` | User CRUD, password hashing (pbkdf2:sha256), case-insensitive lookup |
| `models/golfer.py` | Golfer CRUD, tier management, ESPN ID mapping |
| `models/pick.py` | Pick upsert (one per user per tier), joins with golfer names |
| `models/tournament.py` | Tournament state, golfer score upserts, score queries |
| `routes/auth.py` | Login, register (with recovery contact), logout |
| `routes/picks.py` | Make/edit picks with deadline enforcement |
| `routes/leaderboard.py` | Pool standings with 8-column grid, ownership data, sortable headers |
| `routes/scores.py` | Tournament scores (leaderboard + traditional Augusta board views) |
| `routes/admin.py` | Player management, ESPN import, score updates, polling controls, test data |
| `routes/team.py` | Squad page with vertical cards, counting indicators, round status |
| `routes/exposure.py` | Golfer ownership analysis with tier/player filters |
| `services/espn.py` | ESPN API polling, parsing (including thru from hole counts), scorecard data |
| `services/scoring.py` | 4-of-6 scoring engine, penalty calculation, leaderboard builder |
| `templates/base.html` | Master template: nav, ownership modal, background, fonts, meta tags |
| `static/css/style.css` | All styles: Augusta aesthetic, .tab-btn, .filter-btn, mini-cards, augusta-board |
| `static/js/app.js` | Hamburger menu, custom dropdowns, table sorting, player filters, ownership modal |
| `static/images/hole12.jpg` | Background image (Augusta Hole 12, Golden Bell) |

## Deployment

- **Hosting**: Railway (web service)
- **Database**: Neon Postgres via `DATABASE_URL` env var
- **Python**: 3.12.8 (pinned in runtime.txt)
- **Process**: `gunicorn app:app` (Procfile)
- **Environment variables**: `DATABASE_URL`, `SECRET_KEY`, `ADMIN_USERNAME`, `ENABLE_POLLING`, `ESPN_POLL_INTERVAL`

## Tier Names (in order)

1. Tier 1
2. Strong Side
3. Weak Side
4. Maybe
5. Meh
6. Do You Believe in Miracles

## Design Conventions

- **Fonts**: Cormorant Garamond (titles/brand, weight 500-600), Libre Baskerville (body/tables)
- **Colors**: --augusta-green #006747, --augusta-gold #C8A951, --augusta-cream #FFF8E7, --over-par #C41E3A, --under-par #00a86b
- **To-par display**: Always var(--augusta-gold) everywhere. No red/green color coding on to-par.
- **Uppercase**: Only leaderboard table headers. Everything else mixed case.
- **Display labels**: "Player" not "Golfer" in user-facing text. "Squad" for team page title.
- **Nav order**: My Team, Pool, Tournament, Exposure, Admin (if admin), Logout
- **Toggle buttons**: .tab-btn for text-only tabs (no background), .filter-btn for solid action buttons (green bg)
- **Ownership**: Percentage only in display. Click opens centered modal with golfer name + owner list.
- **Custom dropdowns**: Replace native `<select>` elements for font consistency
- **Favicon**: Hibiscus emoji SVG

## Working Style

- Direct communication -- no filler phrases
- Show actual code blocks, not summaries
- Feature branches for anything non-trivial
- Test visually before pushing
- Commit messages: imperative mood, explain the "why" not the "what"
