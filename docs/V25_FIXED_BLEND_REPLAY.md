# V25 fixed V23 model/Elo blend — strictly historical diagnostic

The V23 model/Elo **50%/50%** weight was already committed before this experiment. We use the exact untouched, historical, full 30-game 2026 postseason V20 research archive as loaded by V22. No game is dropped, no probability is re-estimated from the known result and no weight search is permitted.

The new script reads original game IDs, timestamps, results, V18 simulation probabilities, Elo probabilities and full V22 audit columns. It rejects records with duplicate IDs, shifted dates, invalid pregame cutoff, missing games or invalid probabilities; it prints the original, Elo and fixed V23 accuracy and Brier on exactly the same 30 games and uploads the full per-game table.

This is **retrospective**, not 30 live V23 challenger forecasts. Even 27/30 historical winners could not be presented as forward 90% skill. The original V23 shadow and true V22 simulated winner+Over combinations remain unmodified; blending marginal win odds does not magically create a valid combined win+Over probability.

Use the GitHub Actions run from `.github/workflows/mlb-v25-fixed-ensemble-replay.yml` to inspect actual diagnostics before any promotion.
