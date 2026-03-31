# Baltz Masters Pool -- Architecture

## Tech stack

- **Backend**: Flask 3.1.0 (Python 3.12.8)
- **Database**: PostgreSQL on Neon, accessed via psycopg2-binary
- **Deployment**: Railway (gunicorn), GitHub for source
- **Frontend**: Server-rendered Jinja2 templates, vanilla JS, no build step
- **Fonts**: Google Fonts (Cormorant Garamond, Libre Baskerville)
- **External API**: ESPN unofficial golf scoreboard endpoint

## Directory structure

```
masters-pool/
  app.py                  Flask app factory, DB connection, session setup, blueprint registration
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

  models/
    __init__.py
    user.py               User CRUD, password hashing (pbkdf2:sha256), case-insensitive lookup
    golfer.py             Golfer CRUD, tier management, ESPN ID mapping
    pick.py               Pick upsert (one per user per tier), joins with golfer names
    tournament.py         Tournament state, golfer score upserts, score queries

  routes/
    __init__.py
    auth.py               Login, register, logout (Blueprint: auth)
    picks.py              Make/edit picks with deadline enforcement (Blueprint: picks)
    leaderboard.py        Pool standings and JSON API (Blueprint: leaderboard)
    scores.py             Live tournament scores from DB (Blueprint: scores)
    admin.py              Player management, ESPN import, score updates, DB init (Blueprint: admin)
    team.py               User's squad view (Blueprint: team)

  services/
    __init__.py
    espn.py               ESPN API polling, parsing, score updates, field listing
    scoring.py            4-of-6 scoring engine, penalty calculation, leaderboard builder

  templates/
    base.html             Master template: nav, background, fonts, flash messages
    login.html            Login form
    register.html         Registration form with recovery contact
    picks.html            6-tier pick selection with custom dropdowns
    leaderboard.html      Pool standings table
    scores.html           Tournament scoreboard
    admin.html            Admin panel: import, add player, tier management, DB init
    team.html             User's squad display

  static/
    css/style.css         All custom styles (Augusta National aesthetic)
    js/app.js             Hamburger menu toggle, custom dropdown behavior
    images/hole12.jpg     Background image (Augusta Hole 12, Golden Bell)
```

## Database schema

### users
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-increment user ID |
| username | VARCHAR(50) | UNIQUE NOT NULL | Display name, stored as typed |
| password_hash | VARCHAR(255) | NOT NULL | Werkzeug pbkdf2:sha256 hash |
| is_admin | BOOLEAN | DEFAULT FALSE | Not currently used for admin checks |
| recovery_contact | VARCHAR(100) | nullable | Email or PIN for account recovery |
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
| thru | VARCHAR(10) | nullable | Holes completed in current round |
| current_round | INTEGER | DEFAULT 0 | Which round is in progress |
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
| GET | /team | team.team | Login | User's squad display |
| GET | /leaderboard | leaderboard.leaderboard | Login | Pool standings |
| GET | /api/leaderboard | leaderboard.api_leaderboard | Login | JSON standings |
| GET | /scores | scores.scores | Login | Tournament scoreboard |
| GET | /admin | admin.admin | Admin | Admin panel |
| POST | /admin/golfer | admin.add_golfer | Admin | Add a player |
| POST | /admin/golfer/ID/delete | admin.remove_golfer | Admin | Delete a player |
| POST | /admin/golfer/ID/edit | admin.edit_golfer | Admin | Edit a player |
| POST | /admin/init-db | admin.init_db | Admin* | Run schema.sql (*skips auth if no tables exist) |
| GET | /admin/test-espn | admin.test_espn | Admin | Raw ESPN parsed data as JSON |
| GET | /admin/espn-field | admin.espn_field | Admin | ESPN field listing as JSON |
| POST | /admin/import-field | admin.import_field | Admin | Import ESPN field into golfers table |
| GET | /admin/update-scores | admin.update_scores_route | Admin | Pull latest scores from ESPN |
| POST | /admin/bulk-tier-update | admin.bulk_tier_update | Admin | Batch tier reassignment |

**Auth levels**: "Login" = session user_id required. "Admin" = logged in and username matches ADMIN_USERNAME.

## ESPN API integration

### Endpoint
```
GET https://site.api.espn.com/apis/site/v2/sports/golf/pga/scoreboard
```
No authentication required. Returns the current/most recent PGA Tour event.

### Data flow
1. `fetch_leaderboard()` -- GET request with 10s timeout, User-Agent header, returns raw JSON or None on failure
2. `parse_leaderboard(data)` -- Extracts from JSON:
   - Tournament: name, event_id, status (pre/active/complete), current_round
   - Per golfer: espn_id, name, position (from `order` field), to_par (from `score`), round scores (from `linescores[].value`), status (MC detected when only 2 rounds played past round 2)
3. `update_scores(conn)` -- Calls fetch + parse, then:
   - Updates `tournament_state` with tournament metadata
   - Matches ESPN golfers to our `golfers` table by `espn_id`
   - Upserts matched golfers into `golfer_scores`
   - Ignores ESPN golfers not in our pool

### ESPN JSON structure
```
events[0].competitions[0].competitors[] -> each golfer
  .id -> ESPN player ID
  .athlete.fullName -> name
  .order -> position
  .score -> to-par string
  .linescores[] -> round scores (.period = round number, .value = strokes)
events[0].competitions[0].status.type.state -> "pre", "in", "post"
events[0].competitions[0].status.period -> current round number
```

## Scoring engine

### 4-of-6 scoring
- Each user picks 6 golfers (one per tier)
- Sort all 6 by total strokes ascending
- Best 4 count toward team total
- Worst 2 are benched

### MC/WD/DQ penalty
- Penalty score = MAX(total_strokes) among all active golfers + 1
- Applied to any golfer with status MC, WD, or DQ
- If a user has 3+ golfers miss the cut, they're forced to count penalty scores

### Tiebreaker
- Primary: team_total ascending (lowest wins)
- Tiebreak: best individual finishing position among counting golfers (parsed from position string, stripping "T" prefix)
- Users with no scores sort to bottom with rank "--"

### Rank notation
- Sequential: 1, 2, 3, 4, 5
- Ties: T3, T3 (both get the same rank, next rank skips)

## CSS conventions

### Color palette
| Variable | Value | Usage |
|----------|-------|-------|
| --augusta-green | #006747 | Buttons, table headers, nav accent |
| --augusta-dark | #003d2a | Button hover, nav background base |
| --augusta-gold | #C8A951 | Brand text, labels, borders, to-par numbers |
| --augusta-cream | #FFF8E7 | Body text on dark backgrounds |
| --augusta-white | #FFFFFF | Table header text |
| --over-par | #C41E3A | Over-par scores (not currently used on scores page) |
| --under-par | #00a86b | Under-par scores (not currently used on scores page) |
| --panel-bg | rgba(0,30,20,0.75) | Content panels, auth containers |
| --cell-bg | rgba(0,30,20,0.7) | Table cells |
| --grid-line | rgba(200,169,81,0.3) | Table borders |

### Font usage
- **Cormorant Garamond** (weight 500-600): Page titles, section headers, nav brand, form labels, buttons
- **Libre Baskerville** (weight 400/700): Body text, table data, nav links, form inputs, dropdown options

### Uppercase rules
- **Only** `.leaderboard-table thead th` uses text-transform: uppercase
- Everything else is mixed case
- Nav brand reads "Baltz Masters Pool"

## Frontend patterns

### Custom dropdowns
All `<select>` elements (except inline admin table selects) are replaced with custom dropdowns:
- `<input type="hidden">` holds the form value
- `.custom-dropdown-trigger` div shows current selection with arrow
- `.custom-dropdown-options` div absolutely positioned below, max-height 240px with scroll
- JS handles open/close, click-outside-to-close, value/label updates
- Options background: rgba(0,20,12,0.92), hover: rgba(0,61,42,0.92)

### Background image
- Hole 12 (Golden Bell) JPEG as full-viewport background via `.bg-image` div with `position: fixed`
- Dark overlay div at rgba(0,0,0,0.5) for text readability
- Mobile (768px): switches to `position: absolute` with `height: 100vh` for iOS Safari compatibility
- Child templates can override via `{% block bg_image %}`

### Auth page pattern
- `.auth-container`: max-width 400px, centered, semi-transparent dark panel with 1px gold border
- Form inputs: transparent background, bottom-border only (gold), cream text
- Buttons: solid augusta-green, no border-radius

### Chrome autofill override
Custom `-webkit-autofill` rules prevent Chrome from overriding the dark transparent input styling with its default blue/white autofill colors.
