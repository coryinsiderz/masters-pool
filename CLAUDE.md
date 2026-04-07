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
- **Projections fetch is Railway-only**: Never run projections polling in local dev. Controlled by ENABLE_PROJECTIONS_POLLING env var (default "0"). The projections API is at gbt.up.railway.app, not DataGolf directly.
- **ESPN IDs pending backfill**: Masters golfers were inserted manually without ESPN IDs. Do NOT delete/recreate golfer rows. Use /admin/backfill-espn-ids when ESPN loads the Masters field.
- **Tier 7 = "X"**: Excluded from pick selection (picks page only shows tiers 1-6). Used for withdrawn or non-competing players.
- **Golfers sorted by ID**: Insertion order = Betfair odds order. get_all_golfers() uses ORDER BY tier, id (not name).
- **Pre-lock gating**: Check _is_picks_locked() or Config.PICKS_DEADLINE. `picks_locked` is available in all templates via the context processor in app.py. Exposure redirects, leaderboard shows empty state, scores strip ownership, squad hides ownership %.

## Starting a Session

1. Check which branch you're on: `git branch --show-current`
2. Check for uncommitted changes: `git status`
3. Start the dev server: `python3 app.py` (runs on port 8888, binds to 0.0.0.0)
4. The app runs at `http://localhost:8888`

## Key File Locations

| File | Purpose |
|------|---------|
| `app.py` | Flask app, DB connection, scheduler (ESPN + projections), Jinja filters (display_name, ordinal), blueprint registration |
| `config.py` | Environment variable configuration (DATABASE_URL, SECRET_KEY, PICKS_DEADLINE, ENABLE_POLLING, ENABLE_PROJECTIONS_POLLING, PROJECTIONS_POLL_INTERVAL) |
| `schema.sql` | Full database schema (7 tables) |
| `models/user.py` | User CRUD, password hashing (pbkdf2:sha256), case-insensitive lookup |
| `models/golfer.py` | Golfer CRUD, tier management, ESPN ID mapping, sorted by ID |
| `models/pick.py` | Pick upsert (one per user per tier), joins with golfer names |
| `models/tournament.py` | Tournament state, golfer score upserts, score queries |
| `routes/auth.py` | Login, register (first char uppercase, recovery contact), logout |
| `routes/picks.py` | Make/edit picks with deadline enforcement, tiers 4-6 dropup |
| `routes/leaderboard.py` | Pool standings, gated behind picks lock |
| `routes/scores.py` | Tournament scores, ownership stripped pre-lock |
| `routes/admin.py` | Player management, ESPN import, polling controls, user delete, projections admin |
| `routes/team.py` | Squad page with vertical cards, ownership hidden pre-lock |
| `routes/exposure.py` | Golfer ownership analysis, redirects pre-lock |
| `routes/projections.py` | Projections chart page, /api/projections/history endpoint |
| `routes/rules.py` | Rules page with scoring, navigation, projections, dynamic payouts |
| `services/espn.py` | ESPN API polling, parsing (including thru from hole counts), scorecard data |
| `services/scoring.py` | 4-of-6 scoring engine, penalty calculation, leaderboard builder |
| `services/projections.py` | Projections: fetch, compute team totals, DG name matching |
| `templates/base.html` | Master template: nav (includes Projections), ownership modal, background, fonts |
| `templates/projections.html` | Chart.js line chart, tabs, three-column sortable legend |
| `static/css/style.css` | All styles: Augusta aesthetic, dropup, gold scrollbar, projections chart/legend |
| `static/js/app.js` | Hamburger menu, custom dropdowns, table sorting, player filters, ownership modal |
| `static/js/team.js` | Squad page JS: Their Team dropdown, Versus comparison, card rendering |
| `static/images/hole12.jpg` | Background image (Augusta Hole 12, Golden Bell) |

## Deployment

- **Hosting**: Railway (web service)
- **Custom domain**: baltzmasters.live (Namecheap DNS CNAME to Railway)
- **Database**: Neon Postgres via `DATABASE_URL` env var
- **Python**: 3.12.8 (pinned in runtime.txt)
- **Process**: `gunicorn app:app` (Procfile)
- **Environment variables**: `DATABASE_URL`, `SECRET_KEY`, `ADMIN_USERNAME`, `ENABLE_POLLING`, `ESPN_POLL_INTERVAL`, `ENABLE_PROJECTIONS_POLLING`, `PROJECTIONS_POLL_INTERVAL`, `PROJECTIONS_API_KEY`

## Tier Names (in order)

1. Tier 1
2. Strong Side
3. Weak Side
4. Maybe
5. Meh
6. Do You Believe in Miracles
7. X (not in field)

## Design Conventions

- **Fonts**: Cormorant Garamond (titles/brand, weight 500-600), Libre Baskerville (body/tables)
- **Colors**: --augusta-green #006747, --augusta-gold #C8A951, --augusta-cream #FFF8E7, --over-par #C41E3A, --under-par #00a86b
- **To-par display**: Always var(--augusta-gold) everywhere. No red/green color coding on to-par.
- **Uppercase**: Only leaderboard table headers. Everything else mixed case.
- **Display labels**: "Player" not "Golfer" in user-facing text. "Squad" for team page title.
- **Nav order**: My Team, Pool, Tournament, Exposure, Projections, Rules, Admin (if admin), Logout
- **Page titles (h1)**: Squad, Live Pool Scoring, What's Goin On at Augusta, Ownership, #model, How It's Supposed to Work
- **Toggle buttons**: .tab-btn for text-only tabs (no background), .filter-btn for solid action buttons (green bg)
- **Ownership**: Percentage only in display. Click opens centered modal. Hidden pre-lock on all pages.
- **Custom dropdowns**: Replace native `<select>` elements for font consistency
- **Picks dropdowns**: Tiers 4-6 open upward (dropup class), gold scrollbar, gradient scroll fade indicator
- **Favicon**: Hibiscus emoji SVG
- **Login modals**: Register and forgot-password are modals on the login page, don't close on outside click
- **Payment display**: .payment-status element. Gold text, no underline for Pay, gold underline for Paid.

## Working Style

- Direct communication -- no filler phrases
- Show actual code blocks, not summaries
- Feature branches for anything non-trivial
- Test visually before pushing
- Commit messages: imperative mood, explain the "why" not the "what"
