"""Build the NPL app's season cache on the PC (fast), for upload to the Cardputer.

    python tools/npl_seed.py            -> writes build/npl_cache.json
    mpremote connect COM5 resume cp build/npl_cache.json :/flash/npl_cache.json

The app keeps this file up to date by itself; seeding just saves the first
load (~21 requests) on the device.
"""
import json
import os
import urllib.request

FEED = "https://site.api.espn.com/apis/site/v2/sports/cricket/23081/scoreboard"
OUT = os.path.join(os.path.dirname(__file__), "..", "build", "npl_cache.json")


def get(day=None):
    url = FEED + ("?dates=" + day if day else "")
    req = urllib.request.Request(url, headers={"User-Agent": "CardOS"})
    return json.loads(urllib.request.urlopen(req, timeout=25).read())


def events(js):
    out = []
    for e in js.get("events", []):
        comp = e["competitions"][0]
        out.append({
            "utc": e.get("date", ""),
            "no": comp.get("description", ""),
            "st": e["status"]["type"].get("state", ""),
            "sum": e["status"].get("summary", ""),
            "v": comp.get("venue", {}).get("fullName", ""),
            "t": [[c["team"].get("abbreviation", "TBA"), c.get("score", "") or "", bool(c.get("winner"))]
                  for c in comp.get("competitors", [])],
        })
    return out


def main():
    cal = [c[:10].replace("-", "") for c in get()["leagues"][0]["calendar"]]
    cache = {"cal": cal, "days": {}}
    for d in cal:
        cache["days"][d] = events(get(d))
        print(d, len(cache["days"][d]), "matches")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(cache, f, separators=(",", ":"))
    print("wrote", os.path.abspath(OUT), os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
