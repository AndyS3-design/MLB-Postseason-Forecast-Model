# Postseason runs: 2020–2026 official final-score study

Research only; 2026 games are **not** an untouched holdout. See JSON for all grid settings and per-year MAE.

| Year | Games | Postseason combined runs/game | Regular combined runs/game | Post/reg |
|---|---:|---:|---:|---:|
| 2020 | 53 | 8.792 | 9.292 | 0.946 |
| 2021 | 37 | 8.568 | 9.061 | 0.946 |
| 2022 | 40 | 7.325 | 8.567 | 0.855 |
| 2023 | 41 | 8.195 | 9.231 | 0.888 |
| 2024 | 43 | 8.419 | 8.787 | 0.958 |
| 2025 | 47 | 8.021 | 8.895 | 0.902 |
| 2026 | 29 | 6.931 | 8.962 | 0.773 |

Selected candidate on 2022–2025 game-level MAE with day-exclusive running data: {"prior_equivalent_games": 1000000000, "strength": 1.2, "n": 171, "pooled_mae": 3.2252335343046514}

2026 retrospective diagnostics (never used for selection):

| Candidate | Games | MAE per team-run | Mean factor | Next factor |
|---|---:|---:|---:|---:|
| strength=1.2, prior-equiv=1000000000 | 29 | 2.619 | 0.901 | 0.901 |
| strength=0.8, prior-equiv=1000000000 | 29 | 2.752 | 0.934 | 0.934 |
| strength=0.8, prior-equiv=20 | 29 | 2.641 | 0.903 | 0.866 |
| strength=1.0, prior-equiv=30 | 29 | 2.577 | 0.886 | 0.847 |

Do not scale past frozen forecasts or silently label this aggregate study a full matchup-model backtest.
