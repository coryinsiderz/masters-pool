# Baltz Masters Pool -- Project Context

## What is this

Baltz Masters Pool is a private golf pool web app for the 2026 Masters Tournament. Users register, pick one golfer per tier (6 tiers), and compete based on the best 4-of-6 cumulative stroke totals. The app pulls live scores from ESPN's unofficial golf API and calculates standings automatically. The visual design mimics the Augusta National scoreboard aesthetic -- dark backgrounds, gold accents, serif typography, no modern UI flourishes.

## Deployment

- **Live URL**: https://baltzmasters.live (custom domain via Namecheap DNS CNAME to Railway)
- **Railway URL**: https://baltzmasters.up.railway.app
- **Hosting**: Railway (web service, gunicorn)
- **Database**: Neon Postgres (shared between local dev and production via DATABASE_URL)
- **GitHub**: https://github.com/coryinsiderz/masters-pool
- **Python**: 3.12.8 pinned in runtime.txt (local dev runs on system Python 3.9)
- **Dev server**: port 8888, binds to 0.0.0.0

## What's built and working

| Feature | Route | Status |
|---------|-------|--------|
| User registration | POST /register | Working, first char uppercase, recovery contact, modal on login page |
| User login | POST /login | Working, case-insensitive username lookup |
| User logout | GET /logout | Working |
| Session management | before_request hook | 30-day permanent sessions |
| Make picks | GET/POST /picks | Working, 6 custom dropdowns (tiers 4-6 open upward), server-side deadline enforcement |
| Squad page | GET /team | Vertical cards with scores, ordinal positions, counting indicators, ownership hidden pre-lock |
| Pool leaderboard | GET /leaderboard | 8-column grid, mini-cards, sortable headers, ownership modal, gated behind picks lock |
| Leaderboard API | GET /api/leaderboard | JSON standings, gated behind picks lock |
| Tournament leaderboard | GET /scores | Full scoreboard with My Players filter, ownership stripped pre-lock |
| Traditional scorecard | GET /scores?view=board | Augusta-style hole-by-hole cumulative to-par board with round tabs |
| Exposure page | GET /exposure | Golfer ownership analysis, tier filters, My Players toggle, redirects pre-lock |
| Projections page | GET /projections | Chart.js line chart, Just Me/Everyone/Chosen Ones tabs, three-column sortable legend |
| Projections API | GET /api/projections/history | Team projection time-series with actual_total and projected_total |
| Admin panel | GET /admin | Player management, tier assignment, ESPN import, polling controls, user management |
| Admin delete user | POST /admin/user/ID/delete | Deletes user picks, team_projections, and user row (protects id=1) |
| ESPN import | POST /admin/import-field | Bulk import golfers from ESPN field |
| Score update | GET /admin/update-scores | Manual ESPN score pull |
| Background polling | APScheduler | Auto-polls ESPN at configurable intervals (1min/5min/off) |
| Projections polling | APScheduler | Auto-fetches projections every 30min during tournament window, Railway only |
| Projections admin | POST /api/admin/fetch-projections-now | Manual projection fetch + team computation |
| Projections toggle | POST /api/admin/projections-polling | Enable/disable projections polling at runtime |
| DG name matching | POST /api/admin/match-dg-names | One-time setup: match API player names to golfers table |
| Polling controls | GET/POST /admin/polling-status, set-poll-interval | Admin UI with interval buttons |
| Bulk tier update | POST /admin/bulk-tier-update | Batch tier reassignment (supports tier 7 "X") |
| Init database | POST /admin/init-db | Runs schema.sql, accessible without login when no tables exist |
| ESPN test | GET /admin/test-espn | Returns raw parsed ESPN data as JSON |
| ESPN field | GET /admin/espn-field | Lists all ESPN field golfers with IDs |
| Ownership modal | All pages | Centered modal showing golfer name, percentage, owner list |
| View other teams | GET /api/teams/summary, /api/team/<id> | Working, post-lock dropdown + Versus side-by-side |
| Password recovery | POST /api/verify-recovery, /api/reset-password | Working, case-insensitive recovery question |
| Register modal | Login page modal | Working, no close on outside click, "Recovery Question Answer" label |
| Payment tracking | Venmo deeplink + admin toggle | Paid column, "Pay @csbaltz $10 on Venmo" deeplink without amount prefill |
| Rules page | GET /rules | Scoring, navigation guide, projections description, dynamic payouts |
| Health check | GET /health | Returns 200 OK |

## External APIs

### ESPN (scores)
- Unofficial scoreboard endpoint, no auth required
- Provides tournament scores, positions, round data, hole-by-hole linescores
- Polled via APScheduler at configurable intervals

### DataGolf (projections discovery)
- Paid API key in .env as DG_API_KEY
- Discovery completed against pre-tournament, in-play, and field-updates endpoints
- Provides win/top-5/top-10/make-cut probabilities, player rankings, field data
- DG names in "Last, First" format

### Projections API (gbt.up.railway.app)
- Pool app fetches from gbt.up.railway.app/api/projections/live with X-API-Key header
- Returns per-golfer projected_final_to_par and actual_to_par
- Key stored as PROJECTIONS_API_KEY or DG_API_KEY in .env

## Projections infrastructure

- **golfer_projections table**: projected_to_par, actual_to_par, mc_probability, win_probability, snapshot_time
- **team_projections table**: projected_total, actual_total, snapshot_time
- **dg_name column** on golfers table for API name matching
- **Name matching**: fuzzy match by last name, 91/91 matched for Masters field (6 required manual diacritical fixes)
- **Polling**: APScheduler job, 30min interval during tournament window (Thu Apr 9 7:30am - Sun Apr 12 7:00pm ET), controlled by ENABLE_PROJECTIONS_POLLING env var, Railway only

## Masters field

- 91 players loaded in Betfair odds order (IDs 268-358)
- All on tier 1 pending tier assignment
- ESPN IDs pending backfill (ESPN hasn't switched from Valero to Masters yet)
- Tier 7 "X" for excluded/withdrawn players (not shown in pick selection)
- Golfers sorted by ID (insertion order = Betfair odds order), not alphabetically

## Pre-lock gating

- **Exposure page**: redirects to picks page with flash message
- **Pool leaderboard**: shows empty state message instead of standings
- **Leaderboard API**: returns 403
- **Scores page**: shows tournament data but strips ownership (count=0, pct=0, owners=[])
- **Squad cards**: hide ownership percentage span
- **Team API**: already gated (Their Team/Versus hidden pre-lock)

## Key decisions

- **Tier names** (in order): Tier 1, Strong Side, Weak Side, Maybe, Meh, Do You Believe in Miracles, X
- **Scoring**: Best 4 of 6 cumulative strokes. MC/WD/DQ golfers get worst-active-score + 1.
- **Tiebreaker**: Best individual finishing position among counting golfers
- **Picks deadline**: 2026-04-09T07:30:00-04:00 (enforced server-side)
- **Admin**: Determined by ADMIN_USERNAME env var (default "cory"), not the is_admin DB column
- **Fonts**: Cormorant Garamond (titles/brand, weight 500-600), Libre Baskerville (body/tables)
- **Colors**: --augusta-green #006747, --augusta-gold #C8A951, --augusta-cream #FFF8E7, --over-par #C41E3A, --under-par #00a86b
- **To-par display**: All gold (#C8A951) everywhere, no red/green color coding
- **Custom dropdowns**: Replace all native <select> elements for font consistency
- **Username storage**: First char uppercased at registration, case-insensitive lookup via LOWER()
- **Password hashing**: pbkdf2:sha256 (not scrypt) for Python 3.9 compatibility
- **Nav order**: My Team, Pool, Tournament, Exposure, Projections, Rules, Admin (if admin), Logout
- **Page titles (h1)**: Squad, Live Pool Scoring, What's Goin On at Augusta, Ownership, #model, How It's Supposed to Work
- **Picks dropdowns**: Tiers 4-6 open upward (dropup), gold scrollbar, gradient scroll indicator
- **Venmo**: deeplink without amount prefill, display says "$10", web fallback
- **Modals**: Register and forgot-password modals don't close on outside click, only via Cancel button
- **Payouts**: 60/25/15 split rounded to nearest $5, shown TBD pre-lock

## Known issues and quirks

- **Shared database**: Local dev and Railway production use the same Neon Postgres instance. Every write is real.
- **Python 3.9 locally**: System Python is 3.9, Railway runs 3.12.8. Werkzeug scrypt hashing fails on 3.9, so pbkdf2:sha256 is used.
- **Mobile Safari background**: position:fixed on background image divs fails on iOS. Mobile breakpoint uses body::before/::after pseudo-elements instead.
- **Flask template caching**: After editing templates, the dev server must be restarted.
- **ESPN API is unofficial**: The scoreboard endpoint can change without notice. All field access handles missing data gracefully.
- **Circular imports**: Routes import get_db_connection lazily inside functions to avoid circular import with app.py.
- **Sticky column gap**: Pool leaderboard shows a faint white line between Name and Total columns on mobile horizontal scroll.
- **ESPN IDs pending**: Masters golfers inserted manually without ESPN IDs. Need backfill once ESPN loads Masters field.
- **Scheduler double-start**: In debug mode, Flask's reloader spawns two processes. Scheduler checks WERKZEUG_RUN_MAIN to only start once.
- **Mock scorecard data**: When no hole-by-hole data is available from ESPN, falls back to mock random data. Remove before go-live.
