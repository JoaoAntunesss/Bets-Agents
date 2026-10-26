#!/usr/bin/env python3
"""Fetches final scores for a day from ESPN (no API key) and writes matches/YYYY-MM-DD/results.json.

Usage: python scripts/results.py [YYYY-MM-DD]
"""
import json
import sys
from datetime import date
from pathlib import Path

from fixtures_today import LEAGUES, fetch


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    results = []
    for code, name in LEAGUES.items():
        try:
            data = fetch(code, day)
        except Exception as e:
            print(f"[warning] {name}: {e}", file=sys.stderr)
            continue
        for ev in data.get("events", []):
            comp = ev["competitions"][0]
            teams = {c["homeAway"]: c for c in comp["competitors"]}
            results.append({
                "league": name,
                "kickoff_utc": ev.get("date"),
                "home": teams["home"]["team"]["displayName"],
                "away": teams["away"]["team"]["displayName"],
                "home_score": teams["home"].get("score"),
                "away_score": teams["away"].get("score"),
                "status": ev["status"]["type"]["description"],
                "finished": bool(ev["status"]["type"].get("completed")),
            })
    folder = Path("matches") / day
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    done = sum(1 for r in results if r["finished"])
    print(f"{len(results)} matches on {day}, {done} finished")
    for r in results:
        print(f'{r["league"]:<14} | {r["home"]} {r["home_score"]}-{r["away_score"]} {r["away"]} ({r["status"]})')


if __name__ == "__main__":
    main()
