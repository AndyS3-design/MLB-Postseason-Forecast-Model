# V29: first-writer-wins without corrupting frozen forecasts

## Problem
Two independently scheduled pregame workers may simulate the same official game with different random draws. V27 correctly refuses to overwrite the first GitHub original, but previously raised an error on the losing runner. This can cause a false-negative workflow failure and interrupt backup/health reporting.

## Safety rule
When the checkout HEAD **did not contain an original**, and the remote GitHub Contents API already contains one, V29 may accept that remote record as the authoritative first writer **only if** the official game ID, date, home/away teams, game start time and game type agree. The remote record must have an explicitly pre-first-pitch forecast timestamp, finite probabilities between 0 and 1, and (if present) a valid append-only official settlement. If the local forecast contains frozen same-simulation win-plus-Over odds, the remote must also contain its own saved joint odds. No marginal-product reconstruction is permitted.

A mismatch to a forecast that **was already present in checkout HEAD** still fails closed, as do game-identity changes, post-first-pitch originals, corrupted probabilities, missing joint odds and conflicting official results. A successful first-writer acceptance never writes any original record.

## Public website consistency
The losing simulation must **not** be published as if it were the saved forecast. V29 therefore restores the previously committed site and skips the losing run's secondary status/site commit, while allowing the main job to finish and health checks to inspect the authoritative original on `master`. The site can refresh on a subsequent normal run. If the restore cannot be completed, the workflow fails rather than publishing the losing simulation.

## Verification
`python -m unittest cloud.test_v27_original_persistence -v`

This is a reliability correction, not a new winner-probability model. It does not change weights, fit on 2026 results, modify any frozen prediction or claim 90% accuracy. Prospective cohort metrics must continue to count all official eligible finals, including games without saved predictions.

**Limit:** Timestamp validity alone is not cryptographic proof of first-pitch commit time. Independent first-original GitHub commit history still needs to be checked in the prospective scorecard.
