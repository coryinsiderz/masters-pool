# Baltz Masters Pool -- Backlog

## Pre-Masters Must Do

- [ ] Remove test data routes (/admin/create-test-users, /admin/reset-for-testing) before go-live
- [ ] Remove mock scorecard data function (get_mock_scorecard_data) and fallback in scores route
- [ ] Set ESPN event ID targeting for The Masters specifically (currently uses whatever tournament is active)
- [ ] Run /admin/init-db on production to ensure schema is current
- [ ] Verify picks deadline is correct: 2026-04-09T07:30:00-04:00
- [ ] Test registration flow end-to-end on production
- [ ] Set up real golfer tiers for Masters field

## Features to Build

### ~~View other entrants' teams~~
- [x] View other entrants' teams (implemented: Their Team dropdown + Versus side-by-side)

### ~~Forgot password flow~~
- [x] Forgot password flow (implemented: recovery question modal on login page)

### DG API projections integration
- DataGolf API for win probability line charts throughout tournament week
- Primary next feature after Masters go-live
- Show team win probability trends over time

### Different background images per page
- Each template can override the background via {% block bg_image %}
- Source high-quality Augusta photos for different holes
- Login: Hole 12 (current), Leaderboard: Hole 16, Scores: Amen Corner aerial, etc.

### Masters.com player links
- Link golfer names to their Masters.com profile page
- Requires mapping ESPN IDs to Masters.com player IDs
- Masters.com player pages: https://www.masters.com/en_US/players/player_{id}.html

## Known Issues to Fix

### Mobile traditional scorecard sticky columns
- Sticky columns (Score, Player, Owned) may still overlap on very narrow viewports (< 375px)
- Partially fixed with explicit widths and z-index but needs testing on real devices
- Consider hiding the Owned column on mobile to give more space

### Pool leaderboard sticky column gap
- Faint white line between Name and Total columns on mobile horizontal scroll
- border-right:none and box-shadow approaches tried, border-collapse artifacts remain
- Works fine on desktop, only visible on mobile when scrolling right

### Session transition
- When users first register, they get redirected to team page but may not have picked yet
- Consider a first-login flow that guides them to picks page
- Document the expected user journey: Register -> Make Picks -> View Squad -> Check Leaderboard

## Nice to Have

- [ ] Auto-refresh leaderboard/scores pages (polling or SSE)
- [ ] Push notifications for score changes (web push or SMS)
- [ ] Player photo avatars on golfer cards
- [ ] Historical pool results (archive past years)
- [ ] Pool chat/trash talk feature
- [ ] Draft-style pick selection (real-time, one at a time)
- [ ] Leaderboard movement indicators (up/down arrows showing rank changes)
- [ ] Per-round score breakdowns on pool leaderboard (R1-R4 team totals)
- [ ] Export leaderboard to image for sharing
- [ ] Mobile app wrapper (PWA)
