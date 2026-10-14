# V13 — Verified 2020–2026 postseason scoring adjustment

_Research updated October 14, 2026. New production scoring rule is a historically informed experimental adjustment, **not** proof of superior prospective forecasting._

## Reason for the change

The V8 historical replay of the 2026 postseason (28 games through October 12) projected **8.269 combined runs** per game, against **7.036 actual**, and its postseason run MAE was worse than a simple historical 2025 postseason average. The old multiplier was a manually chosen 2022–2025 strength of 0.80 with a published partial-2026 aggregate blended at 30%. It had never been tuned on a full set of prior-season official individual final scores.

The October 14, 2026 Milwaukee–Los Angeles early preview, saved before this change, estimated **7.816 combined runs** and showed a representative 5–3 score. It is frozen evidence and **will not be rewritten**.

## Verified official postseason final-score data

Season | Completed games | Actual combined runs/game | Combined regular-season runs/game
---|---:|---:|---:
2020 | 53 | 8.792 | 9.292
2021 | 37 | 8.568 | 9.061
2022 | 40 | 7.325 | 8.567
2023 | 41 | 8.195 | 9.231
2024 | 43 | 8.419 | 8.787
2025 | 47 | 8.021 | 8.895
2026 through October 13 | 29 | **6.931** | 8.962

The prior **261 official completed postseason games** are stored in `data/official_postseason_2020_2025.csv`, with stable MLB game IDs. 2026 final-game history is read from the cloud's separately refreshed local official MLB CSV. The main research reproduction files are `outputs/v13_postseason/official_postseason_2020_2026.csv`, `comparison.json` and `REPORT.md`. MLB schedule/linescore APIs supply postseason finals; Retrosheet regular-season game logs and the local official 2026 regular CSV supply denominators. Repeated game IDs are checked, and canceled/live games are excluded.

### Calibration without game-day leakage

Each forecast calculates a historical **combined scoring ratio** from completed postseason seasons strictly earlier than the target season, using up to the previous **six seasons**, weighted by observed numbers of completed games. Its current 2026 component includes official **final games from dates strictly before the predicted game's ET calendar date**. Results on the predicted date, later games, revised outcomes and the actual final are never passed into that game's forecast.

The historical ratio is combined with the current season's *previously completed* postoperative ratio using a fixed, conservative prior of **80 equivalent games**:

```text
current_weight = previous_completed_postseason_games / (previous_completed_postseason_games + 80)
ratio = historical_ratio * (1 - current_weight) + current_year_ratio * current_weight
factor = 1 + 1.20 * (ratio - 1)
new_home_run_rate = old_frozen_model_home_run_rate * factor
new_away_run_rate = old_frozen_model_away_run_rate * factor
```

The multiplier is fed to the original complete baseball score simulator. Pitcher, lineup, bullpen and game-context data continue to be evaluated as before; no fake runs or exact final scores are inserted. The 2020–2025 archive is used only as a scoring prior; it is **not** added as if it were regular-season training data in the original 2016–2025 Poisson fit.

### Chronological model selection, not in-sample 2026 fitting

Using only historical individual completed games in **2022–2025 (171 matchups)**, the study compared multiple shrinkage strengths and prior-equivalent sizes. Every evaluated day's in-season feature sample included games from **strictly earlier days only**. The lowest tested pooled absolute error for a simple prior-based league scoring forecast was **3.2252 combined runs** with strength 1.20 and effectively no current-year adaptation.

The deployed choice, **strength 1.20 with an 80-game equivalent prior**, scored **3.2274 combined-run MAE** on those same 171 games: only **0.0022 runs/game** above the fixed model. This near-tie supports retaining conservative adaptation. These figures test **the postseason context layer alone against league-run baselines**, not the full game-specific run-model error or winner accuracy, and the parameter selection set is *not* an untouched test set.

The 2026 games were excluded from selecting the coefficient and smoothing parameter; they are disclosed as a small, previously inspected retrospective diagnostic. The 29 already-completed 2026 playoff games correspond to an **approximately 0.855** next-game postseason multiplier under the fixed rule; the old live October 14 preliminary used **0.890**. This does not guarantee a total below any threshold.

The real current-matchup model smoke test, using October 14 earlier-date historical features but without a live late lineup snapshot, returned approximately **7.627 expected combined runs** using the new adjustment. The separately timestamped genuine preliminary remains unchanged. The actual future final may differ because of later official pitcher/lineup information, scheduling, and simulation.

## Better projected-score display

Previously, the website deliberately chose an exact score close to the **rounded expected combined total**, which could make the integer score seem artificially anchored to 8 despite the distribution having a lower modal outcome. From V13 onward it displays the **most frequent exact simulated score among outcomes that match the model's favored winner**, while also showing the entire-game *mean expected total* separately. The exact-score percentage remains visible and is ordinarily very small. This display change **does not** change model simulations, probabilities, or expected runs; it avoids converting the average directly into a supposed exact result.

## Safe deployment and future assessment

- Existing early previews, original finals and authorized revisions are never overwritten.
- The new rule is versioned as `13.0.0-recent-postseason-scoring` and applied only to new forecasts.
- A new `historic_postseason_only` timestamped research challenger omits current-season adaptation; primary original, no-adaptation and neutral-postseason scorings can be compared on **the same future officially settled games**.
- Unit tests check use of the full archive, strict earlier-day cutoffs, same-day exclusions, missing-data behavior, scoreline simulation invariants and the full original/preview integrity suite.
- The 2026 data have previously influenced research decisions in this project. Even though this particular calibration grid excluded them, the current postseason should **not** be advertised as a pristine untouched validation sample. Further genuinely prospective games and error uncertainty intervals are needed.

These forecasts are experimental research, not financial advice, betting recommendations, or guarantees.
