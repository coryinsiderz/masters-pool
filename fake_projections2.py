"""Throwaway: delete old fake data, insert new dual actual/projected test data."""
import os
import random
from datetime import datetime, timedelta, timezone

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = True

# 1. Delete old fake data
with conn.cursor() as cur:
    cur.execute("DELETE FROM team_projections WHERE snapshot_time >= '2026-04-05 23:04:06'")
    print(f"Deleted {cur.rowcount} team_projections rows")
    cur.execute("DELETE FROM golfer_projections WHERE snapshot_time >= '2026-04-05 23:04:06'")
    print(f"Deleted {cur.rowcount} golfer_projections rows")

# 2. Get users with picks and their golfers
with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
    cur.execute(
        """SELECT p.user_id, p.golfer_id, p.tier, u.username
           FROM picks p JOIN users u ON p.user_id = u.id
           ORDER BY p.user_id, p.tier"""
    )
    all_picks = cur.fetchall()

users = {}
for p in all_picks:
    uid = p["user_id"]
    if uid not in users:
        users[uid] = {"username": p["username"], "golfers": []}
    users[uid]["golfers"].append(p["golfer_id"])

all_golfer_ids = list({p["golfer_id"] for p in all_picks})
print(f"\n{len(users)} users, {len(all_golfer_ids)} unique golfers")

# 3. Generate 5 snapshots within the tournament window
# Thu Apr 9 7:30 AM ET = 11:30 UTC, spaced 12 hours apart
base = datetime(2026, 4, 9, 11, 30, 0, tzinfo=timezone.utc)
snapshot_times = [base + timedelta(hours=i * 12) for i in range(5)]

# 4. Initialize golfer states
golfer_proj = {}  # projected finish (72-hole)
golfer_actual = {}  # actual cumulative score
for gid in all_golfer_ids:
    golfer_proj[gid] = round(random.uniform(-8, 4), 1)
    golfer_actual[gid] = 0.0  # everyone starts at E

golfer_rows = 0
team_rows = 0
earliest = snapshot_times[0]

for snap_idx, snap_time in enumerate(snapshot_times):
    # Evolve golfer states
    with conn.cursor() as cur:
        for gid in all_golfer_ids:
            if snap_idx > 0:
                # Projected drifts slightly
                golfer_proj[gid] = round(golfer_proj[gid] + random.uniform(-1.0, 1.0), 1)
                # Actual accumulates round scores (getting further from zero)
                golfer_actual[gid] = round(golfer_actual[gid] + random.uniform(-2.5, 1.5), 1)

            mc_prob = max(0, min(1, 0.1 + (golfer_proj[gid] / 40)))

            cur.execute(
                """INSERT INTO golfer_projections
                   (golfer_id, projected_to_par, actual_to_par, mc_probability, win_probability, snapshot_time)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (gid, golfer_proj[gid], golfer_actual[gid], round(mc_prob, 4), 0.01, snap_time),
            )
            golfer_rows += 1

    # Compute team projections (best 4 of 6 for both)
    with conn.cursor() as cur:
        for uid, udata in users.items():
            proj_scores = []
            actual_scores = []
            for gid in udata["golfers"]:
                proj_scores.append(golfer_proj[gid])
                actual_scores.append(golfer_actual[gid])

            proj_scores.sort()
            proj_total = round(sum(proj_scores[:4]), 1)

            actual_scores.sort()
            actual_total = round(sum(actual_scores[:4]), 1)

            cur.execute(
                """INSERT INTO team_projections
                   (user_id, projected_total, actual_total, snapshot_time)
                   VALUES (%s, %s, %s, %s)""",
                (uid, proj_total, actual_total, snap_time),
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
