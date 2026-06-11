# Matchup Board

A week-at-a-glance board of MLB matchups: every game for the current week
(played and upcoming), each showing the two teams, the score (final, live, or
— later — a model projection), first-pitch time, and the starting pitchers.

This is **step 1** of a larger project: data ingestion plus the main display.
It deliberately ships with no prediction model yet — upcoming games read
"projection pending." The seam where the model plugs in is already in place
(`mlbboard/predictions.py`), so steps 3–4 (a GBDT baseline, then a DNN) can
fill in projected scores without touching the display.

## Data source

Everything comes from the **MLB Stats API** (`https://statsapi.mlb.com`) — the
same undocumented endpoint that powers MLB.com. A single `/schedule` request,
with `team`, `linescore`, and `probablePitcher` hydrated, returns teams,
scores, status, game time, and probable starters for the whole week.

> The MLB Stats API is unofficial and MLB frames its use as educational /
> non-commercial. Review their terms before building anything you intend to
> ship commercially.

Statcast (via `pybaseball`) is **not** used here — that's the historical
pitch-level data for training the model in later steps, a separate pipeline.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py            # then open http://127.0.0.1:5000
```

Run the tests (no network required — they parse a saved sample payload):

```bash
python -m pytest -q
```

## Configuration

Read from the environment:

| Variable              | Default              | Purpose                                  |
|-----------------------|----------------------|------------------------------------------|
| `MLB_BOARD_TZ`        | `America/New_York`   | Timezone for game times and "today"      |
| `MLB_BOARD_CACHE_TTL` | `60`                 | Seconds to cache a schedule response     |

## Routes

| Route         | Returns                                             |
|---------------|-----------------------------------------------------|
| `/`           | The HTML board for the current week                 |
| `/api/games`  | The same data as JSON (handy for the next phases)   |
| `/healthz`    | `{"status": "ok"}`                                  |

## Project layout

```
mlbboard/
  __init__.py      app factory (create_app)
  mlb_client.py    MLB Stats API client: HTTP, retries, TTL cache
  models.py        Team / Pitcher / Game / GameDay + parsing
  dates.py         current-week and rolling-window helpers
  predictions.py   Predictor protocol + NullPredictor (the model seam)
  views.py         routes + presenter (Game -> view-model dicts)
  templates/index.html
  static/style.css
tests/
  test_parsing.py  parser tests over a real-shaped payload
  sample_schedule.json
run.py             local dev entrypoint
```

## How the data flows

1. `views.index` asks `MLBClient.get_schedule(start, end)` for the current week.
2. The client hits `/schedule`, then `parse_schedule` turns the JSON into
   `GameDay` → `Game` objects (status bucketed into final / live / upcoming /
   other; scores, records, probable pitchers, venue, inning state extracted).
3. `build_board` formats those into plain dicts (clock times, status labels,
   winner highlighting), applying the registered `Predictor` to upcoming games.
4. The template renders the board; `/api/games` returns the same view-models.

## What's next

- **Step 2** — establish a Marcel baseline and an evaluation harness.
- **Step 3** — a GBDT plate-appearance model + Monte Carlo game simulator.
  Wrap it as a `Predictor` and register it via the `PREDICTOR` config key; the
  board will start showing projected scores on upcoming games automatically.
- **Step 4** — the embedding + sequence DNN, measured against the GBDT.
- For past games, surface a model-vs-actual evaluation on each card.
