#!/usr/bin/env python3
"""Lists today's matches in 10 leagues (ESPN, no API key needed).

Usage: python scripts/fixtures_today.py [YYYY-MM-DD]
Writes matches/YYYY-MM-DD/fixtures.json and prints a summary.
"""
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

LEAGUES = {
    "eng.1": "Premier League",
    "esp.1": "La Liga",
    "ita.1": "Serie A",
    "ger.1": "Bundesliga",
    "fra.1": "Ligue 1",
    "por.1": "Primeira Liga",
    "ned.1": "Eredivisie",
    "eng.2": "Championship",
    "bra.1": "Brasileirão",
    "usa.1": "MLS",
}


def fetch(code, day):
    url = (
        f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard"
        f"?dates={day.replace('-', '')}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    fixtures = []
    for code, name in LEAGUES.items():
        try:
            data = fetch(code, day)
        except Exception as e:
            print(f"[warning] {name}: {e}", file=sys.stderr)
            continue
        for ev in data.get("events", []):
            comp = ev["competitions"][0]
            teams = {c["homeAway"]: c["team"]["displayName"] for c in comp["competitors"]}
            fixtures.append(
                {
                    "league": name,
                    "kickoff_utc": ev.get("date"),
                    "home": teams.get("home"),
                    "away": teams.get("away"),
                    "status": ev["status"]["type"]["description"],
                    "venue": comp.get("venue", {}).get("fullName"),
                    "city": comp.get("venue", {}).get("address", {}).get("city"),
                }
            )
    folder = Path("matches") / day
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "fixtures.json").write_text(json.dumps(fixtures, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(fixtures)} matches on {day}")
    for m in sorted(fixtures, key=lambda x: x["kickoff_utc"] or ""):
        print(f'{(m["kickoff_utc"] or "")[11:16]} UTC | {m["league"]:<14} | {m["home"]} vs {m["away"]} ({m["status"]})')


if __name__ == "__main__":
    main()
