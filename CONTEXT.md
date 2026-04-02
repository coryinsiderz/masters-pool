# Baltz Masters Pool -- Project Context

## What is this

Baltz Masters Pool is a private golf pool web app for the 2026 Masters Tournament. Users register, pick one golfer per tier (6 tiers), and compete based on the best 4-of-6 cumulative stroke totals. The app pulls live scores from ESPN's unofficial golf API and calculates standings automatically. The visual design mimics the Augusta National scoreboard aesthetic -- dark backgrounds, gold accents, serif typography, no modern UI flourishes.

## Deployment

- **Live URL**: https://baltzmasters.up.railway.app
- **Hosting**: Railway (web service, gunicorn)
- **Database**: Neon Postgres (shared between local dev and production via DATABASE_URL)
- **GitHub**: https://github.com/coryinsiderz/masters-pool
- **Python**: 3.12.8 pinned in runtime.txt (local dev runs on system Python 3.9)
- **Dev server**: port 8888, binds to 0.0.0.0

## What's built and working

| Feature | Route | Status |
|---------|-------|--------|
| User registration | POST /register | Working, stores recovery contact |
| User login | POST /login | Working, case-insensitive username lookup |
| User logout | GET /logout | Working |
| Session management | before_request hook | 30-day permanent sessions |
| Make picks | GET/POST /picks | Working, 6 custom dropdowns, server-side deadline enforcement |
| Squad page | GET /team | Vertical cards with scores, ordinal positions, counting indicators, round status |
| Pool leaderboard | GET /leaderboard | 8-column grid, mini-cards with pipe format, sortable headers, ownership modal |
| Leaderboard API | GET /api/leaderboard | JSON endpoint for standings |
| Tournament leaderboard | GET /scores | Full scoreboard with My Players filter, thru display |
| Traditional scorecard | GET /scores?view=board | Augusta-style hole-by-hole cumulative to-par board with round tabs |
| Exposure page | GET /exposure | Golfer ownership analysis, tier filters, My Players toggle |
| Admin panel | GET /admin | Player management, tier assignment, ESPN import, polling controls |
| ESPN import | POST /admin/import-field | Bulk import golfers from ESPN field |
| Score update | GET /admin/update-scores | Manual ESPN score pull |
| Background polling | APScheduler | Auto-polls ESPN at configurable intervals (1min/5min/off) |
| Polling controls | GET/POST /admin/polling-status, set-poll-interval | Admin UI with interval buttons |
| Bulk tier update | POST /admin/bulk-tier-update | Batch tier reassignment |
| Init database | POST /admin/init-db | Runs schema.sql, accessible without login when no tables exist |
| Test data setup | POST /admin/reset-for-testing | Full reset with 24 test users and random picks |
| ESPN test | GET /admin/test-espn | Returns raw parsed ESPN data as JSON |
| ESPN field | GET /admin/espn-field | Lists all ESPN field golfers with IDs |
| Ownership modal | All pages | Centered modal showing golfer name, percentage, owner list |
| Health check | GET /health | Returns 200 OK |

## What's not built yet

See BACKLOG.md for the full list.

## Key decisions

- **Tier names** (in order): Tier 1, Strong Side, Weak Side, Maybe, Meh, Do You Believe in Miracles
- **Scoring**: Best 4 of 6 cumulative strokes. MC/WD/DQ golfers get worst-active-score + 1.
- **Tiebreaker**: Best individual finishing position among counting golfers
- **Picks deadline**: 2026-04-09T07:30:00-04:00 (enforced server-side)
- **Admin**: Determined by ADMIN_USERNAME env var (default "cory"), not the is_admin DB column
- **Fonts**: Cormorant Garamond (titles/brand, weight 500-600), Libre Baskerville (body/tables)
- **Colors**: --augusta-green #006747, --augusta-gold #C8A951, --augusta-cream #FFF8E7, --over-par #C41E3A, --under-par #00a86b
- **No uppercase**: text-transform removed site-wide except leaderboard table headers
- **To-par display**: All gold (#C8A951) everywhere, no red/green color coding
- **Traditional scorecard**: Cream background, cumulative to-par per hole, red text = under par, green text = over par (matching physical Augusta board)
- **Custom dropdowns**: Replace all native <select> elements for font consistency
- **Username storage**: Preserved as typed (case-insensitive lookup via LOWER())
- **Password hashing**: pbkdf2:sha256 (not scrypt) for Python 3.9 compatibility
- **Display labels**: "Player" not "Golfer" in all user-facing text. "Squad" for team page title.
- **Nav order**: My Team, Pool, Tournament, Exposure, Admin (if admin), Logout
- **Page titles (browser tab)**: My Team, Pool, Tournament, Exposure, Admin, Login, Register
- **Favicon**: Hibiscus emoji SVG (closest to azalea)
- **Toggle buttons**: .tab-btn for text-only tabs, .filter-btn for solid action buttons
- **Ownership display**: Percentage only, click opens centered modal
- **Thru parsing**: Derived from hole-by-hole linescore count in ESPN data (18 holes = F, fewer = in progress)
- **Background polling**: APScheduler with admin-configurable intervals (60s, 300s, 7500s)

## Known issues and quirks

- **Shared database**: Local dev and Railway production use the same Neon Postgres instance. Every write is real.
- **Python 3.9 locally**: System Python is 3.9, Railway runs 3.12.8. Werkzeug scrypt hashing fails on 3.9, so pbkdf2:sha256 is used.
- **Mobile Safari background**: position:fixed on background image divs fails on iOS. Mobile breakpoint uses body::before/::after pseudo-elements instead.
- **Flask template caching**: After editing templates, the dev server must be restarted.
- **ESPN API is unofficial**: The scoreboard endpoint can change without notice. All field access handles missing data gracefully.
- **Admin check uses username**: The admin gate compares current_user.username to ADMIN_USERNAME, not the is_admin boolean in the database.
- **Dev server port**: Runs on 8888, binds to 0.0.0.0 for network access.
- **Circular imports**: Routes import get_db_connection lazily inside functions to avoid circular import with app.py.
- **Mobile traditional scorecard**: Sticky columns (Score, Player, Owned) may overlap on very narrow viewports. Partially fixed with explicit widths/z-index.
- **Mock scorecard data**: When no hole-by-hole data is available from ESPN, falls back to mock random data for visual testing. Remove before go-live.
- **Test routes**: /admin/create-test-users and /admin/reset-for-testing are temporary. Delete before Masters go-live.
- **Scheduler double-start**: In debug mode, Flask's reloader spawns two processes. Scheduler checks WERKZEUG_RUN_MAIN to only start once.
