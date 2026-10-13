# Start here — MLB Prediction Lab

You already have the 2026 MLB backtest running in Visual Studio on Windows. **Recommended:** use the small ADDON ZIP and copy its contents beside `run_all.py` in your existing project. That preserves your locally imported 2026 game results.

```powershell
py -m pip install -r requirements.txt
py -m unittest discover -q
py -m streamlit run dashboard.py
```

Your default browser should open the local dashboard (usually `http://localhost:8501`). Press Ctrl+C in Developer PowerShell to stop it. See `DASHBOARD_SETUP.md` for all features and troubleshooting.

**Model labels:** winner = Elo (historically evaluated), total runs = experimental (not reliable for betting), starting pitchers = informational only, Kalshi quotes = user-entered (not linked to your account), auto-update = on browser visit (not background monitoring).
