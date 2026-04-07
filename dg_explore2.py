import requests, os, json
from dotenv import load_dotenv
load_dotenv()
key = os.getenv('DG_API_KEY')

# Check these endpoints for strokes-based projections:
endpoints = [
    f"https://feeds.datagolf.com/preds/in-play?tour=pga&key={key}&odds_format=decimal",
    f"https://feeds.datagolf.com/preds/pre-tournament?tour=pga&file_format=json&key={key}&odds_format=decimal",
    f"https://feeds.datagolf.com/preds/pre-tournament-pred-dist?tour=pga&key={key}",
    f"https://feeds.datagolf.com/preds/in-play-expected-totals?tour=pga&key={key}",
]

for url in endpoints:
    name = url.split('datagolf.com/')[1].split('?')[0]
    print(f"\n{'='*60}")
    print(f"ENDPOINT: {name}")
    r = requests.get(url)
    print(f"STATUS: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        if isinstance(data, list):
            print(f"Array of {len(data)} items")
            print(json.dumps(data[:2], indent=2))
        elif isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, list):
                    print(f"  {k}: array of {len(v)}")
                    if len(v) > 0:
                        print(json.dumps(v[:2], indent=2))
                else:
                    print(f"  {k}: {v}")
    else:
        print(r.text[:300])
