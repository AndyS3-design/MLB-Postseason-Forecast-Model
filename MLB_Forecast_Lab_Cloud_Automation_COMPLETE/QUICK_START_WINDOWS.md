# Windows quick start — current cloud project

The project is **already hosted** in this repository. Do **not** create another GitHub repository or upload a second ZIP inside the existing source tree.

**Live site:** https://andys3-design.github.io/MLB_Backtest_Expanded_2026_Postseason_Markets/

## From GitHub Desktop

1. Open or clone `AndyS3-design/MLB_Backtest_Expanded_2026_Postseason_Markets` on the `master` branch.
2. Use **Repository → Show in Explorer** to inspect the working folder.
3. The maintained model is inside `MLB_Forecast_Lab_Cloud_Automation_COMPLETE`; the workflow is at the repository root under `.github/workflows/mlb-cloud.yml`.
4. Make source or documentation changes in a branch when practical. Run tests before committing, then commit and push.
5. In GitHub's **Actions** tab, open **MLB Forecast Lab — game-time forecasts**. Use **Run workflow** for a manual maintenance/forecast check.
6. Check the `check`, `forecasts` (if eligible) and `deploy` jobs. A scheduled gate can correctly skip the heavy forecast job if no game is in its window.

## Python tests and local page rendering

```powershell
cd MLB_Forecast_Lab_Cloud_Automation_COMPLETE
py -m pip install -r requirements.txt
py -m unittest cloud.test_cloud cloud.test_v7 cloud.test_starter_backfill cloud.test_revision -q
py -m cloud.worker render
```

GitHub Actions uses Python 3.12. The website is a **static GitHub Pages dashboard**, so turning off a local Windows computer does not stop hosted pages or scheduled jobs.

New original forecasts aim to occur **8–30 minutes before scheduled first pitch**. The schedule checks every five minutes but is not guaranteed to run exactly on time; late/missing forecasts must not be backdated.

For troubleshooting, maintenance and safe rollback see [Operations](../docs/OPERATIONS.md). For resume-ready project details see [Portfolio](../docs/PORTFOLIO.md).
