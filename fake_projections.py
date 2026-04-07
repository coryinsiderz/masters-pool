"""Throwaway script: insert fake projection snapshots for chart testing."""
import os
import random
from datetime import datetime, timedelta, timezone

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = True

# 1. Get all users who have picks, with their picked golfers
with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
    cur.execute(
        """SELECT p.user_id, p.golfer_id, p.tier, u.username
           FROM picks p
           JOIN users u ON p.user_id = u.id
           ORDER BY p.user_id, p.tier"""
    )
    all_picks = cur.fetchall()

# Group picks by user
users = {}
for p in all_picks:
    uid = p["user_id"]
    if uid not in users:
        users[uid] = {"username": p["username"], "golfers": []}
    users[uid]["golfers"].append(p["golfer_id"])

print(f"Found {len(users)} users with picks")
print(f"Total golfer-pick pairs: {len(all_picks)}")

# 2. Generate 5 snapshots, 3 hours apart, starting 15 hours ago
now = datetime.now(timezone.utc)
snapshot_times = [now - timedelta(hours=15 - i * 3) for i in range(5)]

# 3. Assign each golfer a starting projected_to_par, then random-walk
all_golfer_ids = list({p["golfer_id"] for p in all_picks})
golfer_state = {}
for gid in all_golfer_ids:
    golfer_state[gid] = round(random.uniform(-5, 3), 1)

golfer_rows = 0
team_rows = 0
earliest = snapshot_times[0]

for snap_idx, snap_time in enumerate(snapshot_times):
    # Insert golfer projections
    with conn.cursor() as cur:
        for gid in all_golfer_ids:
            # Random walk: drift by -1.5 to +1.5 per snapshot
            if snap_idx > 0:
                golfer_state[gid] = round(
                    golfer_state[gid] + random.uniform(-1.5, 1.5), 1
                )
            proj = golfer_state[gid]
            mc_prob = max(0, min(1, 0.15 + (proj / 30)))  # higher score = more MC risk
            win_prob = max(0, 0.05 - (proj / 100))

            cur.execute(
                """INSERT INTO golfer_projections
                   (golfer_id, projected_to_par, mc_probability, win_probability, snapshot_time)
                   VALUES (%s, %s, %s, %s, %s)""",
                (gid, proj, round(mc_prob, 4), round(win_prob, 4), snap_time),
            )
            golfer_rows += 1

    # Compute team projections (best 4 of 6)
    with conn.cursor() as cur:
        for uid, udata in users.items():
            scores = []
            for gid in udata["golfers"]:
                scores.append(golfer_state[gid])
            scores.sort()
            total = round(sum(scores[:4]), 1)

            cur.execute(
                """INSERT INTO team_projections
                   (user_id, projected_total, snapshot_time)
                   VALUES (%s, %s, %s)""",
                (uid, total, snap_time),
            )
            team_rows += 1

conn.close()

print(f"\nInserted {golfer_rows} golfer_projections rows")
print(f"Inserted {team_rows} team_projections rows")
print(f"Snapshots: {len(snapshot_times)}")
for i, t in enumerate(snapshot_times):
    print(f"  [{i+1}] {t.isoformat()}")

earliest_str = earliest.strftime("%Y-%m-%d %H:%M:%S")
print(f"\n{'='*60}")
print(f"CLEANUP SQL (run manually after testing):")
print(f"{'='*60}")
print(f"DELETE FROM team_projections WHERE snapshot_time >= '{earliest_str}';")
print(f"DELETE FROM golfer_projections WHERE snapshot_time >= '{earliest_str}';")
