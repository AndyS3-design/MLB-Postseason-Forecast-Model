# Your next 10 minutes: cloud-hosted MLB Forecast Lab

You already have a baseball research project on Windows. **Keep that folder unchanged.**

1. Unzip **MLB_Forecast_Cloud_Project.zip** into a NEW folder.
2. Move three *optional but valuable* files from the **old** MLB folder into the **new** matching folders:
   - `data/advanced_pitching_details.csv`
   - `data/pitcher_directory.csv`
   - `outputs/v62_pitcher_calibration.json`
   - If present: `data/mlb_2026_regular.csv`
3. Open **GitHub Desktop**, select **File → Add Local Repository**, choose the NEW folder. Choose **Create a repository here** if needed.
4. Commit, click **Publish repository**, and give it a name such as `mlb-forecast-lab`. Free GitHub Pages generally requires the repository to be public.
5. On GitHub.com, visit your repository → **Settings → Pages** → change Source to **GitHub Actions**.
6. Go to **Actions** → **MLB Forecast Lab — hourly baseball forecasts** → **Run workflow**.
7. When both jobs are green, open the site URL shown at **Settings → Pages**. Bookmark it on your phone.

If the GitHub workflow fails, copy the error text from **Actions → forecasts** into ChatGPT. The cloud runner cannot be considered live until both workflow jobs complete successfully.

**Forecast timing:** new picks are saved only ~12 minutes to 4 hours *before* official scheduled first pitch. Already-started games will correctly show no new historical pretend pick.

**Schedule caveats:** jobs run about once per hour, but GitHub does not guarantee on-time execution; published pages remain readable between runs.
