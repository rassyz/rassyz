#!/usr/bin/env python3
"""Update the Strava stats section of a GitHub profile README.

Reads STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET / STRAVA_REFRESH_TOKEN from env.
If TOKEN_FILE is set, the refresh token is read from that JSON file instead
({"refresh_token": "..."}) and the ROTATED refresh token is written back to
it after every exchange (Strava invalidates the old one on each use).

Dry-run:  python3 update_strava.py --activities activities.json --readme README.md
"""
import argparse, json, os, sys, urllib.request, urllib.parse
from datetime import datetime

API = "https://www.strava.com/api/v3"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
START, END = "<!-- STRAVA:START -->", "<!-- STRAVA:END -->"

def post_token(params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request("https://www.strava.com/oauth/token", data=data)
    with urllib.request.urlopen(req) as r:
        return json.load(r)

def get_json(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)

def fetch_activities(token):
    acts, page = [], 1
    while True:
        batch = get_json(f"{API}/athlete/activities?per_page=200&page={page}", token)
        if not batch:
            return acts
        acts.extend(batch)
        page += 1

def fmt_en(x, dec=1):
    """English number format: 673.2 / 1,356"""
    return f"{x:,.{dec}f}"

def render(acts, now):
    year = now.year
    runs = [a for a in acts
            if (a.get("sport_type") == "Run" or a.get("type") == "Run")
            and a["start_date_local"].startswith(str(year))]
    total_km = sum(a["distance"] for a in runs) / 1000
    longest = max((a["distance"] for a in runs), default=0) / 1000
    elev = sum(a.get("total_elevation_gain", 0) for a in runs)
    monthly = [0.0] * 12
    for a in runs:
        monthly[int(a["start_date_local"][5:7]) - 1] += a["distance"] / 1000
    mx = max(monthly) or 1
    lines = [
        "## 🏃‍♂️ Running Journey",
        "",
        f"**Statistics ({year})**",
        f"- **Total distance:** {fmt_en(total_km)} km",
        f"- **Total runs:** {len(runs)}",
        f"- **Longest run:** {fmt_en(longest, 2)} km",
        f"- **Total elevation:** {fmt_en(elev, 0)} m",
        "",
        f"**Monthly volume ({year}):**",
        "```",
    ]
    for i, v in enumerate(monthly):
        filled = max(1, round(v / mx * 12)) if v > 0 else 0
        bar = "█" * filled + "░" * (12 - filled)
        note = f"  (as of {MONTHS[now.month - 1]} {now.day})" if i == now.month - 1 else ""
        lines.append(f"{MONTHS[i]:<4} {bar}  {fmt_en(v):>6} km{note}")
    lines.append("```")
    return "\n".join(lines)

def splice(readme_text, section):
    if START in readme_text and END in readme_text:
        pre = readme_text.split(START)[0]
        post = readme_text.split(END, 1)[1]
        return f"{pre}{START}\n{section}\n{END}{post}"
    return readme_text.rstrip() + f"\n\n{START}\n{section}\n{END}\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--activities", help="local activities JSON (dry-run, skips API)")
    ap.add_argument("--readme", default="README.md")
    args = ap.parse_args()

    token_file = os.environ.get("TOKEN_FILE")
    if args.activities:
        acts = json.load(open(args.activities))
    else:
        cid = os.environ["STRAVA_CLIENT_ID"]
        secret = os.environ["STRAVA_CLIENT_SECRET"]
        if token_file and os.path.exists(token_file):
            refresh = json.load(open(token_file))["refresh_token"]
        else:
            refresh = os.environ["STRAVA_REFRESH_TOKEN"]
        tok = post_token({"client_id": cid, "client_secret": secret,
                          "refresh_token": refresh, "grant_type": "refresh_token"})
        if token_file:
            json.dump({"refresh_token": tok["refresh_token"]}, open(token_file, "w"))
        acts = fetch_activities(tok["access_token"])

    section = render(acts, datetime.now())
    old = open(args.readme).read() if os.path.exists(args.readme) else ""
    new = splice(old, section)
    if new != old:
        open(args.readme, "w").write(new)
        print("README updated")
    else:
        print("No change")

if __name__ == "__main__":
    sys.exit(main())
