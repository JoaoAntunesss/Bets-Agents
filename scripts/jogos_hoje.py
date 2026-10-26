#!/usr/bin/env python3
"""Lista os jogos de hoje das 10 ligas (ESPN, sem chave de API).

Uso: python scripts/jogos_hoje.py [AAAA-MM-DD]
Grava em jogos/AAAA-MM-DD/jogos.json e imprime um resumo.
"""
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

LIGAS = {
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


def buscar(codigo, dia):
    url = (
        f"https://site.api.espn.com/apis/site/v2/sports/soccer/{codigo}/scoreboard"
        f"?dates={dia.replace('-', '')}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def main():
    dia = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    jogos = []
    for codigo, nome in LIGAS.items():
        try:
            dados = buscar(codigo, dia)
        except Exception as e:
            print(f"[aviso] {nome}: {e}", file=sys.stderr)
            continue
        for ev in dados.get("events", []):
            comp = ev["competitions"][0]
            equipas = {c["homeAway"]: c["team"]["displayName"] for c in comp["competitors"]}
            jogos.append(
                {
                    "liga": nome,
                    "hora_utc": ev.get("date"),
                    "casa": equipas.get("home"),
                    "fora": equipas.get("away"),
                    "estado": ev["status"]["type"]["description"],
                    "estadio": comp.get("venue", {}).get("fullName"),
                    "cidade": comp.get("venue", {}).get("address", {}).get("city"),
                }
            )
    pasta = Path("jogos") / dia
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "jogos.json").write_text(json.dumps(jogos, ensure_ascii=False, indent=2))
    print(f"{len(jogos)} jogos em {dia}")
    for j in sorted(jogos, key=lambda x: x["hora_utc"] or ""):
        print(f'{(j["hora_utc"] or "")[11:16]} UTC | {j["liga"]:<14} | {j["casa"]} vs {j["fora"]} ({j["estado"]})')


if __name__ == "__main__":
    main()
