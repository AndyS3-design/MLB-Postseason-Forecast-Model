# V13 — One-time corrected preliminary, October 14, 2026

An existing **7.0.0** early preliminary for Brewers at Dodgers was correctly frozen at 5–3 (7.816 expected combined runs). When V13 introduced verified 2020–2026 postseason scoring and a modal exact-score display, that old original could not be changed without destroying its evidence value.

For the current game only, an explicit version- and game-ID-gated request (`cloud_records/preliminary_update_requests/849811.json`) authorizes a **separate, one-time Updated Preliminary**. The worker must fetch the official scheduled game, verify identity/date, verify the current model is `13.0.0-recent-postseason-scoring`, confirm status is genuinely pregame, and finish the complete fresh score simulation at least **45 minutes before first pitch**.

The updated record is saved create-exclusive under `cloud_records/preliminary_revisions/<game_id>_<UTC>.json`. The original record under `cloud_records/preliminary/<game_id>.json` remains byte-for-byte intact. Neither preliminary can ever be substituted for the final original under `cloud_records/predictions/<game_id>.json`, which is independently calculated in the established 8–30-minute pregame window.

The website lists both early versions, with the most recent updated preliminary ahead of the older original until the final arrives. Scores, probabilities, expected runs and model version are preserved, and the UI explicitly says that a difference between the V7 and V13 early runs is due at least in part to **changed algorithms**, not simply fresher lineups. Model-health metrics count the final only. Prospective preliminary-vs-final information-gain evaluation excludes cross-version pairs.

A missing GitHub window or a game already started cannot be repaired by backdating a new prediction. The request is intentionally one-time and is not a rule that continually revises game-day forecasts. Unit tests cover locking, cutoff, game/date identity, model-version selection, the official-final path and the dashboard.
