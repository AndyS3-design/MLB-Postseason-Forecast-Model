# V15: independently frozen forecast after both official batting orders are confirmed

This upgrade is for **October 14, 2026 NLCS Game 3: Milwaukee Brewers at Los Angeles Dodgers**. The actual MLB pregame live feed returned nine ordered hitters for **both** teams at approximately 5:33 PM Eastern. It was explicitly still in `Pre-Game` status. The existing early 4:27 PM forecast was based on lineup-unconfirmed inputs.

## Verified official orders

Brewers: Jackson Chourio, Brice Turang, William Contreras, Andrew Vaughn, Jake Bauers, Garrett Mitchell, Cooper Pratt, Luis Lara, Joey Ortiz.

Dodgers: Mookie Betts, Freddie Freeman, Teoscar Hernández, Kyle Tucker, Andy Pages, Shohei Ohtani, Will Smith, Miguel Rojas, Tommy Edman.

Lineup order/identity is checked from the official MLB Stats API's `game/{gamePk}/feed/live` pregame boxscore, not guessed from earlier game lineups or postgame data.

## What changes in the forecast

The same frozen V13 training model and 2020–2026 postseason scoring prior run again. The live MLB pregame snapshot provides the **current nine hitter IDs**, allowing the model to compute player-lineup contributions using cached earlier-date hitting history. If the earlier-date sample is insufficient, the lineup factor remains neutral rather than inventing batter production. The lineup multiplier is *experimental and not independently calibrated*, so changing the lineup inputs does not imply an accuracy gain.

The new `lineup_confirmed_pregame` version is written create-exclusively under `cloud_records/lineup_previews/<game_id>_<UTC>.json`. Original preliminary JSON, V13 updated preliminary JSON and the true late final original JSON remain untouched. This is **a separate timestamped forecast**, not an overwrite or a replacement for the final.

Safety gates reject updates if the final original exists, the official game is already live, either team lacks nine confirmed batters, the calculation finishes less than 45 minutes before scheduled first pitch, or a lineup-confirmed snapshot was already saved. The request that authorizes this one additional 2026 forecast is `cloud_records/lineup_refresh_requests/849811.json`.

The website displays both verified orders and the new forecast's exact-score mode, winning probability, expected runs and 3.5/4.5/5.5/6.5 over-under probabilities. The final forecast is still targeted 8–30 minutes before first pitch. All saved pregame versions retain original creation timestamps and can be inspected separately.

## Validation

Run `python -m unittest cloud.test_v15_lineup_refresh cloud.test_v12_two_stage cloud.test_v13_postseason_context -q` from the application directory. V15 CI also runs all earlier model and prediction-integrity safeguards and checks the dashboard script with Node.

This is a game-specific request, not evidence that every future matchup has been fully lineup-verified. Future automatic lineup-triggered revisions can be added separately, with care not to delay or replace the late original forecast.
