#!/usr/bin/env python3
"""Ledger: reads matches/*/bets.json and computes profit, ROI and hit rates.

Usage: python scripts/ledger.py        (prints a summary)
Also imported by dashboard.py.
"""
import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MATCHES = ROOT / "matches"


def load_bets():
    bets = []
    for f in sorted(MATCHES.glob("*/bets.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for b in data.get("bets", []):
            b = dict(b)
            b["date"] = data.get("date") or f.parent.name
            b.setdefault("tier", "")
            b.setdefault("status", "pending")
            b.setdefault("placed", False)
            b.setdefault("legs", [])
            bets.append(b)
    return bets


def set_placed(bet_id, placed):
    for f in MATCHES.glob("*/bets.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        hit = False
        for b in data.get("bets", []):
            if b.get("id") == bet_id:
                b["placed"] = bool(placed)
                hit = True
        if hit:
            f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
    return False


def returned(b):
    st = b.get("status")
    if st == "won":
        return b["stake"] * b["odds"]
    if st == "void":
        return b["stake"]
    return 0.0


def agg(bets):
    settled = [b for b in bets if b.get("status") in ("won", "lost")]
    pending = [b for b in bets if b.get("status") == "pending"]
    staked = sum(b["stake"] for b in settled)
    ret = sum(returned(b) for b in settled)
    won = sum(1 for b in settled if b["status"] == "won")
    return {
        "bets": len(bets), "settled": len(settled), "won": won, "lost": len(settled) - won,
        "pending": len(pending), "pending_stake": round(sum(b["stake"] for b in pending), 2),
        "staked": round(staked, 2), "returned": round(ret, 2), "profit": round(ret - staked, 2),
        "roi": round((ret - staked) / staked * 100, 1) if staked else None,
        "hit_rate": round(won / len(settled) * 100, 1) if settled else None,
    }


def summarize(bets):
    placed = [b for b in bets if b.get("placed")]
    tiers = {}
    for t in sorted({b["tier"] for b in bets}):
        tiers[t] = agg([b for b in bets if b["tier"] == t])
    markets = {}
    for b in bets:
        for leg in b["legs"]:
            r = leg.get("result")
            if r in ("won", "lost"):
                m = markets.setdefault(leg.get("market", "?"), {"won": 0, "lost": 0})
                m[r] += 1
    market_list = sorted(({"market": k, **v, "rate": round(v["won"] / (v["won"] + v["lost"]) * 100)} for k, v in markets.items()),
                         key=lambda x: -(x["won"] + x["lost"]))
    series, cum, cump = [], 0.0, 0.0
    for d in sorted({b["date"] for b in bets}):
        for b in bets:
            if b["date"] == d and b["status"] in ("won", "lost"):
                p = returned(b) - b["stake"]
                cum += p
                if b.get("placed"):
                    cump += p
        series.append({"date": d, "profit": round(cum, 2), "profit_placed": round(cump, 2)})
    return {"all": agg(bets), "placed": agg(placed), "by_tier": tiers, "by_market": market_list[:8],
            "series": series, "bets": sorted(bets, key=lambda b: (b["date"], b["tier"]), reverse=True)}


def demo_bets():
    """Fictional ledger for the dashboard demo mode."""
    rnd = random.Random(7)
    teams = ["Falcons", "Rovers", "United", "City", "Athletic", "Wanderers", "Albion", "Dynamo", "Sporting", "Real Norte"]
    markets = ["Over 1.5 goals", "Home or draw", "Both teams to score", "Over 2.5 goals", "Away or draw", "Over 8.5 corners"]
    shape = {"safe": (3, 2.0, .62), "balanced": (5, 1.5, .52), "ambitious": (8, 1.0, .40)}
    bets = []
    today = date.today()
    for i in range(14, 0, -1):
        d = (today - timedelta(days=i)).isoformat()
        for tier, (n, stake, p) in shape.items():
            legs, odds = [], 1.0
            for _ in range(n):
                o = round(rnd.uniform(1.25, 1.75), 2)
                odds *= o
                a, b = rnd.sample(teams, 2)
                res = "won" if rnd.random() < p + .10 else "lost"
                legs.append({"match": f"{a} vs {b}", "league": "Demo League", "market": rnd.choice(markets), "odds": o, "result": res})
            won = all(l["result"] == "won" for l in legs)
            bets.append({"id": f"{d}-{tier}", "date": d, "tier": tier, "stake": stake, "odds": round(odds, 2),
                         "status": "won" if won else "lost", "placed": rnd.random() < .7, "legs": legs})
    for tier, (n, stake, p) in shape.items():
        legs = [{"match": "Falcons vs Rovers", "league": "Demo League", "market": "Over 1.5 goals", "odds": 1.4, "result": "pending"}] * n
        bets.append({"id": f"{today.isoformat()}-{tier}", "date": today.isoformat(), "tier": tier, "stake": stake,
                     "odds": round(1.4 ** n, 2), "status": "pending", "placed": False, "legs": legs})
    return bets


def main():
    s = summarize(load_bets())
    a = s["all"]
    print(f"Bets: {a['bets']} ({a['settled']} settled, {a['pending']} pending)")
    if a["settled"]:
        print(f"Staked {a['staked']}  Returned {a['returned']}  Profit {a['profit']:+}  ROI {a['roi']}%  Hit rate {a['hit_rate']}%")
        for t, v in s["by_tier"].items():
            print(f"  {t:<10} {v['won']}/{v['settled']} won  profit {v['profit']:+}")
    else:
        print("Nothing settled yet. Run /settle after the matches finish.")


if __name__ == "__main__":
    main()
