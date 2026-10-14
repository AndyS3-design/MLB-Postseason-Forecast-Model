# 2026 MLB Postseason — Retrospective Forecast Audit

**Research replay, not independent validation.** 2026 outcomes have influenced earlier model development. Starter names and lineups verified only after games are excluded.

Games: **28**; model training: **2016–2025**; 12,000 simulations per game. Before **2026-10-13** (exclusive).

| Metric | With playoff context | Without playoff context |
|---|---:|---:|
| Winner accuracy | 64.3% | 64.3% |
| Winner Brier (lower better) | 0.24192 | 0.24288 |
| Under 6.5 Brier (lower better) | 0.23189 | 0.23430 |
| Total MAE (lower better) | 2.713 | 3.002 |
| Mean projected total | 8.27 | 8.98 |
| Actual mean total | 7.04 | 7.04 |

**Elo winner accuracy:** 60.7%; **Elo Brier:** 0.23854; **50/50 Brier:** 0.25000.

## Per-game results

| Date | Game | Actual away–home | Mean total forecast | Home win chance | Winner correct? |
|---|---|---:|---:|---:|:---:|
| 2026-09-29 | PHI @ ATL | 3–5 | 8.53 | 50.4% | Yes |
| 2026-09-29 | CHA @ HOU | 6–3 | 8.27 | 51.9% | No |
| 2026-09-29 | BOS @ NYA | 0–9 | 8.33 | 51.3% | Yes |
| 2026-09-29 | CHN @ SDN | 0–8 | 8.30 | 49.5% | No |
| 2026-09-30 | PHI @ ATL | 4–3 | 8.41 | 51.7% | No |
| 2026-09-30 | CHA @ HOU | 7–3 | 8.19 | 51.5% | No |
| 2026-09-30 | BOS @ NYA | 2–9 | 8.12 | 51.3% | Yes |
| 2026-09-30 | CHN @ SDN | 1–4 | 8.33 | 50.8% | Yes |
| 2026-10-01 | PHI @ ATL | 2–6 | 8.35 | 50.6% | Yes |
| 2026-10-03 | CHA @ CLE | 3–0 | 8.51 | 55.3% | No |
| 2026-10-03 | ATL @ LAN | 3–5 | 8.41 | 58.8% | Yes |
| 2026-10-03 | NYA @ TBA | 0–1 | 8.36 | 52.8% | Yes |
| 2026-10-03 | SDN @ MIL | 2–3 | 8.46 | 58.6% | Yes |
| 2026-10-04 | SDN @ MIL | 3–4 | 8.26 | 57.0% | Yes |
| 2026-10-04 | ATL @ LAN | 3–2 | 8.07 | 56.6% | No |
| 2026-10-05 | CHA @ CLE | 4–3 | 8.30 | 52.5% | No |
| 2026-10-05 | NYA @ TBA | 2–5 | 8.13 | 51.9% | Yes |
| 2026-10-06 | LAN @ ATL | 3–1 | 8.29 | 45.4% | Yes |
| 2026-10-06 | MIL @ SDN | 3–4 | 8.26 | 45.1% | No |
| 2026-10-07 | CLE @ CHA | 9–3 | 8.28 | 50.4% | No |
| 2026-10-07 | LAN @ ATL | 4–1 | 8.14 | 46.2% | Yes |
| 2026-10-07 | TBA @ NYA | 4–3 | 8.21 | 49.1% | Yes |
| 2026-10-07 | MIL @ SDN | 3–1 | 8.21 | 44.8% | Yes |
| 2026-10-08 | CLE @ CHA | 9–5 | 8.31 | 49.7% | Yes |
| 2026-10-10 | CHA @ CLE | 0–2 | 8.35 | 54.4% | Yes |
| 2026-10-11 | LAN @ MIL | 1–2 | 8.34 | 53.8% | Yes |
| 2026-10-12 | LAN @ MIL | 4–7 | 7.68 | 53.7% | Yes |
| 2026-10-12 | CLE @ TBA | 7–3 | 8.10 | 57.4% | No |

## Limitations

- 2026 games were seen during model development: this is retrospective research, not independent validation.
- No verified archived pregame starter identities or lineups exist for these games; strict replay omits them.
- The optional 2026 postseason scoring snapshot shares some 2026 outcomes and is applied only starting October 12.
- Do not optimize model coefficients on this sample and then call its error a holdout.
- Prospective claims require timestamped first-pitch-locked forecasts, many settled games, and uncertainty intervals.

Full probabilities and proof-of-cutoff fields are in the companion CSV.
