#!/usr/bin/env python3
"""Sala de Análise: painel local que mostra os agentes a trabalhar em tempo real.

Uso:  python scripts/dashboard.py [porta]
Abre http://localhost:8765 (noutro terminal, enquanto corres /dia no Claude Code).

O estado é calculado pelos ficheiros que os agentes vão gravando em jogos/AAAA-MM-DD/.
Não precisa de internet nem de bibliotecas extra.
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

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
JOGOS = RAIZ / "jogos"
HTML = AQUI / "dashboard.html"

# (ficheiro sem .md, nome no cartão, descrição)
FASES = [
    {
        "id": "recolha", "nome": "Recolha", "modo": "jogo",
        "agentes": [
            ("analista-equipas", "Equipas", "Forma e estilo de jogo"),
            ("historiador", "Historiador", "Confrontos diretos"),
            ("arbitro", "Árbitro", "Cartões, faltas, penáltis"),
            ("meteorologo", "Meteorologista", "Tempo, vento e relvado"),
            ("estadio", "Estádio", "Fator casa e viagem"),
            ("medico", "Médico", "Lesões, suspensões, dúvidas"),
            ("jornalista", "Repórter", "Notícias, pressão e balneário"),
            ("forma-jogadores", "Forma", "Momento dos jogadores"),
        ],
    },
    {
        "id": "mercados", "nome": "Especialistas", "modo": "jogo",
        "agentes": [
            ("mercado-resultado", "Resultado", "1X2, dupla hipótese, handicap"),
            ("mercado-golos", "Golos", "Totais e ambas marcam"),
            ("mercado-cantos", "Cantos", "Cantos do jogo e por equipa"),
            ("mercado-cartoes", "Cartões", "Cartões do jogo"),
        ],
    },
    {
        "id": "construtor", "nome": "Construtor", "modo": "global",
        "agentes": [("propostas", "Construtor", "Monta as 3 múltiplas do dia")],
    },
    {
        "id": "juri", "nome": "Júri", "modo": "global",
        "agentes": [
            ("juri-advogado-diabo", "Advogado do diabo", "Procura o que pode falhar"),
            ("juri-estatistico", "Estatístico", "Confirma o valor real"),
            ("juri-gestor-risco", "Gestor de risco", "Limites e veto"),
            ("juri-noticias", "Notícias", "Última hora e onzes"),
        ],
    },
    {
        "id": "presidente", "nome": "Presidente", "modo": "global",
        "agentes": [("decisao", "Presidente", "Decisão final")],
    },
]

VOTOS = re.compile(r"\b(APROVAR|REJEITAR|REDUZIR STAKE|VETO|ESPERAR)\b")


def slugify(txt):
    import unicodedata
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", txt.lower()).strip("-")


def listar_jogos(pasta):
    jogos, vistos = [], set()
    triagem = pasta / "triagem.json"
    if triagem.exists():
        try:
            dados = json.loads(triagem.read_text(encoding="utf-8"))
        except Exception:
            dados = []
        for j in dados if isinstance(dados, list) else []:
            if not isinstance(j, dict):
                continue
            slug = j.get("pasta") or slugify(f'{j.get("casa", "")}-vs-{j.get("fora", "")}')
            if slug and slug not in vistos:
                vistos.add(slug)
                titulo = f'{j.get("casa", "?")} vs {j.get("fora", "?")}'
                jogos.append({"pasta": slug, "titulo": titulo, "liga": j.get("liga", "")})
    for d in sorted(p for p in pasta.iterdir() if p.is_dir()):
        if d.name not in vistos:
            vistos.add(d.name)
            jogos.append({"pasta": d.name, "titulo": d.name.replace("-vs-", " vs ").replace("-", " "), "liga": ""})
    return jogos


def ler(p):
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def _estado(dia):
    pasta = JOGOS / dia
    datas = sorted((p.name for p in JOGOS.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name)), reverse=True) if JOGOS.exists() else []
    base = {"data": dia, "datas": datas, "jogos": [], "fases": [], "iniciou": False, "eventos": [],
            "propostas": "", "decisao": "", "atualizado": datetime.now().strftime("%H:%M:%S")}
    if not pasta.exists():
        for f in FASES:
            base["fases"].append({"id": f["id"], "nome": f["nome"], "agentes": [
                {"id": a[0], "nome": a[1], "desc": a[2], "estado": "espera", "feitos": 0, "total": 0, "ficheiros": [], "votos": {}}
                for a in f["agentes"]]})
        return base

    jogos = listar_jogos(pasta)
    n = len(jogos)
    base["jogos"] = jogos
    base["iniciou"] = (pasta / "triagem.json").exists() or any(pasta.iterdir())
    anterior_completa = True
    for f in FASES:
        agentes, todos_feitos = [], True
        for fich, nome, desc in f["agentes"]:
            ficheiros, votos = [], {}
            if f["modo"] == "jogo":
                total = n
                for j in jogos:
                    fp = pasta / j["pasta"] / f"{fich}.md"
                    if fp.exists():
                        ficheiros.append({"rotulo": j["titulo"], "caminho": f'{dia}/{j["pasta"]}/{fich}.md', "t": fp.stat().st_mtime})
            else:
                total = 1
                if (pasta / f"{fich}.md").exists():
                    ficheiros.append({"rotulo": nome, "caminho": f"{dia}/{fich}.md", "t": (pasta / f"{fich}.md").stat().st_mtime})
                    if f["id"] == "juri":
                        for v in VOTOS.findall(ler(pasta / f"{fich}.md")):
                            votos[v] = votos.get(v, 0) + 1
            feitos = len(ficheiros)
            if total > 0 and feitos == total:
                est = "concluido"
            elif feitos > 0 or (anterior_completa and base["iniciou"]):
                est = "trabalhar"
            else:
                est = "espera"
            if est != "concluido":
                todos_feitos = False
            agentes.append({"id": fich, "nome": nome, "desc": desc, "estado": est,
                            "feitos": feitos, "total": total, "ficheiros": ficheiros, "votos": votos})
        anterior_completa = anterior_completa and todos_feitos
        base["fases"].append({"id": f["id"], "nome": f["nome"], "modo": f["modo"], "agentes": agentes})
    eventos = []
    for f in base["fases"]:
        for a in f["agentes"]:
            for fi in a["ficheiros"]:
                eventos.append({"t": fi["t"], "hora": datetime.fromtimestamp(fi["t"]).strftime("%H:%M:%S"),
                                "agente": a["nome"], "id": a["id"], "fase": f["id"],
                                "jogo": fi["rotulo"] if f["modo"] == "jogo" else ""})
    base["eventos"] = sorted(eventos, key=lambda e: e["t"], reverse=True)[:40]
    base["propostas"] = ler(pasta / "propostas.md")
    base["decisao"] = ler(pasta / "decisao.md")
    return base


# ---------- Executar o Claude a partir do painel ----------
PERMITIDAS = "WebSearch,WebFetch,Agent,Task,Read,Write,Edit,Glob,Grep,Bash(python *),Bash(python3 *)"
EXEC = {"proc": None, "inicio": None, "log": None, "alvo": ""}
LOCK = threading.Lock()


def achar_claude():
    c = shutil.which("claude")
    if c:
        return c
    for nome in ("claude.exe", "claude"):
        p = Path.home() / ".local" / "bin" / nome
        if p.exists():
            return str(p)
    return None


def iniciar(alvo):
    with LOCK:
        proc = EXEC["proc"]
        if proc is not None and proc.poll() is None:
            return {"ok": False, "erro": "Já está uma análise a correr."}
        exe = achar_claude()
        if not exe:
            return {"ok": False, "erro": "Não encontrei o Claude Code. Abre um PowerShell e confirma que consegues correr: claude --version"}
        dia = date.today().isoformat()
        pasta = JOGOS / dia
        pasta.mkdir(parents=True, exist_ok=True)
        alvo = re.sub(r"[^\w\s\-.,'À-ÿ]", "", alvo or "").strip()[:80]
        prompt = "/dia" + (f" {alvo}" if alvo else "")
        cmd = [exe, "-p", prompt, "--model", "sonnet", "--permission-mode", "acceptEdits",
               "--allowedTools", PERMITIDAS, "--permission-prompts", "none"]
        log = open(pasta / "_claude.log", "w", encoding="utf-8")
        flags = 0x08000000 if os.name == "nt" else 0  # sem janela extra no Windows
        try:
            EXEC["proc"] = subprocess.Popen(cmd, cwd=str(RAIZ), stdin=subprocess.DEVNULL,
                                            stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        except Exception as e:
            return {"ok": False, "erro": f"Não consegui arrancar o Claude: {e}"}
        EXEC["inicio"] = datetime.now().strftime("%H:%M:%S")
        EXEC["log"] = str(pasta / "_claude.log")
        EXEC["alvo"] = alvo
        return {"ok": True}


def parar():
    with LOCK:
        proc = EXEC["proc"]
        if proc is not None and proc.poll() is None:
            proc.terminate()
            return {"ok": True}
        return {"ok": False, "erro": "Não há nenhuma análise a correr."}


def cauda_log(dia, n=25):
    p = JOGOS / dia / "_claude.log"
    if not p.exists():
        return ""
    return "\n".join(ler(p).strip().splitlines()[-n:])


def estado(dia):
    d = _estado(dia)
    proc = EXEC["proc"]
    a_correr = proc is not None and proc.poll() is None
    d["execucao"] = {
        "a_correr": a_correr,
        "inicio": EXEC["inicio"],
        "alvo": EXEC["alvo"],
        "codigo": None if (proc is None or a_correr) else proc.returncode,
        "log": cauda_log(dia),
    }
    if a_correr:
        d["iniciou"] = True
    opcoes = []
    jf = JOGOS / dia / "jogos.json"
    if jf.exists():
        try:
            for j in json.loads(ler(jf)):
                opcoes.append({"titulo": f'{j.get("casa", "?")} vs {j.get("fora", "?")}',
                               "hora": (j.get("hora_utc") or "")[11:16], "iso": j.get("hora_utc") or "", "liga": j.get("liga", "")})
        except Exception:
            pass
    d["opcoes"] = opcoes
    return d


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _enviar(self, codigo, tipo, corpo):
        dados = corpo if isinstance(corpo, bytes) else corpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            self._enviar(200, "text/html; charset=utf-8", HTML.read_bytes())
        elif u.path == "/api/estado":
            dia = (q.get("data") or [""])[0]
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", dia):
                dia = date.today().isoformat()
            self._enviar(200, "application/json; charset=utf-8", json.dumps(estado(dia), ensure_ascii=False))
        elif u.path == "/api/ficheiro":
            rel = (q.get("caminho") or [""])[0]
            try:
                p = (JOGOS / rel).resolve()
                p.relative_to(JOGOS.resolve())
                ok = p.is_file() and p.suffix in (".md", ".json")
            except Exception:
                ok = False
            if ok:
                self._enviar(200, "text/plain; charset=utf-8", p.read_text(encoding="utf-8"))
            else:
                self._enviar(404, "text/plain; charset=utf-8", "Ficheiro não encontrado")
        else:
            self._enviar(404, "text/plain; charset=utf-8", "Não encontrado")

    def do_POST(self):
        # Só aceita pedidos feitos pela própria página (evita que outros sites iniciem o Claude).
        host = (self.headers.get("Host") or "").split(":")[0]
        origem = self.headers.get("Origin") or ""
        if host not in ("localhost", "127.0.0.1") or self.headers.get("X-Sala") != "1" or (
                origem and urlparse(origem).hostname not in ("localhost", "127.0.0.1")):
            self._enviar(403, "application/json; charset=utf-8", json.dumps({"ok": False, "erro": "Pedido recusado."}))
            return
        tam = int(self.headers.get("Content-Length") or 0)
        try:
            corpo = json.loads(self.rfile.read(tam) or b"{}") if tam else {}
        except Exception:
            corpo = {}
        caminho = urlparse(self.path).path
        if caminho == "/api/iniciar":
            res = iniciar(str(corpo.get("alvo") or ""))
        elif caminho == "/api/parar":
            res = parar()
        else:
            res = {"ok": False, "erro": "Não encontrado"}
        self._enviar(200, "application/json; charset=utf-8", json.dumps(res, ensure_ascii=False))


def main():
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    JOGOS.mkdir(exist_ok=True)
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), Handler)
    url = f"http://localhost:{porta}"
    print(f"Sala de Análise a correr em {url}  (Ctrl+C para parar)")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nTerminado.")


if __name__ == "__main__":
    main()
