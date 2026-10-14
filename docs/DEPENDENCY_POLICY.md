# Dependency policy — reproducible 2026 forecast environment

The end-user package guidance at `MLB_Forecast_Lab_Cloud_Automation_COMPLETE/requirements.txt` uses bounded ranges for supported Python/macOS/Windows developer installs.

The deployed **Ubuntu GitHub Actions, Python 3.12** forecast and V17 validation workflows instead install `requirements-ci-py312.txt`, a concrete version snapshot from [the passing V17 runner on October 14, 2026](https://github.com/AndyS3-design/MLB-Postseason-Forecast-Model/actions/runs/38648337355). The snapshot pins NumPy, SciPy, scikit-learn, Pandas and their observed transitive dependencies to reduce accidental forecast changes caused solely by an upstream package release. The original run artifact also contains `ci_python312_dependencies.txt`.

**The pinned dependency file is platform-specific, version-pinned, not hash-pinned.** Do not claim full cryptographic supply-chain reproducibility. Updating a pinned dependency requires a new branch, clean CI run, probabilistic golden-case comparisons, and an explicit research note if numeric forecasts change. Security fixes are important; schedule updates and retest rather than freezing insecure versions forever.

Production GitHub Actions checkout/setup steps use Node24-compatible `actions/checkout@v5` and `actions/setup-python@v6`, tested on the hosted runner. Older research workflows are preserved rather than modified en masse while they are not part of the daily production path.

Security considerations: the public repository must contain **no credentials, tokens, .env, or signed cloud secrets**. GitHub Action tokens should be scoped by job (only forecasting commits need contents write; Pages deploy uses pages/id-token write). Stored original forecasts are append-only by application logic; Git administrators can still rewrite history. For integrity, audit the saved game ID, immutable UTC timestamp, GitHub workflow/commit and official MLB result reconciliation.

All package fingerprints and test results are supporting reproducibility evidence, **not** a claim that ML predictive accuracy has improved.
