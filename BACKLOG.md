# Baltz Masters Pool -- Backlog

## Pre-Masters Must Do

- [ ] ESPN ID backfill: run /admin/backfill-espn-ids once ESPN loads Masters field (check daily Mon-Wed)
- [ ] Remove mock scorecard data function (get_mock_scorecard_data) and fallback in scores route
- [ ] Set ESPN event ID targeting for The Masters specifically (currently uses whatever tournament is active)
- [ ] Run /admin/init-db on production to ensure schema is current
- [ ] Set up real golfer tiers for Masters field (currently all tier 1)
- [ ] Projections model validation: verify betting tool Masters projections flow correctly once tournament starts

## Features to Build

### Different background images per page
- Each template can override the background via {% block bg_image %}
- Source high-quality Augusta photos for different holes
- Login: Hole 12 (current), Leaderboard: Hole 16, Scores: Amen Corner aerial, etc.

### Masters.com player links
- Link golfer names to their Masters.com profile page
- Requires manual ID mapping, no programmatic source
- Masters.com player pages: https://www.masters.com/en_US/players/player_{id}.html

### Projections chart improvements
- Day labels on x-axis (Thu/Fri/Sat/Sun markers)
- Round start/end markers (vertical lines at round boundaries)
- Tooltip refinements
- Consider showing projected position alongside projected score

## Known Issues to Fix

### Pool leaderboard sticky column gap
- Faint white line between Name and Total columns on mobile horizontal scroll
- border-right:none and box-shadow approaches tried, border-collapse artifacts remain
- Works fine on desktop, only visible on mobile when scrolling right

### Pool leaderboard mini-card format iteration
- Current pipe-delimited format may need refinement based on real tournament data
- Test with actual Masters scores to validate readability

### Exposure page toggle styling refinement
- Filter buttons could use visual polish
- Consider tier count badges

### Session transition
- When users first register, they get redirected to team page but may not have picked yet
- Consider a first-login flow that guides them to picks page

## Nice to Have

- [ ] Auto-refresh leaderboard/scores pages (polling or SSE)
- [ ] Push notifications for score changes
- [ ] Player photo avatars on golfer cards
- [ ] Historical pool results (archive past years)
- [ ] Pool chat/trash talk feature
- [ ] Draft-style pick selection (real-time, one at a time)
- [ ] Leaderboard movement indicators (up/down arrows showing rank changes)
- [ ] Per-round score breakdowns on pool leaderboard
- [ ] Export leaderboard to image for sharing
- [ ] Mobile app wrapper (PWA)
- [ ] Admin password reset for users
- [ ] Test Venmo deeplink behavior on various devices
