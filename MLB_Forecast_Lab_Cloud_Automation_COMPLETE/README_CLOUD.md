# MLB Forecast Lab Cloud Edition (Baseball-Only)

This is a **deployable GitHub Actions + GitHub Pages** variant of the V6 baseball-only forecasting model. It is not a running service until you publish the repository and enable GitHub Pages.

## What it does

- Runs a scheduled **UTC hourly** GitHub Actions job while your home computer is off.
- Refreshes completed official MLB games, excluding all games with a date on or after the forecast's New York calendar date.
- Attempts an initial download of the **2023–2025 Retrosheet detailed pitching records**, and calibrates the optional pitcher adjustment using **2024 validation only**. If the records are unavailable, it clearly labels the missing starter adjustment.
- Downloads a bounded number of **recent completed 2026 MLB box scores** per run. The actual 2026 starting-pitcher detail history builds incrementally over multiple scheduled runs; providing your already-imported CSV files accelerates setup.
- Creates one **immutable** future-game prediction per MLB game, around 12 minutes to 4 hours ahead of first pitch. It never recreates a missed prediction after the game starts.
- After results are official, adds the actual final, evaluates winner probability, run error and the total-run probability; the original forecast fields remain intact.
- Publishes a lightweight, mobile-friendly **static website** featuring one projected score, mean total runs, win probability, 0–6 versus 7+ run chances, and offense/defense/pitching ratings.
- Includes **no betting odds, sportsbook integrations, prediction markets or financial recommendations**.

## Setup (Windows + GitHub Desktop)

1. Unzip the whole project into a **new folder**, separate from your existing Visual Studio project. It contains the required `GL2023.TXT`, `GL2024.TXT`, and `GL2025.TXT` Retrosheet game logs and the model source.
2. Optional but strongly recommended: from your working Windows MLB project, copy **`data/advanced_pitching_details.csv`**, **`data/pitcher_directory.csv`**, and **`outputs/v62_pitcher_calibration.json`** into the corresponding folders here. Copy your `data/mlb_2026_regular.csv` too if you already have it. Do **not** copy API keys, passwords or personal files.
3. Install **GitHub Desktop** from https://desktop.github.com/ if needed. Use **File → Add Local Repository**, choose this new folder, and if prompted choose **Create a repository here**. Commit the initial files, then click **Publish repository**. Use `mlb-forecast-lab` as a convenient name. For free GitHub Pages, use a **public repository** (only baseball research files should be uploaded).
4. Go to your new repository on GitHub → **Settings → Pages → Build and deployment → Source: GitHub Actions**. Save.
5. Open the repo's **Actions** tab, select **MLB Forecast Lab — hourly baseball forecasts**, then **Run workflow** to initialize the data and publish the first page. Some accounts require confirming workflow enablement or setting Actions workflow permissions to **Read and write** under Settings → Actions → General. The workflow declares `contents: write`, `pages: write` and `id-token: write` as needed.
6. Wait for the two jobs **forecasts** and **deploy** to finish. Under Settings → Pages you will see your actual site URL. Its conventional form is `https://YOUR_GITHUB_USERNAME.github.io/mlb-forecast-lab/`.
7. Your computer may now be off. The site stays published, and GitHub's runners perform the scheduled jobs. To inspect failure messages: **Actions → latest run → forecasts**.

**Important:** This runs *hourly checks*, not a constantly running real-time process. GitHub may delay or skip schedules and may disable scheduled workflows in inactive public repositories (60-day rule). The website provides a **last refreshed** timestamp and warns about stale information. More reliable service levels require a paid scheduled server/monitoring system.

## Folders

| Path | Contents |
|---|---|
| `cloud/worker.py` | UTC schedules, first-pitch lock, cloud scoring and results settlement |
| `cloud/refresh.py` | Refresh completed MLB games, preserve existing files atomically |
| `.github/workflows/mlb-cloud.yml` | Hourly forecast and Pages deployment automation |
| `site/` | Static phone/desktop website; only results, not model source |
| `cloud_records/predictions/` | One stored JSON file per game with the original pregame timestamp |
| `data/` | Historic Retrosheet logs, official completed game data and optional pitcher details |
| `outputs/v62_pitcher_calibration.json` | Optional 2024-selected pitcher calibration |
| `cloud/test_cloud.py` | Offline tests of deadlines, overwrites, settlement and leakage checks |

## Local testing on Windows

```powershell
py -m pip install -r requirements.txt
py -m unittest cloud.test_cloud -v
py -m cloud.worker run --offline
```

Open `site/index.html` with a local HTTP server if you want to see the shell of the website (it will not show predictions until a pregame forecast is generated):

```powershell
py -m http.server 8000 --directory site
```

Then go to `http://localhost:8000`. Stop with Ctrl+C. A full online check requires publishing to GitHub and allowing MLB API access on GitHub Actions.

## Integrity and caveats

- Model coefficients are trained on 2023–2024 baseball games. Additional starter adjustment is selected with 2024 validation, and the known 2025/2026 diagnostic results informed development. **This is not a prospectively validated accurate or profitable model.**
- Same-day game results are **always excluded** from pregame features, even if a doubleheader's first game already finished.
- A forecast logged after the scheduled first pitch is refused. An API might reschedule a game; the stored *original* start time and creation timestamp remain visible for auditing.
- Official lineups are used only if the API provides a genuine pregame snapshot. No lineup or player result is pulled from future box scores.
- Pitcher, bullpen, lineup, venue, weather and fielding-quality data can be missing and are **not invented**. More model complexity is not automatically better. The app surfaces its data gaps.
- The single integer score is a representative simulated score; **mean total runs** is an average of all simulations and can differ from that score's sum.
- The website is **public** when GitHub Pages is configured on a public repository. Only publish baseball-model inputs and forecasts you intend to share. GitHub secrets aren't needed by this project.
- No sportsbook or betting-market feeds are used anywhere in this cloud project.

## Attribution

The historical game-log files in this research bundle originate from Retrosheet. *The information used here was obtained free of charge from and is copyrighted by Retrosheet. Interested parties may contact Retrosheet at www.retrosheet.org.* Official MLB Stats API data are subject to MLB's usage policies.
