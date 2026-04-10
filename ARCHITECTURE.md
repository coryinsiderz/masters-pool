# Baltz Masters Pool -- Architecture

## Tech stack

- **Backend**: Flask 3.1.0 (Python 3.12.8)
- **Database**: PostgreSQL on Neon, accessed via psycopg2-binary
- **Deployment**: Railway (gunicorn), GitHub for source
- **Frontend**: Server-rendered Jinja2 templates, vanilla JS, no build step
- **Fonts**: Google Fonts (Cormorant Garamond, Libre Baskerville)
- **Charts**: Chart.js (CDN) with chartjs-adapter-date-fns for time-axis
- **External APIs**: ESPN unofficial golf scoreboard, DataGolf, projections API (gbt.up.railway.app)
- **Background jobs**: APScheduler (BackgroundScheduler)

## Directory structure

```
masters-pool/
  app.py                  Flask app, DB connection, scheduler (ESPN + projections), Jinja filters, blueprint registration
  config.py               Environment variable configuration with defaults
  schema.sql              Full database schema (7 tables)
  requirements.txt        Python dependencies (pinned versions)
  Procfile                Railway/gunicorn process definition
  runtime.txt             Python version pin (3.12.8)
  .env                    Local environment variables (gitignored)
  .env.example            Template for required env vars
  CLAUDE.md               Claude Code project rules and conventions
  CONTEXT.md              Current project state snapshot
  ARCHITECTURE.md         This file
  BACKLOG.md              Remaining work and feature ideas

  models/
    __init__.py
    user.py               User CRUD, password hashing (pbkdf2:sha256), case-insensitive lookup, recovery_contact
    golfer.py             Golfer CRUD, tier management, ESPN ID mapping, sorted by ID (Betfair odds order)
    pick.py               Pick upsert (one per user per tier), joins with golfer names
    tournament.py         Tournament state, golfer score upserts, score queries

  routes/
    __init__.py
    auth.py               Login, register (first letter each word capitalized, recovery contact), logout (Blueprint: auth)
    picks.py              Make/edit picks with deadline enforcement, tier validation, tiers 4-6 dropup (Blueprint: picks)
    leaderboard.py        Pool standings with ownership data, sortable grid, gated behind picks lock (Blueprint: leaderboard)
    scores.py             Tournament scores: leaderboard + Augusta board, ownership stripped pre-lock (Blueprint: scores)
    admin.py              Player management, ESPN import/backfill, polling controls, user delete, projections admin (Blueprint: admin)
    team.py               Squad page with vertical cards, counting indicators, ownership hidden pre-lock (Blueprint: team)
    exposure.py           Golfer ownership analysis, tier/player filters, redirects pre-lock (Blueprint: exposure)
    projections.py        Projections chart page, /api/projections/history endpoint (Blueprint: projections)
    rules.py              Rules page with scoring, navigation guide, projections, dynamic payouts (Blueprint: rules)

  services/
    __init__.py
    espn.py               ESPN API: fetch, parse (with thru from hole counts), scorecard data, field listing
    scoring.py            4-of-6 scoring engine (sorts by to_par not strokes), team_to_par computation, leaderboard builder with tiebreakers
    projections.py        Projections: fetch (gbt "players"/"to_par" keys), compute_team_projections (ESPN actuals, partial scores), match_dg_names()

  templates/
    base.html             Master template: nav (includes Projections link), ownership modal, background, fonts
    login.html            Login form + register modal + forgot-password modal (no close on outside click)
    register.html         Standalone registration form (legacy, modals preferred)
    picks.html            6-tier pick selection with custom dropdowns (tiers 4-6 dropup)
    leaderboard.html      Pool standings: 8-column grid with mini-cards, sortable headers, right border
    scores.html           Tournament scores: leaderboard view + traditional Augusta board with round tabs
    admin.html            Admin panel: polling, ESPN import, player list (tier 7 "X"), user management with delete
    team.html             Squad: vertical golfer cards, ownership hidden pre-lock, Venmo deeplink
    exposure.html         Golfer ownership table with tier filters and My Players toggle
    projections.html      Chart.js line chart, Just Me/Everyone/Chosen Ones tabs, three-column sortable legend
    rules.html            Rules: scoring, navigation guide, projections description, dynamic payouts

  static/
    css/style.css         All styles: Augusta aesthetic, dropup, gold scrollbar, scroll fade, projections chart/legend
    js/app.js             Hamburger menu, custom dropdowns, table sorting, player filters, ownership modal
    js/team.js            Squad page JS: Their Team dropdown, Versus side-by-side, card rendering
    images/hole12.jpg     Background image (Augusta Hole 12, Golden Bell, 2880x1620)
```

## Database schema

### users
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-increment user ID |
| username | VARCHAR(50) | UNIQUE NOT NULL | Display name, first letter of each word capitalized at registration |
| password_hash | VARCHAR(255) | NOT NULL | Werkzeug pbkdf2:sha256 hash |
| is_admin | BOOLEAN | DEFAULT FALSE | Not currently used for admin checks |
| recovery_contact | VARCHAR(100) | nullable | Answer for account recovery |
| paid | BOOLEAN | DEFAULT FALSE | Venmo payment status |
| created_at | TIMESTAMP | DEFAULT NOW() | Registration timestamp |

### golfers
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-increment golfer ID (insertion order = Betfair odds order) |
| espn_id | VARCHAR(20) | nullable | ESPN athlete ID for score matching (backfilled for all 91) |
| name | VARCHAR(100) | NOT NULL | Full player name |
| dg_name | VARCHAR(200) | nullable | DataGolf API name ("Last, First" format) for projections matching |
| masters_id | VARCHAR | nullable | Masters.com player profile ID (for profile links, not yet wired to frontend) |
| tier | INTEGER | NOT NULL, CHECK 1-7 | Pool tier assignment (7 = "X", excluded from picks) |
| created_at | TIMESTAMP | DEFAULT NOW() | Creation timestamp |

### picks
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-increment pick ID |
| user_id | INTEGER | FK -> users, NOT NULL | Who made the pick |
| golfer_id | INTEGER | FK -> golfers, NOT NULL | Which golfer was picked |
| tier | INTEGER | CHECK 1-7, NOT NULL | Which tier this pick is for |
| created_at | TIMESTAMP | DEFAULT NOW() | First pick timestamp |
| updated_at | TIMESTAMP | DEFAULT NOW() | Last change timestamp |
| | | UNIQUE(user_id, tier) | One pick per user per tier |

### golfer_scores
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| golfer_id | INTEGER | PK, FK -> golfers | One score row per golfer |
| round_1-4 | INTEGER | nullable | Round strokes |
| total_strokes | INTEGER | nullable | Sum of all rounds played |
| to_par | VARCHAR(10) | nullable | Display string ("-5", "+3", "E") |
| status | VARCHAR(10) | DEFAULT 'active' | active, MC, WD, or DQ |
| position | VARCHAR(10) | nullable | Tournament position ("1", "T5") |
| thru | VARCHAR(10) | nullable | Holes completed: "F", "12", or "" |
| current_round | INTEGER | DEFAULT 0 | Which round is in progress |
| current_round_par | TEXT | nullable | ESPN round-specific to-par |
| updated_at | TIMESTAMP | DEFAULT NOW() | Last ESPN update |

### tournament_state
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, DEFAULT 1, CHECK id=1 | Singleton row |
| status | VARCHAR(20) | DEFAULT 'pre' | pre, active, or complete |
| current_round | INTEGER | DEFAULT 0 | Current tournament round (1-4) |
| last_poll_at | TIMESTAMP | nullable | Last ESPN poll timestamp |
| tournament_name | VARCHAR(100) | DEFAULT 'The Masters 2026' | Display name |
| espn_event_id | VARCHAR(20) | nullable | ESPN event identifier |

### golfer_projections
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-increment |
| golfer_id | INTEGER | FK -> golfers | Which golfer |
| projected_to_par | NUMERIC | nullable | Projected 72-hole finish to-par |
| actual_to_par | NUMERIC | nullable | Cumulative actual score to-par |
| mc_probability | NUMERIC | nullable | Probability of missing the cut |
| win_probability | NUMERIC | nullable | Probability of winning |
| snapshot_time | TIMESTAMP | DEFAULT NOW() | When this projection was captured |

### team_projections
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-increment |
| user_id | INTEGER | FK -> users | Which user's team |
| projected_total | NUMERIC | nullable | Best 4-of-6 projected to-par total |
| actual_total | NUMERIC | nullable | Best 4-of-6 actual to-par total (from ESPN scores, partial if <4 started, 0 if none) |
| snapshot_time | TIMESTAMP | DEFAULT NOW() | When this was computed |

## Route map

| Method | Path | Handler | Auth | Description |
|--------|------|---------|------|-------------|
| GET | /health | app.health | None | Returns 200 OK |
| GET | / | leaderboard.leaderboard | Login | Redirects to leaderboard |
| GET/POST | /login | auth.login | None | Login form + process |
| GET/POST | /register | auth.register | None | Registration (first letter each word capitalized) |
| GET | /logout | auth.logout | None | Clear session |
| GET/POST | /picks | picks.picks | Login | Pick selection (deadline enforced) |
| GET | /team | team.team | Login | Squad page |
| GET | /leaderboard | leaderboard.leaderboard | Login+Lock | Pool standings (empty pre-lock) |
| GET | /api/leaderboard | leaderboard.api_leaderboard | Login+Lock | JSON standings (403 pre-lock) |
| GET | /scores | scores.scores | Login | Tournament scores (ownership stripped pre-lock) |
| GET | /exposure | exposure.exposure | Login+Lock | Ownership (redirects pre-lock) |
| GET | /projections | projections.projections | Login | Projections chart page |
| GET | /api/projections/history | projections.projections_history | Login | Projection time-series JSON |
| GET | /rules | rules.rules | Login | Rules page |
| GET | /admin | admin.admin | Admin | Admin panel |
| POST | /admin/golfer | admin.add_golfer | Admin | Add a player |
| POST | /admin/golfer/ID/delete | admin.remove_golfer | Admin | Delete a player |
| POST | /admin/golfer/ID/edit | admin.edit_golfer | Admin | Edit a player |
| POST | /admin/user/ID/delete | admin.delete_user | Admin | Delete a user (protects id=1) |
| POST | /admin/init-db | admin.init_db | Admin* | Run schema.sql |
| GET | /admin/test-espn | admin.test_espn | Admin | Raw ESPN data |
| GET | /admin/espn-field | admin.espn_field | Admin | ESPN field listing |
| POST | /admin/import-field | admin.import_field | Admin | Import ESPN field |
| GET | /admin/update-scores | admin.update_scores_route | Admin | Pull ESPN scores |
| GET | /admin/backfill-espn-ids | admin.backfill_espn_ids | Admin | Match ESPN names to golfers, set espn_id |
| POST | /admin/bulk-tier-update | admin.bulk_tier_update | Admin | Batch tier reassignment |
| GET | /admin/polling-status | admin.polling_status | Admin | Scheduler state JSON |
| POST | /admin/set-poll-interval | admin.set_poll_interval | Admin | Change ESPN polling interval |
| POST | /admin/toggle-paid/ID | admin.toggle_paid | Admin | Toggle user paid status |
| POST | /api/admin/fetch-projections | admin.api_fetch_projections | Admin | Fetch pre-tournament projections |
| POST | /api/admin/fetch-projections-now | admin.api_fetch_projections_now | Admin | Fetch live projections + compute teams |
| POST | /api/admin/match-dg-names | admin.api_match_dg_names | Admin | Match DG names to golfers |
| POST | /api/admin/projections-polling | admin.api_projections_polling_toggle | Admin | Enable/disable projections polling |
| GET | /api/admin/projections-polling-status | admin.api_projections_polling_status | Admin | Projections polling state |
| GET | /api/teams/summary | team.teams_summary | Login+Lock | All users with team totals |
| GET | /api/team/ID | team.team_detail | Login+Lock | Full card data for a user |
| POST | /api/verify-recovery | auth.verify_recovery | None | Verify recovery answer |
| POST | /api/reset-password | auth.reset_password | None | Reset password |

## Config variables

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | required | Neon Postgres connection string |
| SECRET_KEY | required | Flask session secret |
| ADMIN_USERNAME | "cory" | Username that gets admin access |
| ENABLE_POLLING | "1" | Enable ESPN background polling |
| ESPN_POLL_INTERVAL | 300 | ESPN poll interval in seconds |
| ENABLE_PROJECTIONS_POLLING | "0" | Enable projections background polling (Railway only) |
| PROJECTIONS_POLL_INTERVAL | 300 | Projections poll interval in seconds (5 min) |
| PROJECTIONS_API_KEY | (falls back to DG_API_KEY) | API key for projections endpoint |
| DG_API_KEY | in .env | DataGolf API key |

## Projections chart (templates/projections.html)

- **Chart.js** loaded via CDN with chartjs-adapter-date-fns for time-based x-axis
- **X-axis**: fixed tournament window Thu Apr 9 7:40am to Sun Apr 12 7:00pm ET, display: false (no labels/grid)
- **Y-axis**: inverted (reverse: true), to-par format, no grid lines, tick labels visible
- **Two datasets per user**: "actual" segment (solid line through snapshot actuals) + "projected" segment (thinner/more transparent line from last actual to projected finish at TOURNEY_END)
- **Live line**: vertical solid line at Date.now(), faint gold rgba(200,169,81,0.2), "Live" label inside chart area
- **Tabs**: Just Me (default) / Everyone / Chosen Ones (dropdown-in-tab-bar matching team.html Their Team pattern)
- **Legend**: three-column (Name / Current / Proj), sortable by any column, Chosen Ones grouped at top with gold divider
- **Entrant list**: server-rendered from route context (not from projection data), works even with zero snapshots
