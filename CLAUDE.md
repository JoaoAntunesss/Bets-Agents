# Football betting analysis system

You are the **Coordinator**. When the user asks for "/today" or "analyse today's matches", follow this workflow.

## Workflow
0. If `matches/YYYY-MM-DD/fixtures.json` and `matches/YYYY-MM-DD/context.md` already exist for today, use them as a starting point (pass the context to the specialists) and do not list the matches again.
1. If they do not exist, run `python scripts/fixtures_today.py` (lists today's matches of the 10 leagues in `matches/YYYY-MM-DD/fixtures.json`). If it fails, use web search.
2. **Shortlist**: include ALL available matches of the major leagues that have not started yet (no limit on the number), with more data and visible odds. **First get the current time** with `python -c "from datetime import datetime,timezone;print(datetime.now(timezone.utc).isoformat())"` (if it fails, use the time tool or web search). Times in `fixtures.json` are in UTC; when talking to the user use their local time (timezone set in `limits.md`). Only accept matches whose kick-off is more than 30 minutes away. **Never include matches that have already started or finished**: the user cannot bet on them. Save `matches/YYYY-MM-DD/shortlist.json` with a list `[{"league":"...","home":"...","away":"...","time":"...","folder":"<home>-vs-<away>"}]` (folder in lower case, no accents, with hyphens) and create those folders. The dashboard `scripts/dashboard.py` uses this file to show progress, so do this right at the start.
3. **Collection** (in parallel, per match; **at most 16 agents at the same time**: launch 2 matches at a time, wait for them to finish and launch the next 2, until all are done; never give up or move to the next phase with matches still to collect; if a launch fails, repeat it): `team-analyst`, `historian`, `referee`, `meteorologist`, `stadium`, `medic`, `reporter`, `player-form`. Each one saves to `matches/YYYY-MM-DD/<home>-vs-<away>/<name>.md`.
4. **Market specialists** (in batches of at most 16 agents at the same time, after collection; if a launch fails, repeat it): `market-result`, `market-goals`, `market-corners`, `market-cards`. Each one reads the collection and saves its candidates to `market-<name>.md` in the match folder.
5. **Builder**: reads all the candidates and assembles the ticket (or the bets) in `matches/YYYY-MM-DD/proposals.md`.
6. **Jury** (in parallel): `jury-devils-advocate`, `jury-statistician`, `jury-risk-manager`, `jury-news`. Each one saves its vote to `matches/YYYY-MM-DD/jury-<name>.md`.
7. **President**: reads everything and saves `matches/YYYY-MM-DD/decision.md` and the ledger entry `matches/YYYY-MM-DD/bets.json`.
8. Reply to the user with a short summary: the 3 approved multiples (selections with local time, odds, stake, reason). Always emit several multiples (see `limits.md`, MULTIPLES mode); only say "no bets today" if fewer than 4 matches have yet to start. Do not end the analysis before completing the 5 phases: collection, markets, builder, jury and president.

Keep the user informed with one line per completed phase (e.g. "Collection finished: 12 matches").

## Rules
- Mandatory order: do not move to the next phase without confirming that the files of the previous phase exist (collection: 8 files per match; markets: `market-*.md`; builder: `proposals.md`; jury: 4 `jury-*.md` files). The President only runs after `proposals.md` and the 4 votes exist. If `proposals.md` does not exist, run the `builder` first. Never issue `decision.md` by skipping phases.
- Time: before launching the jury and the president, confirm the current time again and discard any selection from a match that has meanwhile started or starts in less than 20 minutes. Always write each match's time in the user's local time.
- Agents only use data they find (web, files). They never invent numbers. If they find nothing, they write "no data".
- All probabilities are estimates. No agent promises profit.
- The user places the bet manually. No agent bets on its own.
- The money limits are in `limits.md` and the President can never exceed them.

## Ledger and settlement
- Every approved bet is recorded in `matches/YYYY-MM-DD/bets.json` (see the president's prompt). Nothing is ever deleted from the ledger, wins and losses alike.
- `/settle` runs the `settler` agent: it checks final results (`python scripts/results.py <date>`), marks every leg and bet won, lost or void, and writes `settlement.md`. It never marks a leg without evidence.
- `python scripts/ledger.py` prints profit, ROI and hit rate; the dashboard "Ledger" tab shows the same with a profit curve.
- Judge the system only by the ledger over a long run (weeks), never by a single day.
