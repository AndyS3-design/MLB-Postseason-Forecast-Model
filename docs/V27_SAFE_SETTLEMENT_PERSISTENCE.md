# V27 — Original forecast preservation and official postgame final persistence

Problem observed October 16, 2026: latest main forecast workflow [38940444652](https://github.com/AndyS3-design/MLB-Postseason-Forecast-Model/actions/runs/38940444652) failed when local data appended a valid `official_final` and `evaluation` to an immutable original (`849810.json`). The workflow had incorrectly required unchanged **raw bytes** for all saved originals.

The new helper keeps every original predicted winner probability, score distribution, Elo estimate, time stamp, run totals, and V22 same-simulation winner-plus-Over 4.5/5.5 markets **immutable**. Only a first-time, source-verified official MLB final and the matched evaluation may be appended. Previously settled records cannot be overwritten, even if only the settlement time differs.

When new originals are first saved, writes are **create-only**. For first official final append, the helper reads the current remote GitHub Contents SHA and writes with that SHA. Concurrent identical settled scores are idempotent and keep the first saved timestamp. True conflicts fail closed.

After the remote state of all originals has been verified, the runner discards locally regenerated settled prediction bytes so the independent secondary website/status commit can rebase without overriding any immutable original.

Tests: `python -m unittest cloud.test_v27_original_persistence -v`; standalone `V27 CI` plus the main job safeguards. Never claim 90% prediction accuracy from settlement or CI fixes; preserve the full prospective denominator and judge future truly pre-first-pitch games separately.
