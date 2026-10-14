# Pages deployment 404 — verified diagnosis and permanent health check

On October 14, 2026, GitHub Pages briefly showed **404 — There isn't a GitHub Pages site here** shortly after a successful V17 deployment following a repository rename. The GitHub Actions deploy step itself reported success, but that only establishes that GitHub accepted an artifact.

A [separate real Internet check from a GitHub-hosted runner](https://github.com/AndyS3-design/MLB-Postseason-Forecast-Model/actions/runs/38649441399) at approximately **22:42 UTC / 6:42 PM Eastern** established:
- The **configured GitHub Pages API** reports `build_type: workflow`, public site, HTTPS enforcement and published URL `https://andys3-design.github.io/MLB-Postseason-Forecast-Model/`.
- GET of that exact project URL: **HTTP 200**, returning the actual dashboard HTML.
- GET of the previous, pre-rename URL: **HTTP 404**.
- GET of the bare account root `https://andys3-design.github.io/`: **HTTP 404**, since the website is a project site under the repository path.
- The initial screenshot was approximately two minutes after the earlier successful deploy; subsequent HTTP 200 is consistent with publication delay, but the API does not prove the precise underlying CDN cause.

**Verified current dashboard:** https://andys3-design.github.io/MLB-Postseason-Forecast-Model/

## Preventing future false-green workflow runs

The production `.github/workflows/mlb-cloud.yml` now has a **fifth independent job** `public_site_health`, dependent on the successful Pages deployment. It reads the actual `steps.deploy.outputs.page_url` rather than guessing a repository URL, and performs external HTTPS GET checks for:

1. The publicly accessible index page, required to contain the expected MLB Forecast Lab content;
2. The same-origin `data.json` document, required to parse as valid JSON with predictions, refresh timestamp and V17 distribution validation.

It retries up to 15 times every 20 seconds because GitHub Pages may take time to propagate. A persistent 404, wrong site, malformed/missing data or missing deployment URL results in a **failed workflow job rather than a misleading green deployment**. The real-model pipeline and all frozen predictions are unchanged.

The check uses only Python standard-library HTTP clients and read-only access. New [offline regression tests](../MLB_Forecast_Lab_Cloud_Automation_COMPLETE/cloud/test_public_site_health.py) cover 404 detection, later recovery, malformed data, and unrelated pages.

If the site shows a 404 again, inspect the **public_site_health** job as well as deploy. Check Settings → Pages for the actual published URL, whether build source remains GitHub Actions, and any customized domain. GitHub documents that publication can take up to 10 minutes after a push. Refresh the exact full project URL rather than the bare account root.
