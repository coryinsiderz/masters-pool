"""Test name matching: compare API field against our golfers table."""
import os
import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
API_KEY = os.environ.get("PROJECTIONS_API_KEY") or os.environ.get("DG_API_KEY")

# 1. Get our golfers
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
    cur.execute("SELECT id, name, dg_name, tier FROM golfers ORDER BY name")
    our_golfers = cur.fetchall()
conn.close()

print(f"Our golfers table: {len(our_golfers)} players")
print(f"Sample: {[g['name'] for g in our_golfers[:5]]}")

# 2. Get API field (using DG pre-tournament as proxy since GBT may not be live yet)
url = "https://feeds.datagolf.com/preds/pre-tournament"
r = requests.get(url, params={"tour": "pga", "key": API_KEY}, timeout=15)
data = r.json()
api_players = data.get("baseline", [])
print(f"\nAPI field: {len(api_players)} players ({data.get('event_name', '?')})")

# 3. Build last-name lookup from our golfers
def extract_last(name):
    if not name: return ""
    name = name.strip()
    if "," in name:
        return name.split(",")[0].strip().lower()
    parts = name.split()
    return parts[-1].strip().lower() if parts else ""

our_lookup = {}
for g in our_golfers:
    last = extract_last(g["name"])
    if last in our_lookup:
        if isinstance(our_lookup[last], list):
            our_lookup[last].append(g)
        else:
            our_lookup[last] = [our_lookup[last], g]
    else:
        our_lookup[last] = g

# 4. Match
matched = []
unmatched_api = []
for p in api_players:
    api_name = p["player_name"]
    api_last = extract_last(api_name)
    hit = our_lookup.get(api_last)
    if hit is None:
        unmatched_api.append(api_name)
    elif isinstance(hit, list):
        # Try first name
        api_first = api_name.split(",")[1].strip().lower() if "," in api_name else ""
        found = False
        for g in hit:
            g_first = g["name"].split(",")[1].strip().lower() if "," in g["name"] else g["name"].split()[0].lower()
            if g_first == api_first:
                matched.append((api_name, g["name"]))
                found = True
                break
        if not found:
            unmatched_api.append(f"{api_name} (ambiguous)")
    else:
        matched.append((api_name, hit["name"]))

# 5. Our golfers not matched
matched_our_names = {m[1] for m in matched}
unmatched_ours = [g["name"] for g in our_golfers if g["name"] not in matched_our_names]

# 6. Report
print(f"\n{'='*60}")
print(f"RESULTS")
print(f"{'='*60}")
print(f"Matched: {len(matched)} / {len(api_players)} API players")
print(f"Match rate vs API field: {len(matched)/len(api_players)*100:.1f}%")
print(f"Our golfers matched: {len(matched)} / {len(our_golfers)}")

if matched:
    print(f"\nSample matches:")
    for api, ours in matched[:10]:
        print(f"  {api:30s} -> {ours}")

if unmatched_api:
    print(f"\nUnmatched API players ({len(unmatched_api)}):")
    for name in sorted(unmatched_api)[:30]:
        print(f"  {name}")
    if len(unmatched_api) > 30:
        print(f"  ... and {len(unmatched_api)-30} more")

if unmatched_ours:
    print(f"\nOur golfers not in API field ({len(unmatched_ours)}):")
    for name in sorted(unmatched_ours):
        print(f"  {name}")
