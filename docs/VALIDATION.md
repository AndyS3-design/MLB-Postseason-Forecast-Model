# Validation, leakage prevention and limitations

## Primary goal

Assess forecasts that were **actually saved before first pitch**, rather than adjusting completed-game replays until they match the final score.

A football/soccer-style score graphic or a high simulation count cannot validate model accuracy. The main question is whether the resulting probabilities and run expectations outperform appropriate baseball-only baselines on **future unseen games**.

## Dataset separation

| Period | Role | Qualification |
|---|---|---|
| 2016–2023 | Historical fit / feature histories | Older seasons receive lower weights |
| 2024 | Model-selection validation | Used to choose regression settings and an optional starter adjustment |
| 2025 | Included in 2026 final fitting; retrospective comparisons | **Not** an untouched validation set; earlier development used these outcomes |
| 2026 onward, new saved forecasts | Prospective evaluation | Count only genuine timestamps before the corresponding first pitch; previous 2026 analyses have also informed development |

Only the earliest original forecast for each game is counted in the project's **primary** prospective metric report. Explicitly requested pregame revisions are separate records for comparison, not additional independent games.

## Metrics to publish as the sample grows

- **Winner accuracy:** Percentage of settled games for which the favorite won. Interpretation requires a comparable baseline.
- **Winner Brier score:** Mean `(p - y)^2` for home-win probability `p` and actual home-win indicator `y`; lower is better.
- **Elo Brier score:** Evaluated on the same games to give a baseball-only baseline.
- **Team-run mean absolute error:** Average absolute difference between projected and actual runs for each team; lower is better.
- **Total-run absolute error:** Absolute difference between expected combined runs and actual combined runs.
- **Under-6.5 Brier score:** Binary probability metric for six or fewer combined runs; lower is better.

As the sample grows, evaluate reliability diagrams, forecast calibration by probability bucket, regular-season versus postseason segments, starter-history coverage, and uncertainty intervals. Record how many games were settled, not just percentages.

## Leakage-control checklist

- [x] Reject in-progress/final games for creation of new original forecasts.
- [x] Filter rolling features to strictly earlier calendar dates.
- [x] Backfill starting pitchers from **earlier verified** MLB games only.
- [x] Stamp each original or authorized revision with an actual UTC creation time and game identity.
- [x] Preserve original forecast fields when official finals are later attached.
- [x] Avoid counting revisions as additional independent games in the primary metrics.
- [ ] Accumulate a meaningful prospective sample and report uncertainty.
- [ ] Independently audit edge cases: postponed/rescheduled games, changed announced starters, doubleheaders and official postgame corrections.

The implemented checks are valuable safeguards, not a proof that the pipeline is free from every possible leakage issue.

## Example of an input-quality change (not accuracy proof)

For Cleveland at Tampa Bay on October 13, 2026, the repository holds an original pregame forecast and a later explicitly labeled pregame revision:

| Detail | Original | Updated pregame |
|---|---:|---:|
| Illustrative score (CLE–TBA) | 3–5 | 3–4 |
| Mean total runs | ~8.05 | ~7.38 |
| Home win probability | ~56.8% | ~57.5% |
| Verified prior starts: CLE pitcher | 2 | 8 |
| Verified prior starts: TBA pitcher | 1 | 8 |
| Training coverage | Earlier configuration | 2016–2025 reported |

This establishes a **data coverage and forecasting pipeline demonstration**, not evidence that the revised projection is closer to the actual score.

## Reporting rules

Do not claim any profitable strategy, production-grade reliability guarantee, fixed winner accuracy, demonstrated model superiority or scientifically established causal effect until the relevant independent data and method support it. Label exploratory backtests as exploratory; document model changes that follow viewing results; compare like-for-like samples and avoid selecting only games that fit a preferred narrative.

## Verified V8 findings (October 13, 2026)

The [full V8 report](V8_RESULTS.md) contains a 28-game retrospective 2026 postseason replay and four years of chronological regular-season research results, with source CSV/JSON artifacts. **These are not independently untouched prospective test sets.** The model did not beat all baselines on playoff run errors or probability Brier scores. Do not select new scoring multipliers on those 28 games and then claim their in-sample improvement demonstrates model reliability.

## Independent official schedule integrity (V10)

A separate rolling official MLB final-game schedule audit now cross-checks local imported results and original forecasts for the prior seven calendar days. It can detect the failure mode where a missing result import makes the imported-only V9 capture rate look too favorable. It is not a substitute for checking longer-term API completeness or pregame starter-source provenance. See [official schedule audit](OFFICIAL_SCHEDULE_AUDIT.md).

## Preliminary versus final pregame comparison (V12)

The earlier preview is published as a distinct immutable file and is **not** counted as an original in primary prospective accuracy or V9 missing-final coverage. The first-pitch-locked original remains the final stage. Only paired preliminary/final records from the same game that both predate first pitch are included in the special early-versus-final research comparison, and only after official settlement. See [two-stage forecasts](TWO_STAGE_FORECASTS.md).

## Postseason scoring changes after the October 2026 retrospective audit

The V13 model incorporates documented official 2020–2025 postseason scoring and a fixed prior-day-only 2026 adaptive scoring context. Its 80-game equivalent strength was selected using only earlier-season 2022–2025 scoring validation, **not** by minimizing the already-known 2026 playoff errors. Nevertheless 2026 games have been reviewed extensively during broader development, so later 2026 diagnostics are not pristine untouched validation. The original preliminary and final predictions remain frozen; experimental postseason calibration should be evaluated only on new paired, timestamped, prospectively settled games. [Read the V13 evidence](POSTSEASON_SCORING_V13.md).
