# Baltz Masters Pool -- Architecture

## Tech stack

- **Backend**: Flask 3.1.0 (Python 3.12.8)
- **Database**: PostgreSQL on Neon, accessed via psycopg2-binary
- **Deployment**: Railway (gunicorn), GitHub for source
- **Frontend**: Server-rendered Jinja2 templates, vanilla JS, no build step
- **Fonts**: Google Fonts (Cormorant Garamond, Libre Baskerville)
- **External API**: ESPN unofficial golf scoreboard endpoint
- **Background jobs**: APScheduler (BackgroundScheduler)

## Directory structure

```
masters-pool/
  app.py                  Flask app, DB connection, scheduler, Jinja filters, blueprint registration
  config.py               Environment variable configuration with defaults
  schema.sql              Full database schema (CREATE TABLE IF NOT EXISTS)
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
    golfer.py             Golfer CRUD, tier management, ESPN ID mapping
    pick.py               Pick upsert (one per user per tier), joins with golfer names
    tournament.py         Tournament state, golfer score upserts, score queries

  routes/
    __init__.py
    auth.py               Login, register (with recovery contact), logout (Blueprint: auth)
    picks.py              Make/edit picks with deadline enforcement, tier validation (Blueprint: picks)
    leaderboard.py        Pool standings with ownership data, sortable 8-column grid (Blueprint: leaderboard)
    scores.py             Tournament scores: leaderboard view + traditional Augusta board (Blueprint: scores)
    admin.py              Player management, ESPN import, polling controls, test data routes (Blueprint: admin)
    team.py               Squad page with vertical cards, counting indicators, round status (Blueprint: team)
    exposure.py           Golfer ownership analysis with tier/player filters (Blueprint: exposure)
    rules.py              Rules page with scoring explanation and dynamic payouts (Blueprint: rules)

  services/
    __init__.py
    espn.py               ESPN API: fetch, parse (with thru from hole counts), scorecard data, field listing
    scoring.py            4-of-6 scoring engine, penalty calculation, leaderboard builder with tiebreakers

  templates/
    base.html             Master template: nav, ownership modal, background, fonts, meta tags
    login.html            Login form (Name + Password)
    register.html         Registration form (Name, Password, Confirm, Recovery)
    picks.html            6-tier pick selection with custom dropdowns
    leaderboard.html      Pool standings: 8-column grid with mini-cards, sortable headers
    scores.html           Tournament scores: leaderboard view + traditional Augusta board with round tabs
    admin.html            Admin panel: polling, ESPN import, test data, player list, tier management
    team.html             Squad: vertical golfer cards with scores, ordinal positions, round status
    exposure.html         Golfer ownership table with tier filters and My Players toggle
    rules.html            Rules: scoring explanation, navigation guide, dynamic payouts

  static/
    css/style.css         All styles: Augusta aesthetic, tab/filter buttons, mini-cards, augusta-board, modal
    js/app.js             Hamburger menu, custom dropdowns, table sorting, player filters, ownership modal
    js/team.js            Squad page JS: Their Team dropdown, Versus side-by-side, card rendering
    images/hole12.jpg     Background image (Augusta Hole 12, Golden Bell, 2880x1620)
```

## Database schema

### users
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-increment user ID |
| username | VARCHAR(50) | UNIQUE NOT NULL | Display name, stored as typed |
| password_hash | VARCHAR(255) | NOT NULL | Werkzeug pbkdf2:sha256 hash |
| is_admin | BOOLEAN | DEFAULT FALSE | Not currently used for admin checks |
| recovery_contact | VARCHAR(100) | nullable | PIN or email for account recovery |
| paid | BOOLEAN | DEFAULT FALSE | Venmo payment status |
| created_at | TIMESTAMP | DEFAULT NOW() | Registration timestamp |

### golfers
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-increment golfer ID |
| espn_id | VARCHAR(20) | nullable | ESPN athlete ID for score matching |
| name | VARCHAR(100) | NOT NULL | Full player name |
| tier | INTEGER | NOT NULL, CHECK 1-6 | Pool tier assignment |
| created_at | TIMESTAMP | DEFAULT NOW() | Creation timestamp |

### picks
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-increment pick ID |
| user_id | INTEGER | FK -> users, NOT NULL | Who made the pick |
| golfer_id | INTEGER | FK -> golfers, NOT NULL | Which golfer was picked |
| tier | INTEGER | CHECK 1-6, NOT NULL | Which tier this pick is for |
| created_at | TIMESTAMP | DEFAULT NOW() | First pick timestamp |
| updated_at | TIMESTAMP | DEFAULT NOW() | Last change timestamp |
| | | UNIQUE(user_id, tier) | One pick per user per tier |

### golfer_scores
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| golfer_id | INTEGER | PK, FK -> golfers | One score row per golfer |
| round_1 | INTEGER | nullable | Round 1 strokes |
| round_2 | INTEGER | nullable | Round 2 strokes |
| round_3 | INTEGER | nullable | Round 3 strokes |
| round_4 | INTEGER | nullable | Round 4 strokes |
| total_strokes | INTEGER | nullable | Sum of all rounds played |
| to_par | VARCHAR(10) | nullable | Display string ("-5", "+3", "E") |
| status | VARCHAR(10) | DEFAULT 'active' | active, MC, WD, or DQ |
| position | VARCHAR(10) | nullable | Tournament position ("1", "T5") |
| thru | VARCHAR(10) | nullable | Holes completed: "F", "12", or "" |
| current_round | INTEGER | DEFAULT 0 | Which round is in progress |
| current_round_par | TEXT | nullable | ESPN round-specific to-par (displayValue from linescore) |
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

## Route map

| Method | Path | Handler | Auth | Description |
|--------|------|---------|------|-------------|
| GET | /health | app.health | None | Returns 200 OK |
| GET | / | leaderboard.leaderboard | Login | Redirects to leaderboard |
| GET | /login | auth.login | None | Login form |
| POST | /login | auth.login | None | Process login |
| GET | /register | auth.register | None | Registration form |
| POST | /register | auth.register | None | Process registration |
| GET | /logout | auth.logout | None | Clear session, redirect to login |
| GET | /picks | picks.picks | Login | Pick selection form |
| POST | /picks | picks.picks | Login | Save picks (deadline enforced) |
| GET | /team | team.team | Login | Squad page with golfer cards |
| GET | /leaderboard | leaderboard.leaderboard | Login | Pool standings (8-column grid) |
| GET | /api/leaderboard | leaderboard.api_leaderboard | Login | JSON standings |
| GET | /scores | scores.scores | Login | Tournament scores (leaderboard or traditional view) |
| GET | /exposure | exposure.exposure | Login | Golfer ownership analysis |
| GET | /admin | admin.admin | Admin | Admin panel |
| POST | /admin/golfer | admin.add_golfer | Admin | Add a player |
| POST | /admin/golfer/ID/delete | admin.remove_golfer | Admin | Delete a player |
| POST | /admin/golfer/ID/edit | admin.edit_golfer | Admin | Edit a player |
| POST | /admin/init-db | admin.init_db | Admin* | Run schema.sql (*no auth if no tables) |
| GET | /admin/test-espn | admin.test_espn | Admin | Raw ESPN parsed data as JSON |
| GET | /admin/espn-field | admin.espn_field | Admin | ESPN field listing as JSON |
| POST | /admin/import-field | admin.import_field | Admin | Import ESPN field into golfers table |
| GET | /admin/update-scores | admin.update_scores_route | Admin | Pull latest scores from ESPN |
| POST | /admin/bulk-tier-update | admin.bulk_tier_update | Admin | Batch tier reassignment |
| POST | /admin/create-test-users | admin.create_test_users | Admin | Create 5 test users with picks |
| POST | /admin/reset-for-testing | admin.reset_for_testing | Admin | Full reset with 24 test users |
| GET | /admin/polling-status | admin.polling_status | Admin | Scheduler state as JSON |
| POST | /admin/set-poll-interval | admin.set_poll_interval | Admin | Change polling interval |
| GET | /api/teams/summary | team.teams_summary | Login+Locked | All users with team totals |
| GET | /api/team/ID | team.team_detail | Login+Locked | Full card data for a user |
| POST | /api/verify-recovery | auth.verify_recovery | None | Verify recovery question answer |
| POST | /api/reset-password | auth.reset_password | None | Reset password after verification |
| POST | /admin/toggle-paid/ID | admin.toggle_paid | Admin | Toggle user paid status |
| GET | /rules | rules.rules | Login | Rules, navigation guide, payouts |

## ESPN API integration

### Endpoint
```
GET https://site.api.espn.com/apis/site/v2/sports/golf/pga/scoreboard
```
No authentication required. Returns the current/most recent PGA Tour event.

### Data flow
1. `fetch_leaderboard()` -- GET request with 10s timeout, User-Agent header, returns raw JSON or None
2. `parse_leaderboard(data)` -- Extracts:
   - Tournament: name, event_id, status (pre/active/complete), current_round
   - Per golfer: espn_id, name, position (from `order`), to_par (from `score`), round scores (from `linescores[].value`), thru (from hole-by-hole linescore count), MC detection (only 2 rounds past round 2)
3. `update_scores(conn=None)` -- Fetches + parses, updates tournament_state and golfer_scores for matched golfers
4. `fetch_scorecard_data()` -- Extracts hole-by-hole scores for the traditional Augusta board view

### ESPN JSON structure
```
events[0].competitions[0].competitors[] -> each golfer
  .id -> ESPN player ID
  .athlete.fullName -> name
  .order -> position
  .score -> to-par string
  .linescores[] -> round scores
    .period -> round number (1-4)
    .value -> total strokes for that round
    .linescores[] -> hole-by-hole scores
      .period -> hole mapping (10-18 = holes 1-9, 1-9 = holes 10-18)
      .value -> strokes on that hole
events[0].competitions[0].status.type.state -> "pre", "in", "post"
events[0].competitions[0].status.period -> current round number
```

- linescores[].displayValue -> round-specific to-par string (e.g., "-1" for current round)

### Thru derivation
ESPN's scoreboard endpoint doesn't provide a `thru` field directly. It's derived from the count of hole-by-hole linescores in the current round: 18 holes = "F" (finished), fewer = in progress (e.g., "10" = through 10 holes), 0 = hasn't started.

- Only sets blanket "F" when tournament is truly over (current_round >= 4 and status complete)
- Per-golfer hole count is always the primary source

### Background polling
APScheduler BackgroundScheduler runs `update_scores()` at configurable intervals. Admin can set to 60s (1 min), 300s (5 min), or 7500s (effectively off). Scheduler only starts in the main Flask process (checks `WERKZEUG_RUN_MAIN` in debug mode).

## Scoring engine

### 4-of-6 scoring
- Each user picks 6 golfers (one per tier)
- Sort all 6 by total strokes ascending
- Best 4 count toward team total
- Worst 2 are benched

### MC/WD/DQ penalty
- Penalty score = MAX(total_strokes) among all active golfers + 1
- Applied to any golfer with status MC, WD, or DQ

### Tiebreaker
- Primary: team_total ascending (lowest wins)
- Tiebreak: best individual finishing position among counting golfers
- Users with no scores sort to bottom with rank "--"

### Rank notation
- Sequential: 1, 2, 3, 4, 5
- Ties: T3, T3 (both get same rank, next rank skips)

## CSS conventions

### Color palette
| Variable | Value | Usage |
|----------|-------|-------|
| --augusta-green | #006747 | Buttons, table headers |
| --augusta-dark | #003d2a | Button hover, fallback background |
| --augusta-gold | #C8A951 | Brand text, labels, to-par numbers, borders |
| --augusta-cream | #FFF8E7 | Body text on dark backgrounds |
| --augusta-white | #FFFFFF | Table header text |
| --over-par | #C41E3A | Over-par (traditional board only) |
| --under-par | #00a86b | Under-par (traditional board only) |
| --panel-bg | rgba(0,30,20,0.75) | Content panels, auth containers |
| --cell-bg | rgba(0,30,20,0.7) | Table cells |
| --grid-line | rgba(200,169,81,0.3) | Table borders |

### Font usage
- **Cormorant Garamond** (weight 500-600): Page titles, section headers, nav brand, form labels, .tab-btn
- **Libre Baskerville** (weight 400/700): Body text, table data, nav links, form inputs, .filter-btn

### Button patterns
- **.tab-btn**: Text-only tabs. Cormorant Garamond, gold text, no background, gold underline on active. Used for: Leaderboard/Traditional toggle, R1-R4 round tabs, tier filter buttons on Exposure.
- **.filter-btn**: Solid action buttons. Green background, cream text, gold background on active. Used for: All Players/My Players toggles, polling interval buttons.
- **.btn-primary**: Green background, cream text. Used for form submit buttons.
- **.btn-danger**: Red background. Used for destructive actions (delete, reset).

### Uppercase rules
- **Only** `.leaderboard-table thead th` uses text-transform: uppercase
- Everything else is mixed case

## Frontend patterns

### Custom dropdowns
All `<select>` elements on picks and admin add-golfer forms are replaced with custom dropdowns:
- `<input type="hidden">` holds the form value
- `.custom-dropdown-trigger` div shows current selection with arrow
- `.custom-dropdown-options` div positioned below, max-height 240px with scroll
- JS handles open/close, click-outside-to-close, value/label updates

### Ownership modal
Single centered modal (in base.html) replaces all per-cell popovers:
- `.owner-modal-overlay` covers screen with semi-transparent background
- `.owner-modal` shows golfer name, ownership percentage, owner list
- Click outside to close. Works on all pages.

### Background image
- Desktop: Hole 12 JPEG via `.bg-image` div with `position: fixed`, dark overlay `.bg-overlay`
- Mobile (768px): `body::before` pseudo-element for background image, `body::after` for overlay. Original divs hidden. Avoids iOS Safari fixed positioning issues.
- `html` has `background-color: var(--augusta-dark)` as fallback

### Jinja filters
- `display_name`: "cory" -> "Cory", "cory baltz" -> "Cory B."
- `ordinal`: 1 -> "1st", "T5" -> "T5th", 13 -> "13th"

### Traditional Augusta board
- Cream background (#f5f0e1), thick horizontal borders, thin vertical
- Numbers show cumulative to-par through each hole (not stroke counts)
- Red text (#C41E3A) = under par, green text (#006747) = over par
- Sticky Score/Player/Owned columns on horizontal scroll
- Round selector tabs (R1-R4) switch which round's holes are displayed
