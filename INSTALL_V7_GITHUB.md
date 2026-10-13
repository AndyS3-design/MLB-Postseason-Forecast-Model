# MLB Forecast Lab V7 — game-time + longer-history patch

This patch is for your existing public repository:
`AndyS3-design/MLB_Backtest_Expanded_2026_Postseason_Markets`, default branch `master`.

**What was broken in Run #2:** the GitHub job completed the model/data refresh but failed on `git push` with `master -> master (fetch first)`. The push from another simultaneous run moved the branch. This patch stops `push` events from retriggering workflows, serializes jobs, and pulls/rebases before pushing. It does **not** force-push or overwrite frozen forecasts.

## Recommended setup (GitHub Desktop)

1. Download and unzip the V7 PATCH archive. It contains only updated project files, not your data and saved forecast history.
2. Open GitHub Desktop and clone `AndyS3-design/MLB_Backtest_Expanded_2026_Postseason_Markets` if it isn't already cloned; select **master**.
3. Open the downloaded patch folder alongside the cloned repository folder.
4. Copy the entire `.github` folder and `MLB_Forecast_Lab_Cloud_Automation_COMPLETE` folder **from the patch folder into the cloned repository root**. Approve **Merge folders / Replace matching files**, but do not delete either existing folder. The patch contains only modified code and site template, so the original `data/`, `outputs/`, and `cloud_records/` are preserved.
5. Back in GitHub Desktop, review the changed files, commit `Upgrade cloud MLB forecasts to game-time V7`, and click **Push origin**.
6. On GitHub select **Actions → MLB Forecast Lab — game-time forecasts → Run workflow → master**. Wait for check → forecasts → deploy (only when the model job is required). This first manual run attempts to fetch 2016–2022 Retrosheet archives and refresh results; allow it to complete.
7. In Settings → Pages, confirm **Source: GitHub Actions**. The page URL stays the same and will show more saved forecasts and final results after successful deployments.

## Schedule and limits

- Lightweight schedule gate every **5 minutes**. The gate only runs the full model when a game is **16–31 minutes before first pitch**. The model worker independently accepts only **8–30 minutes** before first pitch; successful forecasts will usually be around 20 minutes before, but start delays and GitHub queueing mean there is no exact-time guarantee.
- Maintenance automatically runs daily at **11:17 UTC** to update past MLB results, obtain historical details, and refresh the website. On days with no games, the website can still refresh from maintenance.
- **Do not overwrite past frozen prediction files**. A prior game recorded two hours early remains an early prediction and can be analyzed as such; V7 changes the timing of *new* forecasts.
- For 2026 forecasting, the model is designed to load game logs for 2016–2025. On the first manual/full run, it tries to download missing older archives from Retrosheet. If it cannot, it continues with the actually available years and labels the coverage explicitly. `advanced_pitching_details.csv` remains limited by whichever years are imported; ten years of team-game logs does not imply ten years of advanced pitcher data.
- Old years receive **recency weights with a 3-year half-life**. The coefficients are selected on 2024 games. Ten-year data may or may not improve prediction accuracy. There are no sportsbook odds or prediction market inputs.
- `python -m cloud.compare_history` retrospectively compares run errors on 2025 games without training on those 2025 results. Because 2025 was already consulted during development, this is research validation, **not an untouched test**. New, saved 2026+ forecasts remain necessary.

## Where to see the training years

After the first manual run and website deployment, open a new forecast → **Model audit → Show pitcher adjustments, data quality and limitations**. It will report the actual regular-season training coverage (e.g., `10 seasons: 2016–2025`, or missing seasons).

## Diagnostic commands (optional, in the nested Cloud Edition folder)

```
py -m unittest cloud.test_cloud cloud.test_v7 -q
py -m cloud.compare_history
py -m cloud.worker run --offline
```

Run `py -m cloud.compare_history` *after* the seven older archives are downloaded; it creates `outputs/v7_history_benchmark.json`. The GitHub workflow does not automatically use the benchmark to claim improved accuracy.

## GitHub failure troubleshooting

- A **green check** means that run succeeded. The Pages URL updates only after successful **deploy**.
- If GitHub skips `forecasts` and `deploy` during a five-minute check, that's normal: no game is close enough.
- If forecast job fails, open its failed step log. For `master -> master (fetch first)` the new workflow retries safely; no force-push.
- Ensure **Settings → Actions → General → Workflow permissions** allows writing repository contents. The existing runs already showed that the bot can commit, so this is not normally necessary.
