#!/usr/bin/env python3
"""Analysis Room: local dashboard showing the agents working in real time.

Usage: python scripts/dashboard.py [port]
Opens http://localhost:8765 (in another terminal, while you run /today in Claude Code).

State is computed from the files the agents write to matches/YYYY-MM-DD/.
Needs no internet access and no extra libraries.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import ledger

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MATCHES = ROOT / "matches"
HTML = HERE / "dashboard.html"

# (file without .md, card name, description)
PHASES = [
    {
        "id": "collection", "name": "Collection", "mode": "match",
        "agents": [
            ("team-analyst", "Teams", "Form and playing style"),
            ("historian", "Historian", "Head-to-head"),
            ("referee", "Referee", "Cards, fouls, penalties"),
            ("meteorologist", "Meteorologist", "Weather, wind and pitch"),
            ("stadium", "Stadium", "Home advantage and travel"),
            ("medic", "Medic", "Injuries, suspensions, doubts"),
            ("reporter", "Reporter", "News, pressure and dressing room"),
            ("player-form", "Form", "Key players' current form"),
        ],
    },
    {
        "id": "markets", "name": "Specialists", "mode": "match",
        "agents": [
            ("market-result", "Result", "1X2, double chance, handicap"),
            ("market-goals", "Goals", "Totals and both teams to score"),
            ("market-corners", "Corners", "Match and per-team corners"),
            ("market-cards", "Cards", "Match cards"),
        ],
    },
    {
        "id": "builder", "name": "Builder", "mode": "global",
        "agents": [("proposals", "Builder", "Builds the day's 3 multiples")],
    },
    {
        "id": "jury", "name": "Jury", "mode": "global",
        "agents": [
            ("jury-devils-advocate", "Devil's advocate", "Looks for what could fail"),
            ("jury-statistician", "Statistician", "Confirms the real value"),
            ("jury-risk-manager", "Risk manager", "Limits and veto"),
            ("jury-news", "News", "Last-minute news and line-ups"),
        ],
    },
    {
        "id": "president", "name": "President", "mode": "global",
        "agents": [("decision", "President", "Final decision")],
    },
]

VOTES = re.compile(r"\b(APPROVE|REJECT|REDUCE STAKE|VETO|WAIT)\b")


def slugify(txt):
    import unicodedata
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", txt.lower()).strip("-")


def list_matches(folder):
    matches, seen = [], set()
    shortlist = folder / "shortlist.json"
    if shortlist.exists():
        try:
            data = json.loads(shortlist.read_text(encoding="utf-8"))
        except Exception:
            data = []
        for m in data if isinstance(data, list) else []:
            if not isinstance(m, dict):
                continue
            slug = m.get("folder") or slugify(f'{m.get("home", "")}-vs-{m.get("away", "")}')
            if slug and slug not in seen:
                seen.add(slug)
                title = f'{m.get("home", "?")} vs {m.get("away", "?")}'
                matches.append({"folder": slug, "title": title, "league": m.get("league", "")})
    for d in sorted(p for p in folder.iterdir() if p.is_dir()):
        if d.name not in seen:
            seen.add(d.name)
            matches.append({"folder": d.name, "title": d.name.replace("-vs-", " vs ").replace("-", " "), "league": ""})
    return matches


def read(p):
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def _state(day):
    folder = MATCHES / day
    dates = sorted((p.name for p in MATCHES.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name)), reverse=True) if MATCHES.exists() else []
    base = {"date": day, "dates": dates, "matches": [], "phases": [], "started": False, "events": [],
            "proposals": "", "decision": "", "updated": datetime.now().strftime("%H:%M:%S")}
    if not folder.exists():
        for ph in PHASES:
            base["phases"].append({"id": ph["id"], "name": ph["name"], "mode": ph["mode"], "agents": [
                {"id": a[0], "name": a[1], "desc": a[2], "state": "waiting", "done": 0, "total": 0, "files": [], "votes": {}}
                for a in ph["agents"]]})
        return base

    matches = list_matches(folder)
    n = len(matches)
    base["matches"] = matches
    base["started"] = (folder / "shortlist.json").exists() or any(folder.iterdir())
    previous_complete = True
    for ph in PHASES:
        agents, all_done = [], True
        for fname, name, desc in ph["agents"]:
            files, votes = [], {}
            if ph["mode"] == "match":
                total = n
                for m in matches:
                    fp = folder / m["folder"] / f"{fname}.md"
                    if fp.exists():
                        files.append({"label": m["title"], "path": f'{day}/{m["folder"]}/{fname}.md', "t": fp.stat().st_mtime})
            else:
                total = 1
                if (folder / f"{fname}.md").exists():
                    files.append({"label": name, "path": f"{day}/{fname}.md", "t": (folder / f"{fname}.md").stat().st_mtime})
                    if ph["id"] == "jury":
                        for v in VOTES.findall(read(folder / f"{fname}.md")):
                            votes[v] = votes.get(v, 0) + 1
            done = len(files)
            if total > 0 and done == total:
                st = "done"
            elif done > 0 or (previous_complete and base["started"]):
                st = "working"
            else:
                st = "waiting"
            if st != "done":
                all_done = False
            agents.append({"id": fname, "name": name, "desc": desc, "state": st,
                           "done": done, "total": total, "files": files, "votes": votes})
        previous_complete = previous_complete and all_done
        base["phases"].append({"id": ph["id"], "name": ph["name"], "mode": ph["mode"], "agents": agents})
    events = []
    for ph in base["phases"]:
        for a in ph["agents"]:
            for fi in a["files"]:
                events.append({"t": fi["t"], "time": datetime.fromtimestamp(fi["t"]).strftime("%H:%M:%S"),
                               "agent": a["name"], "id": a["id"], "phase": ph["id"],
                               "match": fi["label"] if ph["mode"] == "match" else ""})
    base["events"] = sorted(events, key=lambda e: e["t"], reverse=True)[:40]
    base["proposals"] = read(folder / "proposals.md")
    base["decision"] = read(folder / "decision.md")
    return base


# ---------- Run Claude from the dashboard ----------
ALLOWED_TOOLS = "WebSearch,WebFetch,Agent,Task,Read,Write,Edit,Glob,Grep,Bash(python *),Bash(python3 *)"
EXEC = {"proc": None, "started": None, "log": None, "target": ""}
LOCK = threading.Lock()


def find_claude():
    c = shutil.which("claude")
    if c:
        return c
    for name in ("claude.exe", "claude"):
        p = Path.home() / ".local" / "bin" / name
        if p.exists():
            return str(p)
    return None


def start(target, command="/today"):
    with LOCK:
        proc = EXEC["proc"]
        if proc is not None and proc.poll() is None:
            return {"ok": False, "error": "An analysis is already running."}
        exe = find_claude()
        if not exe:
            return {"ok": False, "error": "Could not find Claude Code. Open a terminal and check that this works: claude --version"}
        day = date.today().isoformat()
        folder = MATCHES / day
        folder.mkdir(parents=True, exist_ok=True)
        target = re.sub(r"[^\w\s\-.,'\u00c0-\u00ff]", "", target or "").strip()[:80]
        prompt = command + (f" {target}" if target else "")
        cmd = [exe, "-p", prompt, "--model", "sonnet", "--permission-mode", "acceptEdits",
               "--allowedTools", ALLOWED_TOOLS, "--permission-prompts", "none"]
        log = open(folder / "_claude.log", "w", encoding="utf-8")
        flags = 0x08000000 if os.name == "nt" else 0  # no extra console window on Windows
        try:
            EXEC["proc"] = subprocess.Popen(cmd, cwd=str(ROOT), stdin=subprocess.DEVNULL,
                                            stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        except Exception as e:
            return {"ok": False, "error": f"Could not start Claude: {e}"}
        EXEC["started"] = datetime.now().strftime("%H:%M:%S")
        EXEC["log"] = str(folder / "_claude.log")
        EXEC["target"] = target
        return {"ok": True}


def stop():
    with LOCK:
        proc = EXEC["proc"]
        if proc is not None and proc.poll() is None:
            proc.terminate()
            return {"ok": True}
        return {"ok": False, "error": "No analysis is running."}


def log_tail(day, n=25):
    p = MATCHES / day / "_claude.log"
    if not p.exists():
        return ""
    return "\n".join(read(p).strip().splitlines()[-n:])


def state(day):
    d = _state(day)
    proc = EXEC["proc"]
    running = proc is not None and proc.poll() is None
    d["execution"] = {
        "running": running,
        "started": EXEC["started"],
        "target": EXEC["target"],
        "code": None if (proc is None or running) else proc.returncode,
        "log": log_tail(day),
    }
    if running:
        d["started"] = True
    options = []
    jf = MATCHES / day / "fixtures.json"
    if jf.exists():
        try:
            for m in json.loads(read(jf)):
                options.append({"title": f'{m.get("home", "?")} vs {m.get("away", "?")}',
                                "time": (m.get("kickoff_utc") or "")[11:16], "iso": m.get("kickoff_utc") or "", "league": m.get("league", "")})
        except Exception:
            pass
    d["options"] = options
    return d


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, ctype, body):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", HTML.read_bytes())
        elif u.path == "/api/state":
            day = (q.get("date") or [""])[0]
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
                day = date.today().isoformat()
            self._send(200, "application/json; charset=utf-8", json.dumps(state(day), ensure_ascii=False))
        elif u.path.startswith("/avatars/"):
            name = Path(u.path).name
            f = HERE / "avatars" / name
            ctype = {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}.get(f.suffix.lower())
            if ctype and f.is_file():
                self._send(200, ctype, f.read_bytes())
            else:
                self._send(404, "text/plain; charset=utf-8", "Not found")
        elif u.path == "/api/ledger":
            bets = ledger.demo_bets() if (q.get("demo") or [""])[0] == "1" else ledger.load_bets()
            self._send(200, "application/json; charset=utf-8", json.dumps(ledger.summarize(bets), ensure_ascii=False))
        elif u.path == "/api/file":
            rel = (q.get("path") or [""])[0]
            try:
                p = (MATCHES / rel).resolve()
                p.relative_to(MATCHES.resolve())
                ok = p.is_file() and p.suffix in (".md", ".json")
            except Exception:
                ok = False
            if ok:
                self._send(200, "text/plain; charset=utf-8", p.read_text(encoding="utf-8"))
            else:
                self._send(404, "text/plain; charset=utf-8", "File not found")
        else:
            self._send(404, "text/plain; charset=utf-8", "Not found")

    def do_POST(self):
        # Only accept requests made by the page itself (stops other sites from starting Claude).
        host = (self.headers.get("Host") or "").split(":")[0]
        origin = self.headers.get("Origin") or ""
        if host not in ("localhost", "127.0.0.1") or self.headers.get("X-Room") != "1" or (
                origin and urlparse(origin).hostname not in ("localhost", "127.0.0.1")):
            self._send(403, "application/json; charset=utf-8", json.dumps({"ok": False, "error": "Request refused."}))
            return
        size = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(size) or b"{}") if size else {}
        except Exception:
            body = {}
        path = urlparse(self.path).path
        if path == "/api/start":
            res = start(str(body.get("target") or ""))
        elif path == "/api/settle":
            res = start(str(body.get("target") or ""), "/settle")
        elif path == "/api/placed":
            res = {"ok": ledger.set_placed(str(body.get("id") or ""), bool(body.get("placed")))}
        elif path == "/api/stop":
            res = stop()
        else:
            res = {"ok": False, "error": "Not found"}
        self._send(200, "application/json; charset=utf-8", json.dumps(res, ensure_ascii=False))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    MATCHES.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://localhost:{port}"
    print(f"Analysis Room running at {url}  (Ctrl+C to stop)")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
