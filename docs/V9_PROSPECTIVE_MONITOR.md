# V9 — prospective prediction coverage and audit

The **Oct 14, 2026** monitoring cohort makes MLB Forecast Lab's published prospective scorecard more honest. It tracks not only the games that received a prediction, but also **imported completed MLB games without a valid saved original forecast**.

### Definitions

- **Eligible denominator:** official completed MLB games already imported to the project's data files, with game dates on or after October 14 and strictly before today's Eastern date.
- **Captured:** one original, correctly identified prediction file with a creation timestamp **strictly before** scheduled first pitch. An earlier-than-target pregame prediction counts as captured but not inside the 8–30-minute preferred window.
- **Missed/invalid:** an eligible game with no original, a mismatched identity, or a late/invalid pregame timestamp. It is **not** patched after the result is known.
- **Settlement pending:** a timely prediction exists and the final game has been imported, but the original forecast file hasn't yet received the separate final-result metadata.
- **Final import missing:** a timely saved original exists, but the official completed game has not yet entered local data. Such games are **not** prematurely marked missed or scored.
- **Shadows:** separately locked research variants are compared only on the same settled future games; they never count as additional originals.

The dashboard's denominator is only as complete as official results successfully imported. A missing or delayed MLB API fetch can produce a partial denominator; don't describe it as covering the entire MLB schedule without checking the source.

### Files and usage

- `cloud/v9_tracking.py`: derives a fresh capture report; never reads forecast scoring outcomes as input.
- `cloud/test_v9_tracking.py`: controlled fixtures for missed, late, mismatched, pending and zero-denominator situations.
- `cloud_records/coverage_latest.json`: cumulative, machine-readable capture report regenerated at each site refresh.
- `site/data.json.prospective_capture`: published dashboard view.
- `docs/PROSPECTIVE_EXPERIMENTS.md`: shadow-variant methodology and decision criteria.

The monitor starts October 14 to prevent existing retrospective studies and older, intentionally early first forecasts from distorting prospective capture rates.

### Accuracy interpretation

A good capture rate is **operational reliability**, not forecasting skill. Winner Brier versus Elo, team-run and total-run errors, and paired shadow comparisons must be evaluated on valid saved originals and disclosed with sample sizes. Hold off on model-weight changes until enough untouched cases have settled.

**No sportsbook or prediction-market prices enter the model.**
