"""Throwaway script to explore DataGolf API responses."""
import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("DG_API_KEY")
if not KEY:
    raise SystemExit("DG_API_KEY not found in .env")

ENDPOINTS = [
    ("PRE-TOURNAMENT PREDICTIONS", "https://feeds.datagolf.com/preds/pre-tournament"),
    ("IN-PLAY PREDICTIONS", "https://feeds.datagolf.com/preds/in-play"),
    ("FIELD UPDATES", "https://feeds.datagolf.com/field-updates"),
]

for label, url in ENDPOINTS:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  {url}")
    print(f"{'='*60}")
    try:
        r = requests.get(url, params={"tour": "pga", "key": KEY}, timeout=10)
        print(f"Status: {r.status_code}")
        if r.status_code != 200:
            print(f"Response: {r.text[:500]}")
            continue
        data = r.json()
        # Show structure
        if isinstance(data, list):
            print(f"Type: list, Length: {len(data)}")
            print(f"Keys per item: {list(data[0].keys()) if data else 'empty'}")
            print("\nFirst 3 items:")
            print(json.dumps(data[:3], indent=2))
        elif isinstance(data, dict):
            print(f"Type: dict, Top-level keys: {list(data.keys())}")
            for k, v in data.items():
                if isinstance(v, list):
                    print(f"\n  '{k}': list of {len(v)} items")
                    if v:
                        print(f"  Keys per item: {list(v[0].keys()) if isinstance(v[0], dict) else type(v[0])}")
                        print(f"  First 3:")
                        print(json.dumps(v[:3], indent=2))
                else:
                    print(f"\n  '{k}': {json.dumps(v)}")
        else:
            print(json.dumps(data, indent=2)[:1000])
    except Exception as e:
        print(f"Error: {e}")
