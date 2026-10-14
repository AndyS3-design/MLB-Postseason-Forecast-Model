# Frozen scoring-model cache across GitHub Action runs

This branch adds a **GitHub Actions cache** for the pre-fitted 2016–2025 Poisson model, so each new GitHub-hosted runner need not start with an empty local model cache.

## Guardrails

- `.github/workflows/mlb-cloud.yml` restores an Actions cache before forecasting; it saves the cache after a successful run.
- Cache keys incorporate dependency, model implementation, 2016–2025 Retrosheet history and the **current detailed-pitching CSV**. Changes to that CSV will invalidate the Actions cache, which is conservative (2026 updates may trigger refits).
- The Python cache layer independently verifies the entire training-feature fingerprint, scikit-learn version and the serialized file SHA-256 before reuse.
- Git ignores `outputs/v8_cache/`, and the worker refuses to commit cache artifacts even if they are somehow staged. Git commits still contain time-stamped original forecasts and official data updates.
- Forecast inputs for recent teams, starters and lineups are **always rebuilt** from eligible earlier-date MLB data; caching doesn't freeze 2026 form or override game-time cutoffs.
- Saved models are serialized with joblib and should be loaded **only** from this project's trusted GitHub Actions cache. The SHA-256 checksum provides accidental-corruption detection, **not** authenticity against an attacker able to replace both model and manifest.

## Expected improvement

In the V8 research build, the model fit/load stage changed from **1.949 seconds** to **0.022 seconds** on a cache hit, and the full historical asset build from **8.234 seconds** to **6.233 seconds**. Those figures measured within a single research job. Cross-job improvements need actual GitHub Actions statistics after cache deployment.

There is no scoring coefficient change. The 2026 postseason and walk-forward replay reports are located under `outputs/v8_audit/` and `outputs/v8_validation/`.
